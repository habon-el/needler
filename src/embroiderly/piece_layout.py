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
FIELDS = {'name', 'group', 'visible', 'locked', 'matrix', 'rotation', 'source', 'rings', 'cut'}
MAX_COPIES = 100
MAX_PART_POINTS = 20000


def geometry_changed(options):
    return any(item.get('matrix', IDENTITY) != IDENTITY or not item.get('visible', True) or 'source' in item
               or item.get('cut') for item in edits(options).values())


def copy_ids(options):
    """Pieces that are duplicates of another piece (not shapes found in the picture)."""
    return {key for key, item in edits(options).items() if 'source' in item}


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
            if 'source' not in item or not isinstance(rings, list) or not rings or any(
                    not isinstance(r, list) or len(r) < 3 or any(
                        not isinstance(p, list) or len(p) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in p)
                        for p in r) for r in rings):
                raise ValueError('A cut part has an invalid outline.')
        if 'cut' in item and item['cut'] is not True:
            raise ValueError('Invalid cut piece.')
    if sum('source' in item for item in value.values()) > MAX_COPIES:
        raise ValueError(f'Use at most {MAX_COPIES} copied or cut pieces.')
    if sum(len(r) for item in value.values() for r in item.get('rings', [])) > MAX_PART_POINTS:
        raise ValueError('Cut parts have too many outline points. Simplify the artwork first.')
    return value


def inventory(region_report, options, width, height, scale):
    saved = edits(options)
    areas = list(region_report['areas'])
    # Duplicates reuse their original's outline and colour, with their own transform and style.
    by_id = {a['id']: a for a in areas}
    styles = options.get('region_styles', {}) if isinstance(options.get('region_styles', {}), dict) else {}
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
    if areas:
        left,top,right,bottom=bounds([r for area in areas for r in area['rings']])
        origin=np.array([(left+right)*scale/2,(top+bottom)*scale/2])
    result = []
    hoop = options.get('piece_hoop_mm', [100, 100])
    if not isinstance(hoop, list) or len(hoop) != 2 or any(type(v) not in (float, int) or not math.isfinite(v) or not 10 <= v <= 1000 for v in hoop):
        raise ValueError('Hoop width and height must be 10–1000 mm.')
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
        from .region_stitches import satin_rails
        try:
            satin_rails(rings, 1)
        except ValueError as error:
            reason = str(error)
        if area['style'] in ('satin', 'raised_satin') and reason:
            level = 'red'; messages.append(reason)
        outside = left < -hoop[0]/2 or right > hoop[0]/2 or top < -hoop[1]/2 or bottom > hoop[1]/2
        if outside:
            messages.append('Piece extends outside the hoop.'); level = 'red'
        pixel_rings = [((np.asarray(r)+origin)/scale).tolist() for r in rings]
        result.append(dict(id=area['id'], order=index+1, name=item.get('name') or f'Part {index+1}',
                           group=item.get('group', ''), colour=area['colour'], style=area['style'],
                           visible=item.get('visible', True), locked=item.get('locked', False), copy='source' in item,
                           rings_mm=rings, rings=pixel_rings, x_mm=(left+right)/2, y_mm=(top+bottom)/2,
                           width_mm=right-left, height_mm=bottom-top, rotation=item.get('rotation', 0),
                           nodes=sum(len(r) for r in rings), area_mm2=area_mm2, satin_reason=reason,
                           audit=dict(level=level, messages=messages, outside_hoop=outside, minimum_area_mm2=floor)))
    return dict(pieces=result, hoop_mm=hoop, origin_mm=origin.tolist(), scale=scale,
                transformed=geometry_changed(options),unavailable=region_report.get('unavailable', ''))


def change(options, report, command):
    """Apply one atomic command to geometry; callers regenerate before committing."""
    if not isinstance(command, dict) or set(command)-{'ids', 'field', 'value', 'linked'}:
        raise ValueError('Invalid piece edit.')
    ids = command.get('ids')
    if not isinstance(ids, list) or not ids or len(set(ids)) != len(ids):
        raise ValueError('Select the pieces to edit.')
    selected = [p for p in report['pieces'] if p['id'] in ids]
    if len(selected) != len(ids):
        raise ValueError('A selected piece no longer exists.')
    field, value = command.get('field'), command.get('value')
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
    if field == 'knife':
        return knife(updated, report, selected, value)
    if field == 'delete':
        if not set(ids) <= copies:
            raise ValueError('Only copied pieces can be deleted. Hide an original piece instead.')
        for key in ids:
            stored.pop(key, None)
            updated.get('region_styles', {}).pop(key, None)
            updated.get('area_holes', {}).pop(key, None)
        edits(updated)
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


def knife(updated, report, selected, value):
    """Cut one piece along a straight line (two points in mm, as drawn on the hoop).
    Each part becomes its own piece in the same place, with the piece's style."""
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
    for index, part in enumerate(sorted(parts, key=lambda g: -g.area)):
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
    ignore = {'piece_edits', 'region_styles', 'interactions'}
    if {k:v for k,v in previous.items() if k not in ignore} != {k:v for k,v in proposed.items() if k not in ignore}:
        raise ValueError('A piece is locked. Unlock it before changing artwork, colours or design-wide settings.')
    new = edits(proposed)
    for key, item in locked.items():
        if new.get(key) != item or previous.get('region_styles', {}).get(key, 'tatami') != proposed.get('region_styles', {}).get(key, 'tatami'):
            raise ValueError('This piece is locked. Unlock it before changing it.')


def render(image, report):
    """Artwork-only raster view. Generation consumes precise vector rings instead."""
    from PIL import Image
    array = np.zeros((image.height, image.width, 4), np.uint8)
    for p in report['pieces']:
        if not p['visible']:
            continue
        mask = np.zeros(array.shape[:2], np.uint8)
        cv2.fillPoly(mask, [np.rint(r).astype(np.int32) for r in p['rings']], 1)
        array[mask > 0] = [int(p['colour'][i:i+2], 16) for i in (1, 3, 5)]+[255]
    return Image.fromarray(array)
