"""Weld pieces of one thread into one, and smooth a piece's outline.

Both replace the selected pieces by a new part stored like a knife cut ({'source', 'rings',
'matrix', 'rotation', 'name'}); the outline is kept in the source piece's picture pixels, before
its transform, so it moves, turns and sizes like any other part. A piece found in the picture (or
a drawn shape) is marked 'cut'; a copy or cut part is removed. The new part keeps the style,
stitch direction, hole choice and outline of the piece it replaces (for weld: the first picked).
Geometry is measured in millimetres on the hoop (rings_mm), so tolerances do not depend on the
picture's resolution.
"""
import hashlib
import math

import numpy as np

COMMANDS = ('weld', 'smooth')
TOUCH_MM = .2          # pieces this close count as touching; the gap between them is closed
SMOOTH = {'light': (.15, 1., 1), 'more': (.35, 1.5, 2)}   # tolerance mm, tolerance in pixels, rounding passes
CORNER_DEG = 50        # a bend sharper than this is a corner and stays sharp
ALREADY_MM = .03       # an outline that moves less than this is already smooth
MIN_HOLE_MM2 = .1      # smaller holes left by a weld are slivers at the seam and are closed
PER_PIECE = ('region_styles', 'area_angles', 'area_holes', 'area_outlines')


def run(updated, report, selected, field, value):
    from .piece_layout import edits
    if any(p.get('line') for p in selected):
        raise ValueError('A stitched line cannot be welded or smoothed. Choose filled parts.')
    if field == 'weld':
        weld(updated, report, selected, value)
    else:
        smooth(updated, report, selected, value)
    edits(updated)
    return updated


def shape_of(p):
    from .region_stitches import polygon
    shape = polygon(p['rings_mm'], 1).buffer(0)
    return max(getattr(shape, 'geoms', [shape]), key=lambda g: g.area)


def weld(updated, report, selected, value):
    """Join 2+ touching pieces of one thread into one: the union of their outlines.
    selected is in the order picked; the first piece gives the style, name and place."""
    from shapely.ops import unary_union
    if value is not None:
        raise ValueError('Invalid weld.')
    if len(selected) < 2:
        raise ValueError('Select two or more pieces to weld.')
    if len({p['colour'].lower() for p in selected}) != 1:
        raise ValueError('These pieces use different threads. Only pieces of the same thread can be welded.')
    shapes = [shape_of(p) for p in selected]
    # Every piece must touch the ones joined so far (in any order), or there is nothing to weld.
    joined, rest = shapes[0], list(range(1, len(shapes)))
    while rest:
        near = [i for i in rest if joined.distance(shapes[i]) <= TOUCH_MM]
        if not near:
            raise ValueError('These pieces do not touch. Move them so they overlap or touch, then weld.')
        joined = unary_union([joined, *(shapes[i] for i in near)])
        rest = [i for i in rest if i not in near]
    if joined.geom_type != 'Polygon':
        # Close the hair-thin gap between pieces that touch; mitre joins keep the corners sharp.
        r = TOUCH_MM/2+.01
        joined = unary_union([s.buffer(r, join_style=2) for s in shapes]).buffer(-r, join_style=2)
    if joined.geom_type != 'Polygon':
        raise ValueError('These pieces do not join into one shape. Move them so they overlap, then weld.')
    from shapely.geometry import Polygon
    joined = Polygon(joined.exterior, [h for h in joined.interiors if Polygon(h).area >= MIN_HOLE_MM2])
    first = selected[0]
    replace(updated, report, first, joined, 'weld:'+':'.join(p['id'] for p in selected), first['name'])
    for p in selected[1:]:
        remove(updated, p['id'])


def smooth(updated, report, selected, value):
    """Remove pixel stair-steps and tiny wiggles; corners sharper than CORNER_DEG stay, and the
    area is kept. value: 'light' or 'more'."""
    if value not in SMOOTH:
        raise ValueError('Choose Light or More smoothing.')
    for p in selected:
        shape = shape_of(p)
        result = smoothed(shape, value, pixel_mm(report, updated, p))
        if result.hausdorff_distance(shape) < ALREADY_MM:
            raise ValueError(f"{p['name']} is already smooth.")
        replace(updated, report, p, result, f"smooth:{value}:{p['id']}", p['name'])


