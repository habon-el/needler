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
from .stitch_fills import (STIPPLE_STITCHES, WAVE_AMPLITUDE_MM, WAVE_LENGTH_MM, contour, fill_shape, gradient, join_runs,
                           meander, radial, spiral, step_fill, tatami, wave)
from .stitch_paths import (MOTIFS, backstitch, bean, blackwork_run, blanket, candlewick, chain, couching, dedupe,
                           enforce_min, hand_stitch, inward_side, motif_run,
                           order_runs, path_length, polygons, running, split_long, stemstitch, zigzag_outline)
from .stitch_satin import SPLIT_MM, satin
from shapely.geometry import LineString

NS = '{http://inkstitch.org/namespace}'
NAME = 'Needler native engine'
VERSION = 1
MODULES = ('stitch_engine.py', 'stitch_fills.py', 'stitch_satin.py', 'stitch_paths.py', 'svg_geometry.py',
           'satin_font.py', 'line_art.py')
DEFAULT_LOCK = '1 -1 1 -1'
PUFF_LOCK = '1 -1 1 -1 1 -1'


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


def _lock_positions(node, end, scale_default, default=DEFAULT_LOCK):
    kind = _attr(node, 'lock_'+end, 'default')
    if kind == 'none':
        return []
    pattern = _attr(node, 'lock_custom_'+end, default) if kind == 'custom' else default
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

    def __init__(self, colour, points, node, trim_after, lockable=True, puff=False, placement=False):
        self.colour, self.points, self.node = colour, points, node
        # A plain running (or triple) line: its centre line, and how to stitch it again
        # from another start (branching travels along such lines and turns rings).
        self.line, self.restitch = None, None
        self.trim_after, self.lockable, self.puff = trim_after, lockable, puff
        # Placement: the outline sewn on the fabric just before the stop for foam.
        self.placement = placement
        # The area this block covers (fills); branching travels inside such areas.
        self.region = None
        # Open fills (gradient) leave fabric showing: travel across them would show.
        self.open = False
        # The machine stops before this block (appliqué: lay the fabric, then trim it).
        self.stop_before = False


def _satin_area(shape, spacing, pull, min_len, walk=True, columns=None, puff=False, join=True, pull_percent=0.0):
    """Narrow or small areas as satin columns along their centre lines (the way
    small shapes and lettering are digitized), joined by inside travel. Flat
    columns take underlay and spacing from their width (automatic)."""
    from .satin_font import area_columns
    runs = []
    for a, b, closed, width in (columns if columns is not None else area_columns(shape)):
        a, b = list(a), list(b)
        try:
            points = satin([(a, closed), (b, closed)], spacing, pull, indexed=len(a) == len(b), puff=puff,
                           outline=shape if puff else None, underlay='auto' if walk else None,
                           auto_space=not puff, pull_percent=pull_percent, split=0.0 if puff else SPLIT_MM,
                           shorten=not puff)
        except ValueError:
            continue
        if len(points) >= 2:
            runs.append(points)
    # Column ends are pulled a little past the outline (pull compensation): travel between
    # columns may start there, so its zone allows that pull (still inside the sewn band).
    zone = shape.buffer(max(0.0, float(pull) if not isinstance(pull, (list, tuple)) else max(pull))+.1) if join else shape
    return (join_runs(runs, zone, 1.5) if join else runs) if runs else []


# 3D puff: satin over foam. Columns must be about as wide as the foam is thick,
# or the foam leans and pokes out of the sides; and narrow enough that one
# stitch crosses them within the 7 mm machine limit.
PUFF_MAX_MM = 6.0


def puff_min_mm(foam_mm):
    """Narrowest column that holds foam of this thickness: 2 mm for 2 mm foam, 3 mm for 3 mm."""
    return max(2.0, min(3.0, float(foam_mm)))


def puff_outline(shape):
    """The rings of an area: placed before the foam, perforated after it."""
    rings = []
    for polygon in getattr(shape, 'geoms', [shape]):
        rings += [list(polygon.exterior.coords)] + [list(r.coords) for r in polygon.interiors]
    return [ring for ring in rings if len(ring) >= 3]


