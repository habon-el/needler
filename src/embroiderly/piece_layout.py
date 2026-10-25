"""Piece geometry, identity and locks. Machine coordinates are never transformed.

IDs refer to the untransformed prepared contour. Matrices operate on millimetres
relative to the artwork/hoop centre; positive Y points down, like the canvas.
The outline is transformed BEFORE stitch generation. Bounding boxes are measured
from outline points, not padded raster boxes. No minimum-size cleanup runs here.
"""
from copy import deepcopy
import math
import re

import cv2
import numpy as np

IDENTITY = [1., 0., 0., 1., 0., 0.]
FIELDS = {'name', 'group', 'visible', 'locked', 'matrix', 'rotation', 'source', 'rings', 'cut', 'drawn', 'under', 'line'}
LINE_STITCHES = ('running', 'triple')   # open lines: a fine single run, or each stitch sewn three times
LINE_SHAPES = ('line', 'freehand_line')
FILL_GAP_MM = .4      # click to fill: gaps in the lines up to about twice this are bridged
FILL_TUCK_MM = .3     # the fill reaches this far under the lines around it, so no gap shows
SHAPES = ('rectangle', 'ellipse', 'polygon', 'freehand', 'line', 'freehand_line')
MAX_DRAWN_POINTS = 2000
MAX_COPIES = 100
MAX_PART_POINTS = 20000


def geometry_changed(options):
    return any(item.get('matrix', IDENTITY) != IDENTITY or not item.get('visible', True) or 'source' in item
               or item.get('cut') or 'drawn' in item for item in edits(options).values())


def copy_ids(options):
    """Pieces that are duplicates of another piece or drawn shapes (not shapes found in the picture)."""
    return {key for key, item in edits(options).items() if 'source' in item or 'drawn' in item}


def bounds(rings):
    points = np.concatenate([np.asarray(r).reshape(-1, 2) for r in rings])
    lo, hi = points.min(axis=0), points.max(axis=0)
    return [float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1])]


def matrix(value):
    if not isinstance(value, list) or len(value) != 6:
        raise ValueError('Invalid piece transform.')
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in value):
        raise ValueError('Piece measurements must be finite numbers.')
    a, b, c, d, x, y = value
    if abs(a*d-b*c) < 1e-10 or max(abs(v) for v in value) > 10000:
        raise ValueError('The piece transform is too small or too large.')
    return np.array([[a, c, x], [b, d, y], [0., 0., 1.]])


def packed(m):
    return [float(m[0, 0]), float(m[1, 0]), float(m[0, 1]),
            float(m[1, 1]), float(m[0, 2]), float(m[1, 2])]


def edits(options):
    value = options.get('piece_edits', {})
    if not isinstance(value, dict) or len(value) > 500:
        raise ValueError('Expected at most 500 piece edits.')
    for key, item in value.items():
        if not re.fullmatch('[a-f0-9]{20}', key) or not isinstance(item, dict) or set(item)-FIELDS:
            raise ValueError('Invalid saved piece.')
        matrix(item.get('matrix', IDENTITY))
        for field in ('name', 'group'):
            if field in item and (not isinstance(item[field], str) or len(item[field]) > 100):
                raise ValueError('Piece names and groups must be under 100 characters.')
        for field in ('visible', 'locked'):
            if field in item and type(item[field]) is not bool:
                raise ValueError('Visibility and lock must be true or false.')
        angle = item.get('rotation', 0)
        if type(angle) not in (int, float) or not math.isfinite(angle):
            raise ValueError('Invalid rotation.')
        if 'source' in item and (not isinstance(item['source'], str) or not re.fullmatch('[a-f0-9]{20}', item['source'])
                                 or 'source' in value.get(item['source'], {})):
            raise ValueError('A copied piece must point to an original piece.')
        if 'rings' in item:
            rings = item['rings']
            if not ('source' in item or 'drawn' in item) or not isinstance(rings, list) or not rings or any(
                    not isinstance(r, list) or len(r) < (2 if 'line' in item or 'line' in value.get(item.get('source'), {}) else 3) or any(
                        not isinstance(p, list) or len(p) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in p)
                        for p in r) for r in rings):
                raise ValueError('A cut part has an invalid outline.')
        if 'drawn' in item and ('source' in item or 'rings' not in item or not isinstance(item['drawn'], str)
                                or not re.fullmatch('#[0-9a-f]{6}', item['drawn'])):
            raise ValueError('A drawn shape needs an outline and a thread colour.')
        if 'line' in item and (item['line'] not in LINE_STITCHES or 'drawn' not in item or len(item.get('rings', [])) != 1):
            raise ValueError('Invalid stitched line.')
        if 'under' in item and (item['under'] is not True or 'drawn' not in item):
            raise ValueError('Invalid filled space.')
        if 'cut' in item and item['cut'] is not True:
            raise ValueError('Invalid cut piece.')
    if sum('source' in item or 'drawn' in item for item in value.values()) > MAX_COPIES:
        raise ValueError(f'Use at most {MAX_COPIES} copied or cut pieces.')
    if sum(len(r) for item in value.values() for r in item.get('rings', [])) > MAX_PART_POINTS:
        raise ValueError('Cut parts have too many outline points. Simplify the artwork first.')
    return value


