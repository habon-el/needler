"""What the written machine files sew, read back from disk and set against the design.

The preview draws the engine's plan with a chosen thread width and light; this reads the
DST and PES as a machine would and measures the stitches themselves: their size next to
the size drawn, stitches over empty fabric (the release gate's own check, counted here
rather than raised), the design's filled shapes the thread leaves bare, and how far apart
fill rows really are. A report, not a gate: crossings already block the download.
"""
import math

import cv2
import numpy as np
import pyembroidery as emb
from shapely.geometry import Point
from shapely.prepared import prep

from . import svg_geometry as sg
from .machine_files import read_pattern
from .stitch_fills import fill_shape

THREAD_MM = .4      # a sewn 40-weight thread lies about this wide on fabric
BARE_MM = .4        # a bare part wider than a thread shows as fabric (lettering_coverage.BARE_MM)
SIZE_MM = .6        # sewn and drawn sizes this close (or 2 %) are the same: pull, file grid
ROW_GAP_MM = .2     # fill rows further apart than asked by more than this leave a space
GRID_PIXELS = 6e6   # coverage raster budget (0.1 mm cells up to 245 x 245 mm)
# Area styles sewn closed: fabric between their stitches is a gap. Open and textured
# fills, appliqué fabric and running lines leave fabric showing on purpose.
DENSE = {None, 'auto_fill', 'auto_satin', 'step_fill', 'contour_fill', 'wave_fill', 'florentine_fill',
         'sculptured_fill', 'radial_fill', 'puff_satin', 'feathered_fill'}
ROWS = {None, 'auto_fill', 'step_fill', 'feathered_fill'}   # straight parallel rows


def design_shapes(svg_path, shift=(0.0, 0.0)):
    """Filled areas of the stitch document, in the machine file's millimetres, with how
    they are sewn; and the drawn bounds of everything sewn (lines and borders too).
    shift: how far the files were moved after the stitch document was made (pieces), mm."""
    root = sg.load(str(svg_path))
    scale = sg.document_scale(root)
    origin = sg.origin(root)
    ox, oy = (origin[0]*scale, origin[1]*scale) if origin is not None else (0.0, 0.0)
    ox, oy = ox-shift[0], oy-shift[1]
    areas, points = [], []
    for node, paths, style, _ in sg.elements(root, tolerance=.02/scale):
        mm = [([(x*scale-ox, y*scale-oy) for x, y in pts], closed) for pts, closed in paths]
        points += [p for pts, _ in mm for p in pts]
        fill = sg.colour(style.get('fill', '#000000')) if 'fill' in style or sg.local(node.tag) != 'line' else None
        if fill is None or node.get('{http://inkstitch.org/namespace}satin_column') == 'true':
            continue
        rings = [(pts, True) for pts, _ in mm if len(pts) >= 3]
        shape = fill_shape(rings, 'evenodd' if style.get('fill-rule') == 'evenodd' else 'nonzero') if rings else None
        if shape is None or shape.is_empty:
            continue
        get = lambda name, default=None: node.get('{http://inkstitch.org/namespace}'+name, default)
        areas.append(dict(shape=shape, colour=fill, method=get('fill_method'),
                          spacing=float(get('row_spacing_mm', .25))))
    bounds = (min(p[0] for p in points), min(p[1] for p in points),
              max(p[0] for p in points), max(p[1] for p in points)) if points else None
    return areas, bounds


def _segments(pattern, threads):
    """Sewn segments (stitch after stitch on one thread) in mm, with their thread."""
    out, colour, previous = [], 0, None
    for x, y, flags in pattern.stitches:
        kind = flags & emb.COMMAND_MASK
        if kind == emb.STITCH:
            point = (x/10, y/10)
            if previous is not None and previous != point:
                out.append((previous, point, threads[colour] if colour < len(threads) else None))
            previous = point
            continue
        if kind == emb.COLOR_CHANGE:
            colour += 1
        # A jump, cut or stop moves or holds the needle without sewing: the next stitch
        # starts a new segment.
        previous = None
    return out