def _starting_near(ring, point):
    ring = list(ring[:-1]) if ring[0] == ring[-1] else list(ring)
    here = min(range(len(ring)), key=lambda i: math.dist(ring[i], point))
    return ring[here:] + ring[:here+1]


def _puff_area(shape, spacing, pull, min_len, foam_mm=3.0):
    """First a 1 mm running stitch around the shape tacks the foam down and
    perforates it so the rest tears away; then each column with its own
    tack-down walk, end caps, zigzag underlay and dense satin (stitch_satin).
    Returns None when the shape cannot puff."""
    from .satin_font import area_columns
    columns = area_columns(shape)
    widths = [2*w for *_, w in columns]
    if not columns or max(widths) > PUFF_MAX_MM or max(widths) < puff_min_mm(foam_mm):
        return None
    runs = _satin_area(shape, spacing, pull, min_len, walk=False, columns=columns, puff=True, join=False)
    if not runs:
        return None
    rings = [running(_starting_near(ring, runs[0][0]), 1.0, .05) for ring in puff_outline(shape)]
    return join_runs(rings + runs, shape, 1.5)


def _element_blocks(node, paths, style, scale, index, min_len, start=None, lines_from=None):
    """start: where the needle is (the last stitch so far); fills begin at their nearest corner.
    lines_from: the same, for running lines (with branching): nearest first, rings begin nearest."""
    stroke = sg.colour(style.get('stroke'))
    fill = sg.colour(style.get('fill', '#000000')) if 'fill' in style or sg.local(node.tag) != 'line' else None
    mm = [([(x*scale, y*scale) for x, y in pts], closed) for pts, closed in paths]
    if not mm:
        return []
    trim = _bool(node, 'trim_after')
    blocks = []
    def emit(colour, runs, puff=False, placement=False):
        runs = [r for r in runs if len(r) >= 2]
        for i, run in enumerate(runs):
            blocks.append(Block(colour, run, node, trim if i == len(runs)-1 else True, puff=puff,
                                placement=placement))
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
                runs = contour(shape, spacing, length, min_len, tolerance=tolerance,
                               underlay=_bool(node, 'fill_underlay'), angle=_float(node, 'angle', 0))
            elif method == 'wave_fill':
                runs = wave(shape, _float(node, 'angle', 0), spacing,
                            max(1.0, _float(node, 'max_stitch_length_mm', 3.0)), min_len,
                            underlay=_bool(node, 'fill_underlay', True),
                            amplitude=min(5.0, max(0.0, _float(node, 'wave_amplitude_mm', WAVE_AMPLITUDE_MM))),
                            wavelength=min(50.0, max(2.0, _float(node, 'wave_length_mm', WAVE_LENGTH_MM))))
            elif method == 'circular_fill':
                runs = spiral(shape, spacing, length, min_len, tolerance=tolerance)
            elif method == 'auto_satin':
                runs = _satin_area(shape, max(.2, _float(node, 'zigzag_spacing_mm', .4)),
                                   _float(node, 'pull_compensation_mm', 0), min_len,
                                   pull_percent=_float(node, 'pull_compensation_percent', 0)) or \
                    tatami(shape, _float(node, 'angle', 0), spacing, 3.0, 4, min_len)
            elif method == 'puff_satin':
                runs = _puff_area(shape, max(.18, _float(node, 'zigzag_spacing_mm', .22)),
                                  _float(node, 'pull_compensation_mm', .45), min_len,
                                  _float(node, 'puff_foam_mm', 3.0))
                if runs:
                    # The placement line shows where the foam goes; it is sewn on the
                    # fabric before the stop and covered by the satin afterwards.
                    inside = shape.buffer(-.3)
                    emit(fill, [running(ring, 2.5, .1) for ring in puff_outline(inside if not inside.is_empty else shape)],
                         placement=True)
                    emit(fill, runs, puff=True)
                    return blocks
                # Too narrow or too wide to puff: sewn flat, before the foam.
                runs = tatami(shape, _float(node, 'angle', 0), spacing, 3.0, 4, min_len)
            elif method == 'step_fill':
                runs = step_fill(shape, _float(node, 'angle', 0), spacing,
                                 max(1.0, _float(node, 'max_stitch_length_mm', 3.5)), min_len,
                                 underlay=_bool(node, 'fill_underlay', True))
            elif method == 'gradient_fill':
                runs = gradient(shape, _float(node, 'angle', 0), spacing,
                                max(spacing, _float(node, 'gradient_open_spacing_mm', 1.6)),
                                max(1.0, _float(node, 'max_stitch_length_mm', 3.0)), 4, min_len)
            elif method == 'radial_fill':
                runs = radial(shape, spacing, max(1.0, _float(node, 'max_stitch_length_mm', 3.0)), min_len)
                if runs is None:
                    # The rays can't reach around this shape: plain tatami instead.
                    runs = tatami(shape, _float(node, 'angle', 0), spacing, 3.0, 4, min_len)
            elif method == 'applique':
                cover = min(6.0, max(1.5, _float(node, 'applique_cover_mm', 3.0)))
                for runs, stop in _applique(shape, cover):
                    first = len(blocks)
                    emit(fill, runs)
                    if len(blocks) > first:
                        blocks[first].stop_before = stop
                runs = []
            elif method == 'meander_fill':
                cell = max(.6, _float(node, 'meander_scale_percent', 100)/100*10)
                stitch = _attr(node, 'stipple_stitch', 'run')
                runs = meander(shape, cell, length, min_len, _seed(node, index), tolerance=tolerance,
                               stitch=stitch if stitch in STIPPLE_STITCHES else 'run')
            else:
                underlay = _bool(node, 'fill_underlay', True)
                runs = tatami(shape, _float(node, 'angle', 0), spacing,
                              max(1.0, _float(node, 'max_stitch_length_mm', 3.0)),
                              max(1, int(_float(node, 'staggers', 4))), min_len,
                              underlay=underlay,
                              underlay_angle=(float(_attr(node, 'fill_underlay_angle')) if _attr(node, 'fill_underlay_angle') not in (None, '') else None),
                              underlay_spacing=(_float(node, 'fill_underlay_row_spacing_mm', 0) or None),
                              underlay_inset=_float(node, 'fill_underlay_inset_mm', .3),
                              underlay_max_len=max(1.0, _float(node, 'fill_underlay_max_stitch_length_mm', 3.0)),
                              start=start)
            emit(fill, runs)
        for block in blocks:
            block.region = shape
            block.open = _attr(node, 'fill_method') == 'gradient_fill'
    if stroke:
        if satin_column and len(mm) >= 2:
            pull = [float(v) for v in str(_attr(node, 'pull_compensation_mm', '0')).split() if v] or [0.0]
            points = satin(mm, max(.1, _float(node, 'zigzag_spacing_mm', .4)), pull if len(pull) > 1 else pull[0],
                           center_walk=_bool(node, 'center_walk_underlay'),
                           contour_underlay=_bool(node, 'contour_underlay'),
                           zigzag_underlay='double' if _attr(node, 'zigzag_underlay') == 'double' else _bool(node, 'zigzag_underlay'),
                           walk_repeats=max(1, int(_float(node, 'center_walk_underlay_repeats', 2))),
                           indexed=_attr(node, 'satin_pairs') == 'indexed', puff=_bool(node, 'puff'),
                           caps=str(_attr(node, 'puff_caps', 'start end')).split(),
                           underlay=_attr(node, 'satin_underlay'), auto_space=_bool(node, 'satin_auto_spacing'),
                           pull_percent=_float(node, 'pull_compensation_percent', 0),
                           split=0.0 if _bool(node, 'puff') else max(0.0, _float(node, 'satin_split_mm', SPLIT_MM)),
                           shorten=_bool(node, 'satin_shortening') and not _bool(node, 'puff'))
            emit(stroke, [points], puff=_bool(node, 'puff'))
        else:
            length = max(.3, _float(node, 'running_stitch_length_mm', 2.5))
            tolerance = max(0.0, _float(node, 'running_stitch_tolerance_mm', .2))
            repeats = int(_float(node, 'bean_stitch_repeats', 0))
            # Fragments that meet become one line; then sew nearest-first.
            runs = order_runs(chain([pts for pts, _ in mm])) if lines_from is None else \
                _begin_near(chain([pts for pts, _ in mm]), lines_from)
            area = _attr(node, 'travel_area')
            if area:
                region = fill_shape([([(x*scale, y*scale) for x, y in pts], True)
                                     for pts, _ in sg.parse_path(area)], 'evenodd')
                if not region.is_empty:
                    runs = join_runs(runs, region, length)
            outline = _attr(node, 'outline_style')
            if outline in OUTLINE_STYLES:
                runs = [_outline(run, outline, node, length) for run in runs if len(run) >= 2]
                emit(stroke, runs, puff=_bool(node, 'puff'), placement=_bool(node, 'puff_placement'))
            else:
                def restitch(run):
                    return bean(running(run, length, tolerance), repeats)
                lines = [(run, sewn) for run, sewn in ((run, restitch(run)) for run in runs) if len(sewn) >= 2]
                first = len(blocks)
                emit(stroke, [sewn for _, sewn in lines], puff=_bool(node, 'puff'),
                     placement=_bool(node, 'puff_placement'))
                for block, (run, _) in zip(blocks[first:], lines):
                    block.line, block.restitch = run, restitch
    return blocks