def pixel_mm(report, updated, p):
    from .piece_layout import IDENTITY, matrix
    m = matrix(updated['piece_edits'].get(p['id'], {}).get('matrix', IDENTITY))
    return report['scale']*math.sqrt(abs(np.linalg.det(m[:2, :2])))


def smoothed(shape, strength, pixel):
    """Douglas–Peucker removes steps and wiggles below the tolerance; then gentle bends are rounded
    (corner cutting) while sharp corners are kept; finally the shape is scaled back to its area."""
    from shapely import affinity
    from shapely.geometry import Polygon
    mm, px, passes = SMOOTH[strength]
    tolerance = max(mm, px*pixel)
    simple = shape.simplify(tolerance, preserve_topology=True)
    rings = [rounded(np.asarray(r.coords[:-1]), passes) for r in (simple.exterior, *simple.interiors)]
    result = Polygon(rings[0], [r for r in rings[1:] if len(r) >= 3]).buffer(0)
    result = max(getattr(result, 'geoms', [result]), key=lambda g: g.area)
    if result.is_empty or result.area < 1.0:
        raise ValueError('This piece is too small to smooth.')
    k = math.sqrt(shape.area/result.area)
    return affinity.scale(result, k, k, origin=result.centroid)


def rounded(points, passes):
    """Corner cutting (Chaikin) at bends gentler than CORNER_DEG; sharper corners are kept."""
    for _ in range(passes):
        if len(points) < 3:
            return points
        before, after = np.roll(points, 1, axis=0), np.roll(points, -1, axis=0)
        a, b = points-before, after-points
        turn = np.degrees(np.abs(np.arctan2(a[:, 0]*b[:, 1]-a[:, 1]*b[:, 0], (a*b).sum(axis=1))))
        out = []
        for i, point in enumerate(points):
            if turn[i] > CORNER_DEG:
                out.append(point)
            else:
                out += [.75*point+.25*before[i], .75*point+.25*after[i]]
        points = np.asarray(out)
    return points


def replace(updated, report, p, shape, seed, name):
    """Store shape (mm on the hoop) as a new part in p's place; p is cut (or removed, for a part)."""
    from .piece_layout import IDENTITY, matrix
    stored = updated.setdefault('piece_edits', {})
    item = stored.get(p['id'], {})
    inverse = np.linalg.inv(matrix(item.get('matrix', IDENTITY)))
    origin, scale = np.array(report['origin_mm']), report['scale']
    def to_source(ring):
        points = np.asarray(ring.coords[:-1], float)
        return ((np.c_[points, np.ones(len(points))] @ inverse.T)[:, :2]+origin)/scale
    from shapely.geometry import Polygon
    rings = [to_source(r) for r in (shape.exterior, *shape.interiors)]
    part = Polygon(rings[0], rings[1:]).simplify(.05)
    key = hashlib.sha256(seed.encode()).hexdigest()[:20]
    n = 0
    while key in stored:
        n += 1
        key = hashlib.sha256(f'{seed}:{n}'.encode()).hexdigest()[:20]
    stored[key] = {'source': item.get('source', p['id']),
                   'rings': [[[round(x, 2), round(y, 2)] for x, y in r.coords[:-1]] for r in (part.exterior, *part.interiors)],
                   'matrix': item.get('matrix', IDENTITY), 'rotation': item.get('rotation', 0), 'name': name[:100]}
    for field in PER_PIECE:
        if p['id'] in updated.get(field, {}):
            updated[field][key] = updated[field][p['id']]
    remove(updated, p['id'])


def remove(updated, key):
    """A copy or cut part goes; a piece from the picture (or a drawn shape) is marked cut."""
    stored = updated['piece_edits']
    if 'source' in stored.get(key, {}):
        del stored[key]
        for field in PER_PIECE:
            updated.get(field, {}).pop(key, None)
    else:
        stored.setdefault(key, {})['cut'] = True