def coverage(areas, segments):
    """Parts of the closed (dense) areas no sewn thread covers, wider than BARE_MM; and a
    test for whether any sewn thread lies over a point (machine-file millimetres)."""
    dense = [a['shape'] for a in areas if a['method'] in DENSE]
    if not dense or not segments:
        return dict(covered_percent=None, bare=[], bare_count=0), lambda x, y: True
    left = min(s.bounds[0] for s in dense)-1; top = min(s.bounds[1] for s in dense)-1
    right = max(s.bounds[2] for s in dense)+1; bottom = max(s.bounds[3] for s in dense)+1
    cell = max(.1, math.sqrt((right-left)*(bottom-top)/GRID_PIXELS))
    size = (int(math.ceil((bottom-top)/cell))+1, int(math.ceil((right-left)/cell))+1)
    px = lambda p: (int(round((p[0]-left)/cell*8)), int(round((p[1]-top)/cell*8)))
    drawn = np.zeros(size, np.uint8)
    for shape in dense:
        for polygon in getattr(shape, 'geoms', [shape]):
            rings = [np.array([px(p) for p in polygon.exterior.coords], np.int32)]
            holes = [np.array([px(p) for p in ring.coords], np.int32) for ring in polygon.interiors]
            cv2.fillPoly(drawn, rings, 1, shift=3)
            if holes:
                cv2.fillPoly(drawn, holes, 0, shift=3)
    sewn = np.zeros(size, np.uint8)
    width = max(1, int(round(THREAD_MM/cell)))
    for a, b, _ in segments:
        cv2.line(sewn, px(a), px(b), 1, width, cv2.LINE_8, 3)
    bare = (drawn > 0) & (sewn == 0)
    total = int(drawn.sum())
    reach = max(1, int(round(BARE_MM/2/cell)))
    disk = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*reach+1, 2*reach+1))
    core = cv2.erode(bare.astype(np.uint8), disk)
    patches = []
    if core.any():
        wide = cv2.dilate(core, disk) & bare.astype(np.uint8)
        count, labels, stats, centres = cv2.connectedComponentsWithStats(wide, connectivity=8)
        for label in range(1, count):
            area = float(stats[label, cv2.CC_STAT_AREA])*cell*cell
            cx, cy = centres[label]
            patches.append(dict(x_mm=round(cx*cell+left, 2), y_mm=round(cy*cell+top, 2), area_mm2=round(area, 2)))
        patches.sort(key=lambda p: -p['area_mm2'])
    def sewn_at(x, y):
        col, row = int(round((x-left)/cell)), int(round((y-top)/cell))
        return not (0 <= row < size[0] and 0 <= col < size[1]) or bool(sewn[row, col])
    return dict(covered_percent=round(100*(1-bare.sum()/total), 1) if total else None, bare=patches[:20],
                bare_count=len(patches)), sewn_at