def inventory(region_report, options, width, height, scale):
    saved = edits(options)
    areas = list(region_report['areas'])
    picture = list(areas)
    styles = options.get('region_styles', {}) if isinstance(options.get('region_styles', {}), dict) else {}
    # Drawn shapes: their own outline (picture pixels) and thread colour; they can be copied and cut too.
    for key, item in saved.items():
        if 'drawn' in item:
            areas.append({'id': key, 'colour': item['drawn'], 'rings': item['rings'], 'style': styles.get(key, 'tatami'),
                          'under': item.get('under', False), 'line': item.get('line')})
    # Duplicates reuse their original's outline and colour, with their own transform and style.
    by_id = {a['id']: a for a in areas}
    for key, item in saved.items():
        if 'source' in item and item['source'] in by_id:
            source = by_id[item['source']]
            # Cut parts carry their own outline (picture pixels, before any transform).
            areas.append({**source, 'id': key, 'style': styles.get(key, source['style']),
                          **({'rings': item['rings']} if 'rings' in item else {})})
    # A piece the knife cut is replaced by its parts.
    areas = [a for a in areas if not saved.get(a['id'], {}).get('cut')]
    missing = set(saved)-{a['id'] for a in areas}-{k for k, v in saved.items() if v.get('cut')}
    if missing:
        raise ValueError('Artwork shapes changed. Undo the artwork change before editing saved pieces; names and locks will not be attached to different shapes.')
    # Match the legacy engine's initial subject-centred hoop origin. Keep this
    # origin fixed as individual pieces move; never recenter after a transform.
    origin = np.array([width*scale/2, height*scale/2])
    # Only shapes found in the picture set the origin, so drawing a shape never moves the others.
    if picture:
        left,top,right,bottom=bounds([r for area in picture for r in area['rings']])
        origin=np.array([(left+right)*scale/2,(top+bottom)*scale/2])
    result = []
    hoop = options.get('piece_hoop_mm', [100, 100])
    if not isinstance(hoop, list) or len(hoop) != 2 or any(type(v) not in (float, int) or not math.isfinite(v) or not 10 <= v <= 1000 for v in hoop):
        raise ValueError('Hoop width and height must be 10–1000 mm.')
    if 'hoop_id' in options and (not isinstance(options['hoop_id'], str) or not re.fullmatch('[a-z0-9-]{1,60}', options['hoop_id'])):
        raise ValueError('Choose a listed hoop.')
    # Existing user-owned minimum-region setting, not a new silent seed.
    floor = float(options.get('floor_mm2', 1))
    for index, area in enumerate(areas):
        item = saved.get(area['id'], {})
        m = matrix(item.get('matrix', IDENTITY))
        rings = []
        for ring in area['rings']:
            points = np.asarray(ring, float)*scale-origin
            rings.append((np.c_[points, np.ones(len(points))] @ m.T)[:, :2].tolist())
        left, top, right, bottom = bounds(rings)
        if area.get('line'):
            # An open stitched line: no area, no satin; its length is what matters.
            length = float(np.linalg.norm(np.diff(np.asarray(rings[0]), axis=0), axis=1).sum())
            outside = left < -hoop[0]/2 or right > hoop[0]/2 or top < -hoop[1]/2 or bottom > hoop[1]/2
            messages = (['Piece extends outside the hoop.'] if outside else []) + [f'Stitched line, {length:.1f} mm long.']
            result.append(dict(id=area['id'], order=index+1, name=item.get('name') or f'Line {index+1}',
                               group=item.get('group', ''), colour=area['colour'], style='line', line=area['line'],
                               visible=item.get('visible', True), locked=item.get('locked', False), copy=True, under=False,
                               rings_mm=rings, rings=[((np.asarray(r)+origin)/scale).tolist() for r in rings],
                               x_mm=(left+right)/2, y_mm=(top+bottom)/2, width_mm=right-left, height_mm=bottom-top,
                               rotation=item.get('rotation', 0), nodes=len(rings[0]), area_mm2=0.0,
                               satin_reason='A stitched line has no satin.',
                               audit=dict(level='red' if outside else 'green', messages=messages, outside_hoop=outside,
                                          minimum_area_mm2=floor)))
            continue
        from .region_stitches import polygon
        shape = polygon(rings, 1)
        area_mm2 = float(shape.area)
        level = 'red' if area_mm2 < floor else 'green'
        messages = [f'{area_mm2:.3f} mm²; minimum region {floor:g} mm². Nothing removed.'] if level == 'red' else ['Area check passed; sew-out still required.']
        from .release_gate import MIN_STITCH_MM
        rectangle=np.asarray(shape.minimum_rotated_rectangle.exterior.coords)[:4]
        span=float(np.linalg.norm(np.roll(rectangle,-1,axis=0)-rectangle,axis=1).min())
        if span < MIN_STITCH_MM:
            if level == 'green':level='yellow'
            messages.append(f'Bounding span {span:.3f} mm is below the {MIN_STITCH_MM:g} mm output-segment minimum; check the generated route. This is a geometric warning, not a fabric assessment.')
        reason = ''
        from .region_stitches import satin_reason
        reason = satin_reason(rings, 1)
        if area['style'] == 'satin' and reason:
            level = 'red'; messages.append(reason)
        outside = left < -hoop[0]/2 or right > hoop[0]/2 or top < -hoop[1]/2 or bottom > hoop[1]/2
        if outside:
            messages.append('Piece extends outside the hoop.'); level = 'red'
        pixel_rings = [((np.asarray(r)+origin)/scale).tolist() for r in rings]
        result.append(dict(id=area['id'], order=index+1, name=item.get('name') or f'Part {index+1}',
                           group=item.get('group', ''), colour=area['colour'], style=area['style'],
                           visible=item.get('visible', True), locked=item.get('locked', False), copy='source' in item or 'drawn' in item,
                           under=bool(area.get('under')), outline=(options.get('area_outlines') or {}).get(area['id']),
                           rings_mm=rings, rings=pixel_rings, x_mm=(left+right)/2, y_mm=(top+bottom)/2,
                           width_mm=right-left, height_mm=bottom-top, rotation=item.get('rotation', 0),
                           nodes=sum(len(r) for r in rings), area_mm2=area_mm2, satin_reason=reason,
                           audit=dict(level=level, messages=messages, outside_hoop=outside, minimum_area_mm2=floor)))
    return dict(pieces=result, hoop_mm=hoop, origin_mm=origin.tolist(), scale=scale,
                transformed=geometry_changed(options),unavailable=region_report.get('unavailable', ''))


