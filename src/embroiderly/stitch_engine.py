"""Needler's own stitch generator: annotated SVG -> machine-neutral stitch plan.

Reads the stitch parameters our pipeline writes on each SVG element (fill
method, angle, row spacing, satin rails, running length, locks, trims) and
returns the pyembroidery JSON plan consumed by the existing writers and release
gate. Objects are sewn in document order. Coordinates are tenths of a
millimetre relative to the document's explicit origin (or the design centre).
"""
import hashlib
import json
import math
from pathlib import Path
from . import svg_geometry as sg
from .stitch_fills import contour, fill_shape, join_runs, meander, spiral, tatami
from .stitch_paths import bean, chain, enforce_min, order_runs, path_length, running, split_long
from .stitch_satin import satin

NS = '{http://inkstitch.org/namespace}'
NAME = 'Needler native engine'
VERSION = 1
MODULES = ('stitch_engine.py', 'stitch_fills.py', 'stitch_satin.py', 'stitch_paths.py', 'svg_geometry.py',
           'satin_font.py', 'line_art.py')
DEFAULT_LOCK = '1 -1 1 -1'


def fingerprint():
    """Identity of the generator code, used in place of an external binary."""
    h = hashlib.sha256(f'{NAME}:{VERSION}'.encode())
    for name in MODULES:
        h.update(Path(__file__).with_name(name).read_bytes())
    return h.hexdigest()


def _attr(node, name, default=None):
    value = node.get(NS+name)
    return default if value is None else value


def _float(node, name, default):
    try:
        value = float(_attr(node, name, default))
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) else default


def _bool(node, name, default=False):
    value = _attr(node, name)
    if value is None:
        return default
    return str(value).strip().lower() in ('true', '1', 'yes')


def _seed(node, index):
    value = _attr(node, 'random_seed')
    if value is not None:
        try:
            return int(value)
        except ValueError:
            pass
    return int(hashlib.sha256((node.get('id') or str(index)).encode()).hexdigest()[:8], 16)


def _lock_positions(node, end, scale_default):
    kind = _attr(node, 'lock_'+end, 'default')
    if kind == 'none':
        return []
    pattern = _attr(node, 'lock_custom_'+end, DEFAULT_LOCK) if kind == 'custom' else DEFAULT_LOCK
    if any(c.isalpha() for c in pattern):
        # SVG-path form: x coordinates are positions along the path in mm;
        # the final segment only orients the pattern and is not sewn.
        points = [p for path, _ in sg.parse_path(pattern) for p in path]
        scale = _float(node, 'lock_'+end+'_scale_percent', 100)/100
        return [x*scale for x, _ in points[1:-1]]
    try:
        steps = [float(v) for v in pattern.split()]
    except ValueError:
        steps = [1, -1, 1, -1]
    scale = _float(node, 'lock_'+end+'_scale_mm', scale_default)
    positions, total = [], 0.0
    for step in steps:
        total += step
        positions.append(total*scale)
    return positions


def _direction(points, from_end):
    sequence = points[::-1] if from_end else points
    anchor = sequence[0]
    for p in sequence[1:]:
        d = math.dist(anchor, p)
        if d >= .3:
            return ((p[0]-anchor[0])/d, (p[1]-anchor[1])/d)
    for p in sequence[1:]:
        d = math.dist(anchor, p)
        if d > 1e-9:
            return ((p[0]-anchor[0])/d, (p[1]-anchor[1])/d)
    return (1.0, 0.0)