def rows(areas, segments, sewn_at=lambda x, y: True):
    """How far apart the fill rows of each straight-row fill really are: the nearest row
    on each side that runs beside it (overlaps it along the rows), measured across. A gap
    wider than asked counts as a space where no other thread covers its middle line
    either (a narrow tip's rows stop short under an outline sewn over them)."""
    out = []
    for area in areas:
        if area['method'] not in ROWS:
            continue
        inside = prep(area['shape'].buffer(.05))
        mine = []
        for a, b, colour in segments:
            if colour != area['colour'] or math.dist(a, b) < .3:
                continue
            middle = ((a[0]+b[0])/2, (a[1]+b[1])/2)
            if inside.contains(Point(middle)):
                mine.append((a, b))
        if len(mine) < 6:
            continue
        # The row direction: the commonest stitch direction, weighted by length.
        angles = np.array([math.degrees(math.atan2(b[1]-a[1], b[0]-a[0])) % 180 for a, b in mine])
        lengths = np.array([math.dist(a, b) for a, b in mine])
        # Short stitches on the 0.1 mm file grid point anywhere within a few degrees: they
        # vote little, and join a row within the angle their rounding allows.
        votes = np.bincount(np.rint(angles).astype(int) % 180, np.where(lengths >= .8, lengths, 0), 180)
        votes = votes+np.roll(votes, 1)+np.roll(votes, -1)
        angle = math.radians(int(votes.argmax()))
        u, n = (math.cos(angle), math.sin(angle)), (-math.sin(angle), math.cos(angle))
        along = [(min(a[0]*u[0]+a[1]*u[1], b[0]*u[0]+b[1]*u[1]), max(a[0]*u[0]+a[1]*u[1], b[0]*u[0]+b[1]*u[1]),
                  ((a[0]+b[0])/2*n[0]+(a[1]+b[1])/2*n[1]))
                 for (a, b), d, length in zip(mine, angles, lengths)
                 if min(abs(d-math.degrees(angle)), 180-abs(d-math.degrees(angle))) <= 4+math.degrees(math.atan(.07/length))]
        if len(along) < 6:
            continue
        along.sort(key=lambda r: r[2])
        # Rows: stitches at one offset across (within the 0.1 mm file grid's rounding).
        grouped = []
        for start, end, offset in along:
            if grouped and offset-grouped[-1][0][-1] <= .08:
                grouped[-1][0].append(offset); grouped[-1][1].append((start, end))
            else:
                grouped.append(([offset], [(start, end)]))
        lines = [(float(np.mean(o)), spans) for o, spans in grouped]
        gaps = []
        for i, (offset, spans) in enumerate(lines):
            for other, others in lines[i+1:]:
                if other-offset > 3.0:
                    break
                # Beside it: the two rows run together for at least 0.5 mm.
                shared = max((min(e1, e2)-max(s1, s2) for s1, e1 in spans for s2, e2 in others), default=0)
                if shared >= .5:
                    start = next(max(s1, s2) for s1, e1 in spans for s2, e2 in others if min(e1, e2)-max(s1, s2) == shared)
                    middle = (other+offset)/2
                    at = lambda t: (t*u[0]+middle*n[0], t*u[1]+middle*n[1])
                    steps = max(2, int(shared/.1))
                    bare = sum(not sewn_at(*at(start+shared*k/steps)) for k in range(steps+1))*shared/steps
                    gaps.append((other-offset, bare, at(start+shared/2)))
                    break
        if not gaps:
            continue
        spacing = [g for g, _, _ in gaps]
        widest, _, where = max(gaps)
        wide = [(g, w) for g, bare, w in gaps if g > area['spacing']+ROW_GAP_MM and bare >= .5]
        if wide:
            widest, where = max(wide)
        out.append(dict(colour=area['colour'], asked_mm=round(area['spacing'], 2),
                        measured_mm=round(float(np.median(spacing)), 2), widest_mm=round(widest, 2),
                        gaps=len(wide), x_mm=round(where[0], 2), y_mm=round(where[1], 2)))
    return out