def change(options, report, command, image=None):
    """Apply one atomic command to geometry; callers regenerate before committing."""
    if not isinstance(command, dict) or set(command)-{'ids', 'field', 'value', 'linked'}:
        raise ValueError('Invalid piece edit.')
    if command.get('field') == 'draw':
        return draw(deepcopy(options), report, command.get('value'))
    if command.get('field') == 'click_fill':
        if image is None:
            raise ValueError('Click to fill needs the prepared artwork.')
        return click_fill(deepcopy(options), report, image, command.get('value'))
    ids = command.get('ids')
    if not isinstance(ids, list) or not ids or len(set(ids)) != len(ids):
        raise ValueError('Select the pieces to edit.')
    selected = [p for p in report['pieces'] if p['id'] in ids]
    if len(selected) != len(ids):
        raise ValueError('A selected piece no longer exists.')
    field, value = command.get('field'), command.get('value')
    if field == 'sew_order':
        # Sewing order by hand: every part, in the order to sew it; None goes back to automatic.
        # It moves no piece, so locked pieces can be reordered too.
        from .sew_sequence import choices
        if value is None:
            updated = deepcopy(options)
            updated.pop('sew_sequence', None)
            return updated
        known = {p['id'] for p in report['pieces']}
        if not isinstance(value, list) or not set(ids) <= set(value) or any(key not in known for key in value if isinstance(key, str)):
            raise ValueError('The parts changed. Generate the stitches again, then change the sewing order.')
        updated = deepcopy(options)
        updated['sew_sequence'] = value
        choices(updated)
        return updated
    if any(p['locked'] for p in selected) and not (field == 'locked' and value is False):
        raise ValueError('This piece is locked. Unlock it before changing it.')
    updated = deepcopy(options); stored = updated.setdefault('piece_edits', {})
    copies = copy_ids(options)
    if field == 'duplicate':
        # Duplicate with offset: each copy keeps its original's look and moves by [dx, dy] mm.
        if not isinstance(value, list) or len(value) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 500 for v in value):
            raise ValueError('Enter a copy offset within 500 mm.')
        import hashlib
        shift = np.array([[1, 0, value[0]], [0, 1, value[1]], [0, 0, 1.]])
        for p in selected:
            original = stored.get(p['id'], {}).get('source', p['id'])
            n = 0
            while True:
                key = hashlib.sha256(f'{original}:{n}'.encode()).hexdigest()[:20]
                if key not in stored:
                    break
                n += 1
            base = stored.get(p['id'], {})
            stored[key] = {'source': original, 'matrix': packed(shift @ matrix(base.get('matrix', IDENTITY))),
                           'rotation': base.get('rotation', 0), 'name': (p['name']+' copy')[:100],
                           **({'rings': base['rings']} if 'rings' in base else {})}
            style = updated.get('region_styles', {}).get(p['id'])
            if style:
                updated.setdefault('region_styles', {})[key] = style
        edits(updated)
        return updated
    if field in ('mirror_copy', 'circle', 'array'):
        # Repeat: a mirrored copy, copies around a circle, or rows and columns (piece_patterns).
        from .piece_patterns import repeat
        repeat(updated, selected, field, value, len(copies))
        edits(updated)
        return updated
    if field in ('weld', 'smooth'):
        # Weld pieces of one thread into one, or smooth an outline (piece_weld); picking order counts.
        from .piece_weld import run
        return run(updated, report, sorted(selected, key=lambda p: ids.index(p['id'])), field, value)
    if field in ('knife', 'split_satin'):
        if any(p.get('line') for p in selected):
            raise ValueError('A stitched line cannot be cut. Delete it and draw it again.')
        return knife(updated, report, selected, value, satin=field == 'split_satin')
    if field == 'delete':
        if not set(ids) <= copies:
            raise ValueError('Only copied pieces and drawn shapes can be deleted. Hide an original piece instead.')
        # Copies and cut parts of a deleted drawn shape go with it.
        ids = ids+[k for k, item in stored.items() if item.get('source') in ids and k not in ids]
        for key in ids:
            stored.pop(key, None)
            updated.get('region_styles', {}).pop(key, None)
            updated.get('area_holes', {}).pop(key, None)
            updated.get('area_angles', {}).pop(key, None)
            updated.get('area_outlines', {}).pop(key, None)
        edits(updated)
        return updated
    if field == 'outline':
        # Outline per part: {stitch, offset_mm, width_mm, colour}, or None to remove it.
        from .part_outlines import choices
        outlines = updated.setdefault('area_outlines', {})
        for p in selected:
            if p.get('line'):
                raise ValueError('A stitched line has no outline. Choose a filled part.')
            if value is None:
                outlines.pop(p['id'], None)
            else:
                outlines[p['id']] = value
        choices(updated)
        return updated
    if field in ('name', 'group', 'visible', 'locked'):
        for p in selected:
            stored.setdefault(p['id'], {})[field] = value
        edits(updated)
        return updated
    if field == 'style':
        from .region_stitches import assignments
        styles = updated.setdefault('region_styles', {})
        for p in selected:
            styles[p['id']] = value
        assignments(updated)
        return updated
    if field in ('align', 'distribute', 'match_size'):
        # Line up several pieces; the order they were picked decides which one sets the size.
        from .piece_arrange import arrange
        return arrange(updated, sorted(selected, key=lambda p: ids.index(p['id'])), field, value)
    if field not in ('position', 'x_mm', 'y_mm', 'width_mm', 'height_mm', 'rotation', 'rotate_by', 'mirror', 'skew'):
        raise ValueError('Unsupported piece property.')
    if field == 'mirror' and value not in ('x', 'y'):
        raise ValueError('Mirror left-right (x) or top-bottom (y).')
    if field not in ('position', 'mirror') and (type(value) not in (int, float) or not math.isfinite(value)):
        raise ValueError('Enter a finite measurement.')
    left, top, right, bottom = bounds([r for p in selected for r in p['rings_mm']])
    cx, cy = (left+right)/2, (top+bottom)/2
    op = np.eye(3)
    if field == 'position':
        if not isinstance(value, list) or len(value) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in value):
            raise ValueError('Enter two finite position measurements.')
        op[0, 2], op[1, 2] = round(value[0], 1)-cx, round(value[1], 1)-cy
    elif field in ('x_mm', 'y_mm'):
        axis = 0 if field == 'x_mm' else 1
        op[axis, 2] = round(value, 1)-(cx if axis == 0 else cy)
    elif field == 'mirror':
        # Flip around the selection's centre; rows and stitch angles mirror with it.
        sx, sy = (-1, 1) if value == 'x' else (1, -1)
        op = np.array([[sx, 0, cx*(1-sx)], [0, sy, cy*(1-sy)], [0, 0, 1]])
    elif field == 'skew':
        # Lean the shape sideways by this many degrees (top moves right for positive).
        if not -60 <= value <= 60:
            raise ValueError('Skew must be between -60° and 60°.')
        t = -math.tan(math.radians(value))
        op = np.array([[1, t, -t*cy], [0, 1, 0], [0, 0, 1]])
    elif field in ('width_mm', 'height_mm'):
        if not .1 <= value <= 1000:
            raise ValueError('Size must be between 0.1 and 1000 mm.')
        ratio = round(value, 1)/(right-left if field == 'width_mm' else bottom-top)
        sx = ratio if field == 'width_mm' or command.get('linked', True) else 1
        sy = ratio if field == 'height_mm' or command.get('linked', True) else 1
        op = np.array([[sx, 0, cx*(1-sx)], [0, sy, cy*(1-sy)], [0, 0, 1]])
    else:
        # Single: absolute angle. Multi: requested group rotation delta. rotate_by: always a delta.
        delta = value if field == 'rotate_by' else value-(selected[0]['rotation'] if len(selected) == 1 else 0)
        angle = math.radians(delta); c, s = math.cos(angle), math.sin(angle)
        op = np.array([[c, -s, cx-c*cx+s*cy], [s, c, cy-s*cx-c*cy], [0, 0, 1]])
    for p in selected:
        item = stored.setdefault(p['id'], {})
        item['matrix'] = packed(op @ matrix(item.get('matrix', IDENTITY)))
        if field in ('rotation', 'rotate_by'):
            item['rotation'] = (p['rotation']+delta) % 360
        elif field == 'mirror':
            item['rotation'] = (-p['rotation']) % 360
    edits(updated)
    return updated