def _along(points, distance):
    """First point on the sewn path that is `distance` from its start in a
    straight line. Locks retrace the path itself, so they stay inside narrow
    tips, while each lock stitch keeps its full length."""
    origin = points[0]
    if distance <= 0:
        return origin
    best = origin
    for a, b in zip(points, points[1:]):
        if math.dist(origin, b) >= distance:
            # Solve |a + t(b-a) - origin| = distance on this leg.
            dx, dy = b[0]-a[0], b[1]-a[1]; fx, fy = a[0]-origin[0], a[1]-origin[1]
            qa, qb, qc = dx*dx+dy*dy, 2*(fx*dx+fy*dy), fx*fx+fy*fy-distance*distance
            disc = max(0.0, qb*qb-4*qa*qc)
            t = (-qb+math.sqrt(disc))/(2*qa) if qa > 1e-12 else 1.0
            t = min(1.0, max(0.0, t))
            return (a[0]+dx*t, a[1]+dy*t)
        if math.dist(origin, b) > math.dist(origin, best):
            best = b
    return best


def _with_locks(points, start_lock, end_lock):
    out = list(points)
    if start_lock:
        p = points[0]
        if path_length(points) < max(start_lock):
            u = _direction(points, False)
            lock = [(p[0]+u[0]*s, p[1]+u[1]*s) for s in start_lock]
        else:
            lock = [_along(points, s) for s in start_lock]
        out = [p]+lock+out[1:]
        if start_lock[-1] != 0:
            out.insert(len(start_lock)+1, p)
    if end_lock:
        p = points[-1]
        backwards = points[::-1]
        if path_length(points) < max(end_lock):
            u = _direction(points, True)
            lock = [(p[0]+u[0]*s, p[1]+u[1]*s) for s in end_lock]
        else:
            lock = [_along(backwards, s) for s in end_lock]
        out += lock
        if end_lock[-1] != 0:
            out.append(p)
    return out


class Block:
    """One sewn run of one element: thread colour, points and routing hints."""

    def __init__(self, colour, points, node, trim_after, lockable=True):
        self.colour, self.points, self.node = colour, points, node
        self.trim_after, self.lockable = trim_after, lockable


def _satin_area(shape, spacing, pull, min_len):
    """Narrow or small areas as satin columns along their centre lines (the way
    small shapes and lettering are digitized), joined by inside travel."""
    from .satin_font import area_columns
    runs = []
    for a, b, closed, width in area_columns(shape):
        a, b = list(a), list(b)
        try:
            points = satin([(a, closed), (b, closed)], spacing, pull, center_walk=2*width >= 1.0,
                           indexed=len(a) == len(b))
        except ValueError:
            continue
        if len(points) >= 2:
            runs.append(points)
    return join_runs(runs, shape, 1.5) if runs else []