def _bounds(pattern):
    points = [(x/10, y/10) for x, y, flags in pattern.stitches if flags & emb.COMMAND_MASK == emb.STITCH]
    if not points:
        return None
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def proof(directory, mask=None, scale=None, origin=None, shift=(0.0, 0.0), canvas_mm=None):
    """Read design.dst and design.pes back from disk and measure them against design.svg.
    shift: how far the files were moved after the stitch document (pieces), in mm.
    mask/scale/origin: the release context, for counting stitches over empty fabric.
    canvas_mm: (width, height) of the canvas the person set."""
    from .export_findings import inspect
    areas, drawn = design_shapes(directory/'design.svg', shift)
    files, threads = {}, None
    for fmt in ('pes', 'dst'):
        pattern = read_pattern(directory/('design.'+fmt))
        if fmt == 'pes':
            threads = [t.hex_color() for t in pattern.threadlist]
        # DST keeps no colours: its blocks follow the same colour changes as the PES.
        segments = _segments(pattern, threads)
        box = _bounds(pattern)
        report = dict(stitches=sum(1 for *_, f in pattern.stitches if f & emb.COMMAND_MASK == emb.STITCH),
                      width_mm=round(box[2]-box[0], 1) if box else 0.0, height_mm=round(box[3]-box[1], 1) if box else 0.0)
        if mask is not None:
            issues = inspect(pattern, mask, scale, origin)
            crossing = [i for i in issues if i['code'] in ('crossing', 'travel')]
            report['crossings'] = len(crossing)
            if crossing:
                report['first_crossing'] = crossing[0]['location']
        files[fmt] = report
    # segments: the DST's (read last); the PES sews the same commands.
    result = dict(files=files, width_mm=files['dst']['width_mm'], height_mm=files['dst']['height_mm'])
    if drawn:
        result['drawn_mm'] = [round(drawn[2]-drawn[0], 1), round(drawn[3]-drawn[1], 1)]
    if canvas_mm:
        result['canvas_mm'] = [round(float(canvas_mm[0]), 1), round(float(canvas_mm[1]), 1)]
    result['coverage'], sewn_at = coverage(areas, segments)
    result['rows'] = rows(areas, segments, sewn_at)
    result['notes'] = notes(result)
    return result


def _differ(a, b):
    return abs(a-b) > max(SIZE_MM, .02*max(a, b))


def notes(result):
    """Plain sentences for the person, only where the files do not sew what was asked."""
    out = []
    files = result['files']
    if _differ(files['pes']['width_mm'], files['dst']['width_mm']) or _differ(files['pes']['height_mm'], files['dst']['height_mm']):
        out.append(f"The PES sews {files['pes']['width_mm']:g} × {files['pes']['height_mm']:g} mm "
                   f"and the DST {files['dst']['width_mm']:g} × {files['dst']['height_mm']:g} mm.")
    width, height = result['width_mm'], result['height_mm']
    drawn = result.get('drawn_mm')
    if drawn and (_differ(width, drawn[0]) or _differ(height, drawn[1])):
        out.append(f'The files sew {width:g} × {height:g} mm; the design is drawn {drawn[0]:g} × {drawn[1]:g} mm.')
    canvas = result.get('canvas_mm')
    if canvas and _differ(height, canvas[1]) and height > 0:
        # The canvas height includes the empty margins around the subject.
        out.append(f"Sewn size {width:g} × {height:g} mm: the canvas you set is {canvas[1]:g} mm high with empty margins. "
                   f"For a design {canvas[1]:g} mm high, set the canvas to {canvas[1]*canvas[1]/height:.1f} mm.")
    crossings = sum(f.get('crossings', 0) for f in files.values())
    if crossings:
        first = files['dst'].get('first_crossing') or files['pes'].get('first_crossing')
        out.append(f"{files['dst'].get('crossings', 0)} stitches in the DST and {files['pes'].get('crossings', 0)} in the PES "
                   f"cross empty fabric" + (f", first at x {first['x_mm']:g}, y {first['y_mm']:g} mm." if first else '.'))
    bare = result['coverage'].get('bare') or []
    if bare:
        first = bare[0]
        count = result['coverage']['bare_count']
        out.append(f"{count} bare part{'s' if count > 1 else ''} wider than a thread "
                   f"in the filled areas, the largest {first['area_mm2']:g} mm² at x {first['x_mm']:g}, y {first['y_mm']:g} mm.")
    gaps = [r for r in result['rows'] if r['gaps']]
    if gaps:
        worst = max(gaps, key=lambda r: r['widest_mm'])
        count = sum(r['gaps'] for r in gaps)
        out.append(f"Fill rows with spaces: {count} place{'s' if count > 1 else ''} where rows are up to {worst['widest_mm']:g} mm apart "
                   f"(asked {worst['asked_mm']:g} mm), at x {worst['x_mm']:g}, y {worst['y_mm']:g} mm.")
    return out