def _applique(shape, cover):
    """Appliqué, sewn in three parts as is usual: a placement run on the edge
    (where to lay the fabric), then after a stop an open zigzag tack-down just
    inside the edge, then after a stop for trimming a satin cover `cover` mm wide
    centred on the cut edge. The inside stays unstitched: the fabric shows.
    Returns [(runs, stop_before)]."""
    from .borders import satin_rails
    if shape.buffer(-cover).is_empty:
        raise ValueError(f'An appliqué piece must be at least {2*cover:g} mm across. Use a larger area or a fill.')
    rings = [list(r.coords) for poly in polygons(shape) for r in (poly.exterior, *poly.interiors)]
    placement = [running(ring, 2.5, .05) for ring in rings]
    inner = shape.buffer(-.8)
    tack = [zigzag_outline(list(r.coords), 1.0, 1.2)
            for poly in polygons(inner) for r in (poly.exterior, *poly.interiors)]
    covers = []
    for ring in rings:
        simple = list(LineString(ring).simplify(cover*.15).coords)
        try:
            for a, b in satin_rails(simple, cover/2):
                covers.append(satin([([tuple(p) for p in a], False), ([tuple(p) for p in b], False)], .4, 0,
                                    split=SPLIT_MM))
        except ValueError:
            # Corners too sharp for matched rails: a dense zigzag of the same width.
            covers.append(zigzag_outline(ring, .8, cover))
    return [(placement, False), (tack, True), (covers, True)]