def _element_blocks(node, paths, style, scale, index, min_len):
    stroke = sg.colour(style.get('stroke'))
    fill = sg.colour(style.get('fill', '#000000')) if 'fill' in style or sg.local(node.tag) != 'line' else None
    mm = [([(x*scale, y*scale) for x, y in pts], closed) for pts, closed in paths]
    if not mm:
        return []
    trim = _bool(node, 'trim_after')
    blocks = []
    def emit(colour, runs):
        runs = [r for r in runs if len(r) >= 2]
        for i, run in enumerate(runs):
            blocks.append(Block(colour, run, node, trim if i == len(runs)-1 else True))
    satin_column = _bool(node, 'satin_column')
    if fill and not satin_column:
        shape = fill_shape([(pts, True) for pts, _ in mm], 'evenodd' if style.get('fill-rule') == 'evenodd' else 'nonzero')
        inset = _float(node, 'edge_inset_mm', 0)
        if inset > 0 and not shape.buffer(-inset).is_empty:
            shape = shape.buffer(-inset, join_style='mitre')
        if not shape.is_empty:
            spacing = max(.1, _float(node, 'row_spacing_mm', .25))
            length = max(.5, _float(node, 'running_stitch_length_mm', 1.5))
            tolerance = max(.01, _float(node, 'running_stitch_tolerance_mm', .1))
            method = _attr(node, 'fill_method', 'auto_fill')
            if method == 'contour_fill':
                runs = contour(shape, spacing, length, min_len, tolerance=tolerance)
            elif method == 'circular_fill':
                runs = spiral(shape, spacing, length, min_len, tolerance=tolerance)
            elif method == 'auto_satin':
                runs = _satin_area(shape, max(.2, _float(node, 'zigzag_spacing_mm', .4)),
                                   _float(node, 'pull_compensation_mm', 0), min_len) or \
                    tatami(shape, _float(node, 'angle', 0), spacing, 3.0, 4, min_len)
            elif method == 'meander_fill':
                cell = max(.6, _float(node, 'meander_scale_percent', 100)/100*10)
                runs = meander(shape, cell, length, min_len, _seed(node, index), tolerance=tolerance)
            else:
                underlay = _bool(node, 'fill_underlay', True)
                runs = tatami(shape, _float(node, 'angle', 0), spacing,
                              max(1.0, _float(node, 'max_stitch_length_mm', 3.0)),
                              max(1, int(_float(node, 'staggers', 4))), min_len,
                              underlay=underlay,
                              underlay_angle=(float(_attr(node, 'fill_underlay_angle')) if _attr(node, 'fill_underlay_angle') not in (None, '') else None),
                              underlay_spacing=(_float(node, 'fill_underlay_row_spacing_mm', 0) or None),
                              underlay_inset=_float(node, 'fill_underlay_inset_mm', .3),
                              underlay_max_len=max(1.0, _float(node, 'fill_underlay_max_stitch_length_mm', 3.0)))
            emit(fill, runs)
    if stroke:
        if satin_column and len(mm) >= 2:
            pull = [float(v) for v in str(_attr(node, 'pull_compensation_mm', '0')).split() if v] or [0.0]
            points = satin(mm, max(.1, _float(node, 'zigzag_spacing_mm', .4)), pull if len(pull) > 1 else pull[0],
                           center_walk=_bool(node, 'center_walk_underlay'),
                           contour_underlay=_bool(node, 'contour_underlay'),
                           zigzag_underlay=_bool(node, 'zigzag_underlay'),
                           walk_repeats=max(1, int(_float(node, 'center_walk_underlay_repeats', 2))),
                           indexed=_attr(node, 'satin_pairs') == 'indexed')
            emit(stroke, [points])
        else:
            length = max(.3, _float(node, 'running_stitch_length_mm', 2.5))
            tolerance = max(0.0, _float(node, 'running_stitch_tolerance_mm', .2))
            repeats = int(_float(node, 'bean_stitch_repeats', 0))
            # Fragments that meet become one line; then sew nearest-first.
            runs = order_runs(chain([pts for pts, _ in mm]))
            area = _attr(node, 'travel_area')
            if area:
                region = fill_shape([([(x*scale, y*scale) for x, y in pts], True)
                                     for pts, _ in sg.parse_path(area)], 'evenodd')
                if not region.is_empty:
                    runs = join_runs(runs, region, length)
            runs = [running(run, length, tolerance) for run in runs]
            emit(stroke, [bean(run, repeats) for run in runs if len(run) >= 2])
    return blocks


def generate(source):
    """Return the stitch plan dictionary for an SVG document (text, bytes or path)."""
    root = sg.load(source)
    scale = sg.document_scale(root)
    document_min = None
    for node in root.iter():
        if sg.local(node.tag) == 'min_stitch_len_mm' and node.text:
            try:
                document_min = float(node.text)
            except ValueError:
                pass
    collapse = 3.0
    for node in root.iter():
        if sg.local(node.tag) == 'collapse_len_mm' and node.text:
            try:
                collapse = float(node.text)
            except ValueError:
                pass
    blocks = []
    for index, (node, paths, style, _) in enumerate(sg.elements(root, tolerance=.02/scale)):
        min_len = _float(node, 'min_stitch_length_mm', document_min if document_min is not None else .45)
        made = _element_blocks(node, paths, style, scale, index, min_len)
        for block in made:
            block.min_len = min_len
            block.start_lock = _lock_positions(node, 'start', .6)
            block.end_lock = _lock_positions(node, 'end', .6)
        blocks.extend(made)
    if not blocks:
        raise ValueError('The design has no stitchable objects.')
    origin = sg.origin(root)
    if origin is not None:
        origin = (origin[0]*scale, origin[1]*scale)
    else:
        xs = [p[0] for b in blocks for p in b.points]; ys = [p[1] for b in blocks for p in b.points]
        origin = ((min(xs)+max(xs))/2, (min(ys)+max(ys))/2)
    return assemble(blocks, origin, collapse)