def draw(updated, report, value):
    """Add a drawn shape as a new piece. value: {shape, points (mm on the hoop), colour}.
    Rectangle and ellipse take two opposite corners; polygon and freehand take the outline points."""
    import hashlib
    from shapely.geometry import Polygon
    if not isinstance(value, dict) or not {'shape', 'points', 'colour'} <= set(value) <= {'shape', 'points', 'colour', 'stitch'} \
            or value['shape'] not in SHAPES:
        raise ValueError('Choose a rectangle, ellipse, polygon or freehand shape.')
    if value['shape'] in LINE_SHAPES:
        return draw_line(updated, report, value)
    colour, points = value['colour'], value['points']
    if not isinstance(colour, str) or not re.fullmatch('#[0-9a-fA-F]{6}', colour):
        raise ValueError('Choose a thread colour for the shape.')
    if not isinstance(points, list) or not 2 <= len(points) <= MAX_DRAWN_POINTS or any(
            not isinstance(p, list) or len(p) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1000 for v in p)
            for p in points):
        raise ValueError('Draw the shape on the hoop.')
    points = np.asarray(points, float)
    if value['shape'] in ('rectangle', 'ellipse'):
        (x0, y0), (x1, y1) = points.min(axis=0), points.max(axis=0)
        if value['shape'] == 'rectangle':
            outline = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        else:
            t = np.linspace(0, 2*math.pi, 72, endpoint=False)
            outline = np.c_[(x0+x1)/2+(x1-x0)/2*np.cos(t), (y0+y1)/2+(y1-y0)/2*np.sin(t)]
        shape = Polygon(outline)
    else:
        if len(points) < 3:
            raise ValueError('A polygon needs at least three points.')
        # A freehand line that crosses itself keeps its largest enclosed part.
        shape = Polygon(points).buffer(0)
        if shape.geom_type == 'MultiPolygon':
            shape = max(shape.geoms, key=lambda g: g.area)
        shape = shape.simplify(.1 if value['shape'] == 'freehand' else 0)
    if shape.is_empty or shape.geom_type != 'Polygon' or shape.area < 1.0:
        raise ValueError('The shape is too small to stitch. Draw at least 1 mm² of area.')
    origin, scale = np.array(report['origin_mm']), report['scale']
    ring = [[round(x, 2), round(y, 2)] for x, y in ((np.asarray(shape.exterior.coords[:-1])+origin)/scale).tolist()]
    stored = updated.setdefault('piece_edits', {})
    n = 0
    while True:
        key = hashlib.sha256(f'drawn:{ring}:{n}'.encode()).hexdigest()[:20]
        if key not in stored:
            break
        n += 1
    count = sum('drawn' in item for item in stored.values())+1
    stored[key] = {'drawn': colour.lower(), 'rings': [ring], 'name': f"{value['shape'].capitalize()} {count}"}
    edits(updated)
    return updated


