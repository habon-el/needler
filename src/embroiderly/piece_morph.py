"""Morph a piece's outline: pinch, punch, twirl or wave, with a strength.

The outline is distorted point by point in millimetres on the hoop, around the selection's centre
(several pieces morph together, as one shape). Edges get points at most MAX_STEP_MM apart first,
so straight sides bend instead of staying straight between their corners. Every morph moves each
point to one place and never folds the outline over itself, so holes stay holes. The result is
stored like a smoothed piece (piece_weld.replace): it keeps the piece's style, direction, holes
and outline, and the stitches are made again from it.
"""
import math

import numpy as np

KINDS = ('pinch', 'punch', 'twirl', 'wave')
STRENGTH = (10, 100)   # percent
PINCH = 1.5            # at full strength the distance to the centre is raised to the power 1+PINCH
TWIRL_DEG = 180        # turn at the centre at full strength; it fades to the edge
TWIRL_REACH = 1.25     # the twirl fades out this far beyond the farthest point, so corners turn too
WAVES = 2              # whole waves across the selection
WAVE_HEIGHT = .2       # wave height at full strength, as a share of the selection's height
MAX_STEP_MM = .5
MIN_STEP_MM = .05


def run(updated, report, selected, value):
    from .piece_layout import bounds, edits
    from .piece_weld import ALREADY_MM, replace, shape_of
    if any(p.get('line') for p in selected):
        raise ValueError('A stitched line cannot be morphed. Choose filled parts.')
    if not isinstance(value, dict) or set(value) != {'kind', 'strength'} or value['kind'] not in KINDS:
        raise ValueError('Choose Pinch, Punch, Twirl or Wave.')
    strength = value['strength']
    if type(strength) not in (int, float) or not math.isfinite(strength) or not STRENGTH[0] <= strength <= STRENGTH[1]:
        raise ValueError(f'Morph strength must be {STRENGTH[0]}–{STRENGTH[1]}%.')
    box = bounds([r for p in selected for r in p['rings_mm']])
    shapes = [shape_of(p) for p in selected]
    morph = warp(value['kind'], strength/100, box, shapes)
    for p, shape in zip(selected, shapes):
        result = morphed(shape, morph, box)
        if result.hausdorff_distance(shape) < ALREADY_MM:
            raise ValueError(f"{p['name']} is too small or too round to {value['kind']}. Choose a stronger morph or another kind.")
        replace(updated, report, p, result, f"morph:{value['kind']}:{strength:g}:{p['id']}", p['name'])
    edits(updated)
    return updated


def warp(kind, s, box, shapes):
    """The point mapping (n×2 array in, n×2 out) for this morph over the selection's box."""
    left, top, right, bottom = box
    centre = np.array([(left+right)/2, (top+bottom)/2])
    reach = max(float(np.linalg.norm(np.asarray(ring.coords)-centre, axis=1).max())
                for shape in shapes for ring in (shape.exterior, *shape.interiors))
    if kind == 'wave':
        height = WAVE_HEIGHT*s*(bottom-top)
        width = max(right-left, 1e-6)
        return lambda p: p+np.c_[np.zeros(len(p)), height/2*np.sin(2*math.pi*WAVES*(p[:, 0]-left)/width)]

    def radial(p):
        d = p-centre
        r = np.hypot(d[:, 0], d[:, 1])
        u = np.clip(r/max(reach, 1e-6), 0, 1)
        if kind == 'twirl':
            # Turn most at the centre, fading to nothing just beyond the farthest point.
            turn = np.radians(TWIRL_DEG*s)*np.clip(1-r/(TWIRL_REACH*reach), 0, 1)
            c, n = np.cos(turn), np.sin(turn)
            return centre+np.c_[d[:, 0]*c-d[:, 1]*n, d[:, 0]*n+d[:, 1]*c]
        # Pinch draws the nearer points in more than the far ones (sides cave in, corners stay);
        # punch pushes them out (sides bulge towards a circle).
        power = 1+PINCH*s if kind == 'pinch' else 1/(1+PINCH*s)
        k = np.power(np.maximum(u, 1e-9), power-1)
        return centre+d*k[:, None]
    return radial


def densified(ring, step):
    """The closed ring with extra points so no edge is longer than step."""
    points = np.asarray(ring.coords[:-1], float)
    out = []
    for a, b in zip(points, np.roll(points, -1, axis=0)):
        n = max(1, int(math.ceil(np.linalg.norm(b-a)/step)))
        out.append(a+np.outer(np.arange(n)/n, b-a))
    return np.concatenate(out)


def morphed(shape, morph, box):
    from shapely.geometry import Polygon
    left, top, right, bottom = box
    step = min(MAX_STEP_MM, max(MIN_STEP_MM, max(right-left, bottom-top)/80))
    rings = [morph(densified(r, step)) for r in (shape.exterior, *shape.interiors)]
    result = Polygon(rings[0], [r for r in rings[1:] if len(r) >= 3]).buffer(0)
    result = max(getattr(result, 'geoms', [result]), key=lambda g: g.area)
    if result.is_empty or result.area < 1.0:
        raise ValueError('The morphed piece is too small to stitch. Choose a gentler morph.')
    return result.simplify(.05, preserve_topology=True)