def assemble(blocks, origin, collapse):
    threads, stitches = [], []
    def put(point, command):
        stitches.append([round((point[0]-origin[0])*10, 3), round((point[1]-origin[1])*10, 3), command])
    needle = None; colour = None; previous = None
    for i, block in enumerate(blocks):
        points = enforce_min(block.points, block.min_len)
        if len(points) < 2:
            continue
        follower = next((b for b in blocks[i+1:] if len(b.points) >= 2), None)
        change = colour != block.colour
        cut = previous is not None and (change or previous.trim_after)
        gap = needle is not None and math.dist(needle, points[0])
        # Short hops inside one colour are sewn directly; longer ones jump.
        joined = previous is not None and not cut and gap <= collapse
        if previous is not None and not cut and not joined and gap > 6.0:
            cut = True
        ends_here = follower is None or block.trim_after or follower.colour != block.colour or \
            math.dist(points[-1], follower.points[0]) > collapse
        start_lock = [] if joined else block.start_lock
        end_lock = block.end_lock if ends_here else []
        sewn = split_long(_with_locks(points, start_lock, end_lock), 7.0)
        if cut:
            put(needle, 'TRIM')
        if change:
            if previous is not None:
                put(needle, 'COLOR_CHANGE')
            threads.append(block.colour)
            colour = block.colour
        if joined:
            # Absorb penetrations closer than the minimum to the needle; a
            # block that is entirely within that distance is not sewn at all.
            ahead = list(sewn)
            while ahead and math.dist(needle, ahead[0]) < block.min_len:
                ahead.pop(0)
            if not ahead:
                previous = block
                continue
            for p in split_long([needle, ahead[0]], 3.0)[1:]:
                put(p, 'STITCH')
            sewn = [needle]+ahead
        else:
            put(sewn[0], 'JUMP')
            put(sewn[0], 'STITCH')
        for p in sewn[1:]:
            put(p, 'STITCH')
        needle = sewn[-1]; previous = block
    if not stitches:
        raise ValueError('The design produced no stitches.')
    if previous is not None and previous.trim_after:
        put(needle, 'TRIM')
    put(needle, 'END')
    return {'threadlist': [dict(color=c, description=None, catalog_number=None, details=None,
                                brand=None, chart=None, weight=None) for c in threads],
            'stitches': _tidy(stitches, min(b.min_len for b in blocks)), 'extras': {}}


def _tidy(stitches, minimum):
    """Final check on the 0.1 mm machine grid that every sewn stitch keeps the
    minimum length after rounding; drop the in-between penetration otherwise."""
    limit = minimum*10-.5
    out = []
    run = []          # indices in `out` of the current attached run
    for x, y, command in stitches:
        grid = (round(x), round(y))
        if command == 'STITCH' and run:
            last = out[run[-1]]
            if math.dist((round(last[0]), round(last[1])), grid) < limit:
                if len(run) > 1:
                    # Replace the previous penetration rather than adding a short stitch.
                    before = out[run[-2]]
                    if math.dist((round(before[0]), round(before[1])), grid) >= limit:
                        out[run[-1]] = [x, y, command]
                continue
        out.append([x, y, command])
        if command == 'STITCH':
            run.append(len(out)-1)
        else:
            run = []
    return out


def generate_plan(svg_path):
    """Bytes of the JSON plan, the same interface the exporter expects."""
    return json.dumps(generate(Path(svg_path).read_bytes())).encode()