def draw_line(updated, report, value):
    """An open stitched line (clicked points or freehand), sewn as a running or triple stitch."""
    import hashlib
    from shapely.geometry import LineString
    colour, points, stitch = value['colour'], value['points'], value.get('stitch', 'running')
    if not isinstance(colour, str) or not re.fullmatch('#[0-9a-fA-F]{6}', colour):
        raise ValueError('Choose a thread colour for the line.')
    if stitch not in LINE_STITCHES:
        raise ValueError('Choose a running or triple stitch line.')
    if not isinstance(points, list) or not 2 <= len(points) <= MAX_DRAWN_POINTS or any(
            not isinstance(p, list) or len(p) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1000 for v in p)
            for p in points):
        raise ValueError('Draw the line on the hoop.')
    line = LineString(points)
    if value['shape'] == 'freehand_line':
        line = line.simplify(.1)
    if line.length < 2:
        raise ValueError('The line is too short to stitch. Draw at least 2 mm.')
    origin, scale = np.array(report['origin_mm']), report['scale']
    ring = [[round(x, 2), round(y, 2)] for x, y in ((np.asarray(line.coords)+origin)/scale).tolist()]
    stored = updated.setdefault('piece_edits', {})
    n = 0
    while True:
        key = hashlib.sha256(f'line:{ring}:{n}'.encode()).hexdigest()[:20]
        if key not in stored:
            break
        n += 1
    count = sum('line' in item for item in stored.values())+1
    stored[key] = {'drawn': colour.lower(), 'rings': [ring], 'line': stitch, 'name': f'Line {count}'}
    edits(updated)
    return updated