def applique_coverage(rings_px, scale, shape_px, cover=3.0):
    """Where an appliqué piece really sews (placement, tack-down and the satin cover,
    whose mitred corners reach past the edge), as a pixel mask for the release check."""
    import cv2
    import numpy as np
    from shapely.geometry import Polygon
    polygon = Polygon(np.asarray(rings_px[0], float)*scale, [np.asarray(r, float)*scale for r in rings_px[1:]]).buffer(0)
    band = np.zeros(shape_px, np.uint8)
    for runs, _ in _applique(polygon, cover):
        for run in runs:
            if len(run) >= 2:
                cv2.polylines(band, [np.rint(np.asarray(run)/scale).astype(np.int32)], False, 1, thickness=3)
    # Satin fills the space between its legs: close the gaps between neighbouring stitches.
    return cv2.morphologyEx(band, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)).astype(bool)


OUTLINE_STYLES = ('backstitch', 'stemstitch', 'blanket', 'zigzag', 'motif', 'couching', 'blackwork', 'handstitch',
                  'candlewick')


def _outline(run, style, node, length):
    """Decorative outline stitch along one line (stitch_paths)."""
    width = min(6.0, max(.5, _float(node, 'outline_width_mm', 2.0 if style != 'stemstitch' else 1.2)))
    if style == 'couching':
        # Ties shorter than about 1 mm would fall under the minimum stitch on each side.
        return couching(run, max(1.0, length), max(1.0, width), max(1.0, _float(node, 'outline_spacing_mm', 3.0)))
    if style == 'blackwork':
        return blackwork_run(run, max(1.0, length))
    if style == 'handstitch':
        return hand_stitch(run, max(1.5, length))
    if style == 'candlewick':
        # Knots wider than 2.5 mm stop reading as knots; width is their size.
        return candlewick(run, max(1.0, length), min(2.5, width), max(2.0, _float(node, 'outline_spacing_mm', 3.0)))
    if style == 'backstitch':
        return backstitch(run, length)
    if style == 'stemstitch':
        # A shallow slant reads as a twisted rope; a steep one as saw teeth.
        return stemstitch(run, max(1.0, length), min(width, .4*max(1.0, length)))
    spacing = max(.4, _float(node, 'outline_spacing_mm', 2.0 if style in ('blanket', 'motif') else .8))
    if style == 'zigzag':
        return zigzag_outline(run, spacing, width)
    closed = len(run) > 3 and math.dist(run[0], run[-1]) < 1e-6
    if style == 'motif':
        # One-sided motifs (triangles, scallops) stand outside a closed shape, off its fill.
        motif = _attr(node, 'outline_motif', 'diamond')
        side = -inward_side(run[:-1]) if closed else 1
        return motif_run(run, max(1.0, length), width, spacing, motif if motif in MOTIFS else 'diamond', side)
    # Spikes point into a closed shape (or out of it with blanket_side="outside").
    side = inward_side(run[:-1]) if closed else 1
    return blanket(run, spacing, width, -side if _attr(node, 'blanket_side') == 'outside' else side)