def click_fill(updated, report, image, value):
    """Click to fill: the empty space under the click, closed by the artwork around it, becomes
    a new piece in the chosen thread. Small gaps in the lines are bridged; a space open to the
    outside is refused. The fill is sewn first and reaches a little under the lines, so the lines
    (and, without holes, the parts inside it) lie on top. value: {point (mm), colour, holes}."""
    import hashlib
    if not isinstance(value, dict) or set(value) != {'point', 'colour', 'holes'} or type(value['holes']) is not bool:
        raise ValueError('Click inside an empty space to fill it.')
    colour, point = value['colour'], value['point']
    if not isinstance(colour, str) or not re.fullmatch('#[0-9a-fA-F]{6}', colour):
        raise ValueError('Choose a thread colour for the fill.')
    if not isinstance(point, list) or len(point) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in point):
        raise ValueError('Click inside an empty space to fill it.')
    rgba = np.asarray(image)
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError('Click to fill needs the prepared artwork.')
    scale = report['scale']
    x, y = ((np.asarray(point, float)+np.array(report['origin_mm']))/scale).round().astype(int)
    height, width = rgba.shape[:2]
    if not (0 <= x < width and 0 <= y < height):
        raise ValueError('Click inside the artwork.')
    sewn = (rgba[:, :, 3] > 127).astype(np.uint8)
    if sewn[y, x]:
        raise ValueError('This part is already stitched. Click an empty space, or choose its stitch type in Stitch styles.')
    gap = max(1, int(round(FILL_GAP_MM/scale)))
    disc = lambda r: cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*r+1, 2*r+1))
    # Close small gaps in the lines first, so the fill does not leak out through them.
    open_space = (1-cv2.dilate(sewn, disc(gap))).astype(np.uint8)
    if not open_space[y, x]:
        raise ValueError('Click a little further from the lines.')
    count, labels = cv2.connectedComponents(open_space, connectivity=4)
    space = (labels == labels[y, x]).astype(np.uint8)
    if space[0, :].any() or space[-1, :].any() or space[:, 0].any() or space[:, -1].any():
        raise ValueError('This space is open to the outside. Click inside a closed shape, or close the gap in the lines.')
    # Back out to the lines, then a little under them.
    space = cv2.dilate(space, disc(gap)) & (1-sewn)
    space = cv2.dilate(space, disc(max(1, int(round(FILL_TUCK_MM/scale)))))
    contours, hierarchy = cv2.findContours(space, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    outer = max((i for i in range(len(contours)) if hierarchy[0, i, 3] == -1), key=lambda i: cv2.contourArea(contours[i]))
    rings = [contours[outer]]
    if value['holes']:
        child = hierarchy[0, outer, 2]
        while child != -1:
            if cv2.contourArea(contours[child]) >= 4:
                rings.append(contours[child])
            child = hierarchy[0, child, 0]
    if cv2.contourArea(rings[0])*scale*scale < 1.0:
        raise ValueError('This space is too small to fill. Fill at least 1 mm².')
    rings = [[[float(px), float(py)] for px, py in cv2.approxPolyDP(r, .5, True)[:, 0, :]] for r in rings]
    rings = [r for r in rings if len(r) >= 3]
    stored = updated.setdefault('piece_edits', {})
    n = 0
    while True:
        key = hashlib.sha256(f'fill:{rings[0]}:{n}'.encode()).hexdigest()[:20]
        if key not in stored:
            break
        n += 1
    count = sum('drawn' in item for item in stored.values())+1
    stored[key] = {'drawn': colour.lower(), 'rings': rings, 'name': f'Fill {count}', 'under': True}
    edits(updated)
    return updated


def knife(updated, report, selected, value, satin=False):
    """Cut one piece along a straight line (two points in mm, as drawn on the hoop).
    Each part becomes its own piece in the same place, with the piece's style.
    satin (Satin here): the narrow side becomes satin, reaching LIMB_OVERLAP_MM under the rest,
    which keeps its fill and is sewn first, as the automatic thin-limb split does."""
    import hashlib
    from shapely.geometry import Polygon
    if len(selected) != 1:
        raise ValueError('Select one piece to cut.')
    if not isinstance(value, list) or len(value) != 2 or any(
            not isinstance(p, list) or len(p) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in p)
            for p in value):
        raise ValueError('Draw the cut as a line across the piece.')
    p = selected[0]
    stored = updated['piece_edits']
    item = stored.get(p['id'], {})
    inverse = np.linalg.inv(matrix(item.get('matrix', IDENTITY)))
    origin, scale = np.array(report['origin_mm']), report['scale']
    def to_source(points):
        points = np.asarray(points, float)
        return ((np.c_[points, np.ones(len(points))] @ inverse.T)[:, :2]+origin)/scale
    rings = [to_source(r) for r in p['rings_mm']]
    shape = Polygon(rings[0], rings[1:]).buffer(0)
    a, b = to_source(value)
    d = b-a
    if np.hypot(*d) < 1e-9:
        raise ValueError('Draw the cut as a line across the piece.')
    # Two half-planes on either side of the (extended) line, large enough for the piece.
    span = max(shape.bounds[2]-shape.bounds[0], shape.bounds[3]-shape.bounds[1])*4+10
    u = d/np.hypot(*d); n = np.array([-u[1], u[0]])
    far_a, far_b = a-u*span, a+u*span
    halves = [Polygon([far_a, far_b, far_b+n*span, far_a+n*span]), Polygon([far_a, far_b, far_b-n*span, far_a-n*span])]
    parts = []
    for half in halves:
        piece = shape.intersection(half)
        parts += [g for g in getattr(piece, 'geoms', [piece]) if g.geom_type == 'Polygon' and g.area > 1.0]
    if len(parts) < 2:
        raise ValueError('The cut line must cross the piece from one side to the other.')
    source = item.get('source', p['id'])
    style = updated.get('region_styles', {}).get(p['id'])
    parts = sorted(parts, key=lambda g: -g.area)
    styles = [style]*len(parts)
    if satin:
        from .engine import LIMB_OVERLAP_MM
        from .region_stitches import satin_reason
        forward = matrix(item.get('matrix', IDENTITY))
        def to_mm(ring):
            points = np.asarray(ring.coords[:-1])*scale-origin
            return (np.c_[points, np.ones(len(points))] @ forward.T)[:, :2]
        narrow = [i for i, g in enumerate(parts) if not satin_reason([to_mm(r) for r in (g.exterior, *g.interiors)], 1)]
        if not narrow:
            from .region_stitches import TURNING_SATIN_MM
            raise ValueError(f'Neither side is narrow enough for satin (up to {TURNING_SATIN_MM:g} mm wide). Cut closer to the thin part.')
        # The smallest side that can be satin; it reaches under the rest so no gap opens at the cut.
        chosen = narrow[-1]
        reach = LIMB_OVERLAP_MM/scale/np.sqrt(abs(np.linalg.det(forward[:2, :2])))
        grown = shape.intersection(parts[chosen].buffer(reach))
        parts[chosen] = max(getattr(grown, 'geoms', [grown]), key=lambda g: g.area if g.geom_type == 'Polygon' else 0)
        styles = ['tatami' if style == 'satin' else style]*len(parts)
        styles[chosen] = 'satin'
        # The fill first, the satin last: it lies on top.
        order = [i for i in range(len(parts)) if i != chosen]+[chosen]
        parts, styles = [parts[i] for i in order], [styles[i] for i in order]
    for index, part in enumerate(parts):
        style = styles[index]
        part = part.simplify(.3)
        key = hashlib.sha256(f"{p['id']}:{a.tolist()}:{b.tolist()}:{index}".encode()).hexdigest()[:20]
        stored[key] = {'source': source, 'rings': [[[round(x, 2), round(y, 2)] for x, y in r.coords[:-1]]
                                                   for r in (part.exterior, *part.interiors)],
                       'matrix': item.get('matrix', IDENTITY), 'rotation': item.get('rotation', 0),
                       'name': f"{p['name']} part {index+1}"[:100]}
        if style:
            updated.setdefault('region_styles', {})[key] = style
    if 'source' in item:
        del stored[p['id']]
        updated.get('region_styles', {}).pop(p['id'], None)
    else:
        stored.setdefault(p['id'], {})['cut'] = True
    edits(updated)
    return updated


def guard(previous, proposed):
    """Shared server guard for saved locks, including assistant/automatic changes.

    Unlock is a separate explicit piece command, handled by the route AFTER this
    comparison. A client cannot evade a lock by omitting piece_edits in options.
    """
    locked = {key: item for key, item in edits(previous).items() if item.get('locked')}
    if not locked:
        return
    # The sewing order, the hoop and stitch edits (a stop, a cut, one stitch) move no piece, so they can change
    # while a piece is locked.
    ignore = {'piece_edits', 'region_styles', 'interactions', 'area_outlines', 'sew_sequence', 'piece_hoop_mm', 'hoop_id',
              'stitch_edits'}
    if {k:v for k,v in previous.items() if k not in ignore} != {k:v for k,v in proposed.items() if k not in ignore}:
        raise ValueError('A piece is locked. Unlock it before changing artwork, colours or design-wide settings.')
    new = edits(proposed)
    for key, item in locked.items():
        if new.get(key) != item or previous.get('region_styles', {}).get(key, 'tatami') != proposed.get('region_styles', {}).get(key, 'tatami') \
                or previous.get('area_outlines', {}).get(key) != proposed.get('area_outlines', {}).get(key):
            raise ValueError('This piece is locked. Unlock it before changing it.')


def render(image, report):
    """Artwork-only raster view. Generation consumes precise vector rings instead."""
    from PIL import Image
    array = np.zeros((image.height, image.width, 4), np.uint8)
    for p in report['pieces']:
        if not p['visible']:
            continue
        mask = np.zeros(array.shape[:2], np.uint8)
        if p.get('line'):
            cv2.polylines(mask, [np.rint(r).astype(np.int32) for r in p['rings']], False, 1, thickness=2)
        else:
            cv2.fillPoly(mask, [np.rint(r).astype(np.int32) for r in p['rings']], 1)
        array[mask > 0] = [int(p['colour'][i:i+2], 16) for i in (1, 3, 5)]+[255]
    return Image.fromarray(array)