BRANCH_MAX_MM = 25.0   # longest travel run that replaces a cut
LINE_BRANCH_MM = 12.0  # longest travel along sewn lines (outlines) that replaces a cut
LINE_TOUCH_MM = .35    # lines this close touch: travel may step from one to the other


def _closed(run):
    return len(run) > 3 and math.dist(run[0], run[-1]) < 1e-6


def _ring_from(run, point):
    """A closed line turned to begin (and end) at its point nearest `point`."""
    from shapely.geometry import Point
    from shapely.ops import substring
    ring = LineString(run)
    at = ring.project(Point(point))
    if not 1e-6 < at < ring.length-1e-6:
        return run
    head, tail = substring(ring, at, ring.length).coords, substring(ring, 0, at).coords
    return [tuple(p) for p in head]+[tuple(p) for p in tail][1:]


def _begin_near(runs, position):
    """Running lines of one element, nearest first from the needle; a closed line (an
    outline ring) begins at its point nearest the needle."""
    out = []
    for run in order_runs(runs, position):
        if position is not None and _closed(run):
            run = _ring_from(run, position)
        out.append(run)
        position = run[-1]
    return out


class _Lines:
    """The running lines of one thread as a graph (a point every 0.5 mm, joined where
    lines touch or cross), for travel that only goes over lines of that thread."""

    def __init__(self, blocks):
        from scipy.spatial import cKDTree
        self.points, self.owner, self.graph = [], [], {}
        for block in blocks:
            dense = split_long(dedupe(block.line), .5)
            base = len(self.points)
            self.points.extend(dense)
            self.owner.extend([id(block)]*len(dense))
            for k in range(base, base+len(dense)-1):
                self._edge(k, k+1)
        self.tree = cKDTree(self.points) if self.points else None
        if self.tree is not None:
            for i, j in self.tree.query_pairs(LINE_TOUCH_MM):
                self._edge(i, j)

    def _edge(self, i, j):
        d = math.dist(self.points[i], self.points[j])
        self.graph.setdefault(i, []).append((j, d))
        self.graph.setdefault(j, []).append((i, d))

    def route(self, a, block, limit, following=None):
        """Shortest way from a along the lines onto `block`'s line (anywhere on a ring,
        else one of its ends), at most `limit` long: [a, ..., entry point], or None.
        A ring ends where it begins: with a `following` line, its entry is also chosen
        near that line, so the thread can travel on to it afterwards."""
        import heapq
        from shapely.geometry import Point
        if self.tree is None:
            return None
        da, i = self.tree.query(a)
        if da > LINE_TOUCH_MM:
            return None
        closed = _closed(block.line)
        ends = None if closed else {tuple(block.line[0]), tuple(block.line[-1])}
        def entry(k):
            return self.owner[k] == id(block) and \
                (ends is None or min(math.dist(self.points[k], e) for e in ends) < 1e-6)
        best, previous, queue = {i: 0.0}, {}, [(0.0, i)]
        while queue:
            cost, k = heapq.heappop(queue)
            if cost > best[k]:
                continue
            if entry(k) and (not closed or following is None):
                break
            for other, d in self.graph.get(k, ()):
                total = cost+d
                if total <= limit and total < best.get(other, math.inf):
                    best[other] = total; previous[other] = k
                    heapq.heappush(queue, (total, other))
        reached = [k for k in best if entry(k)]
        if not reached:
            return None
        if closed and following is not None:
            onward = LineString(following.line)
            k = min(reached, key=lambda n: best[n]+2*onward.distance(Point(self.points[n])))
        else:
            k = min(reached, key=best.get)
        path = [k]
        while path[-1] != i:
            path.append(previous[path[-1]])
        return [a, *(self.points[n] for n in reversed(path))]


def _line_toward(block, following):
    """A ring sewn after a cut begins where it comes nearest the next line of its thread,
    so the thread can travel straight on from where the ring ends."""
    from shapely.ops import nearest_points
    point, _ = nearest_points(LineString(block.line), LineString(following.line))
    block.line = _ring_from(block.line, (point.x, point.y))
    block.points = block.restitch(block.line)


def _line_entry(block, point):
    """Begin `block`'s line at `point` (turning a ring, or reversing an open line)."""
    if _closed(block.line):
        block.line = _ring_from(block.line, point)
    elif math.dist(block.line[-1], point) < math.dist(block.line[0], point):
        block.line = block.line[::-1]
    else:
        return
    block.points = block.restitch(block.line)


def _branch(blocks):
    """Branching, as professional software does it: between two parts in the same
    thread, travel with short running stitches inside the area just sewn or under
    areas sewn later, instead of cutting the thread. Same-colour travel on its own
    fill barely shows; travel under later areas is covered. Travel never leaves
    sewn areas, so the release gate still sees no stitch over empty fabric.
    Running lines (outlines, line art) travel along the lines of their own thread
    instead: back over lines just sewn or along lines sewn over next."""
    from shapely.geometry import LineString
    from shapely.prepared import prep
    from shapely.ops import unary_union
    from .stitch_paths import Travel
    prepared = {}
    def fast(region):
        key = id(region)
        if key not in prepared:
            prepared[key] = prep(region)
        return prepared[key]
    networks = {}
    def lines(i):
        # The lines of the run of same-thread blocks around block i.
        def same(k):
            return blocks[k].colour == blocks[i].colour and blocks[k].puff == blocks[i].puff \
                and blocks[k].placement == blocks[i].placement
        first = i
        while first > 0 and same(first-1):
            first -= 1
        if first not in networks:
            last = i
            while last+1 < len(blocks) and same(last+1):
                last += 1
            networks[first] = _Lines([k for k in blocks[first:last+1] if k.line])
        return networks[first]
    def thread(k):
        return blocks[k].colour == blocks[k+1].colour and blocks[k].puff == blocks[k+1].puff \
            and blocks[k].placement == blocks[k+1].placement and not blocks[k+1].stop_before
    for i in range(len(blocks)-1):
        prev, nxt = blocks[i], blocks[i+1]
        if prev.line and nxt.line and thread(i):
            if _closed(prev.line) and (i == 0 or blocks[i-1].trim_after or not thread(i-1)):
                # A ring sewn after a cut may begin anywhere: next to the next line.
                _line_toward(prev, nxt)
            if prev.trim_after:
                after = blocks[i+2] if i+2 < len(blocks) and blocks[i+2].line and thread(i+1) else None
                route = lines(i).route(tuple(prev.points[-1]), nxt, LINE_BRANCH_MM, after)
                if route is not None:
                    _line_entry(nxt, route[-1])
                    nxt.points = [*running(route, 2.0, 0)[:-1], *nxt.points]
                    prev.trim_after = False
            continue
        if not prev.trim_after or not thread(i):
            continue
        a, b = tuple(prev.points[-1]), tuple(nxt.points[0])
        if prev.region is None or nxt.region is None or prev.open or nxt.open:
            continue
        if math.dist(a, b) > BRANCH_MAX_MM:
            continue
        route = None
        if math.dist(a, b) > 1e-6:
            # Straight: covered by the area just sewn plus areas sewn later along the line.
            line = LineString([a, b])
            strip = line.buffer(.5)
            hits = [prev.region] + [k.region for k in blocks[i+1:]
                                    if k.region is not None and not k.open and fast(k.region).intersects(line)]
            cover = unary_union([r.intersection(strip) for r in {id(r): r for r in hits}.values()])
            if cover.buffer(.02).contains(line):
                route = [a, b]
            elif prev.region.distance(nxt.region) < .05:
                # Touching parts: travel around inside the two of them.
                route = Travel(unary_union([prev.region, nxt.region])).route(a, b, direct_mm=0)
                if route is not None and path_length(route) > 1.6*math.dist(a, b)+5:
                    route = None
        else:
            route = [a, b]
        if route is None:
            continue
        travel = running(route, 2.0, 0)
        nxt.points = [*travel[:-1], *nxt.points]
        prev.trim_after = False


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
    branching = False
    for node in root.iter():
        if sg.local(node.tag) == 'branching' and node.text:
            branching = node.text.strip() == 'true'
        if sg.local(node.tag) == 'collapse_len_mm' and node.text:
            try:
                collapse = float(node.text)
            except ValueError:
                pass
    blocks = []
    for index, (node, paths, style, _) in enumerate(sg.elements(root, tolerance=.02/scale)):
        min_len = _float(node, 'min_stitch_length_mm', document_min if document_min is not None else .45)
        # Auto start: each fill begins near where the previous part ended (shorter travel).
        needle = tuple(blocks[-1].points[-1]) if blocks else None
        made = _element_blocks(node, paths, style, scale, index, min_len, needle,
                               needle if branching else None)
        for block in made:
            block.min_len = min_len
            # Over foam, tie-offs are six 1 mm stitches: short locks pull out of the foam.
            lock_mm, pattern = (1.0, PUFF_LOCK) if block.puff else (.6, DEFAULT_LOCK)
            block.start_lock = _lock_positions(node, 'start', lock_mm, pattern)
            block.end_lock = _lock_positions(node, 'end', lock_mm, pattern)
        blocks.extend(made)
    if not blocks:
        raise ValueError('The design has no stitchable objects.')
    # Flat parts, then the foam placement lines, then (after the stop) everything over foam.
    blocks = [b for b in blocks if not b.puff and not b.placement] + \
        [b for b in blocks if b.placement and not b.puff] + [b for b in blocks if b.puff]
    if branching:
        _branch(blocks)
    origin = sg.origin(root)
    if origin is not None:
        origin = (origin[0]*scale, origin[1]*scale)
    else:
        xs = [p[0] for b in blocks for p in b.points]; ys = [p[1] for b in blocks for p in b.points]
        origin = ((min(xs)+max(xs))/2, (min(ys)+max(ys))/2)
    return assemble(blocks, origin, collapse)


def assemble(blocks, origin, collapse):
    threads, stitches, puff_threads = [], [], []
    def put(point, command):
        stitches.append([round((point[0]-origin[0])*10, 3), round((point[1]-origin[1])*10, 3), command])
    needle = None; colour = None; previous = None; over_foam = False
    for i, block in enumerate(blocks):
        points = enforce_min(block.points, block.min_len)
        if len(points) < 2:
            continue
        follower = next((b for b in blocks[i+1:] if len(b.points) >= 2), None)
        # The first puff block always changes thread, even to the same colour:
        # the machine stops so the foam can be laid on the fabric.
        # A stop is a change to the same thread (PES reads it back as STOP).
        change = colour != block.colour or block.puff != over_foam or (block.stop_before and previous is not None)
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
            colour, over_foam = block.colour, block.puff
            if block.puff:
                puff_threads.append(len(threads)-1)
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
            'stitches': _tidy(stitches, min(b.min_len for b in blocks)),
            'extras': {'puff_threads': puff_threads} if puff_threads else {}}


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
