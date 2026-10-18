"""Native satin columns from two rails (optional rungs) and their underlays.

Rails are matched by arc length between rungs, so stitches stay perpendicular
where the author placed rungs. Pull compensation widens each side outward.
Units: millimetres. No stitch is placed outside the rails except compensation.
"""
import math
from itertools import combinations
from shapely.geometry import LineString, Point
from .stitch_paths import dedupe, lerp, path_length, resample, running


def _closed(points):
    return len(points) > 2 and math.dist(points[0], points[-1]) < 1e-6


def choose_rails(subpaths):
    paths = [dedupe(p) for p, _ in subpaths]
    paths = [p for p in paths if len(p) >= 2]
    if len(paths) < 2:
        raise ValueError('A satin column needs two rails.')
    if len(paths) == 2:
        return paths[0], paths[1], []
    lines = [LineString(p) for p in paths]
    candidates = []
    for a, b in combinations(range(len(paths)), 2):
        others = [r for r in range(len(paths)) if r not in (a, b)]
        if all(lines[r].distance(lines[a]) < .05 and lines[r].distance(lines[b]) < .05 for r in others):
            candidates.append((lines[a].length+lines[b].length, a, b, others))
    if candidates:
        _, a, b, others = max(candidates)
    else:
        order = sorted(range(len(paths)), key=lambda i: -lines[i].length)
        a, b, others = order[0], order[1], []
    return paths[a], paths[b], [paths[r] for r in others]


def _align(a, b):
    if _closed(a) and _closed(b):
        ring_b = b[:-1]
        j = min(range(len(ring_b)), key=lambda i: math.dist(ring_b[i], a[0]))
        ring_b = ring_b[j:]+ring_b[:j]
        def signed(points):
            return sum(p[0]*q[1]-q[0]*p[1] for p, q in zip(points, points[1:]+points[:1]))
        if (signed(a[:-1]) > 0) != (signed(ring_b) > 0):
            ring_b = [ring_b[0]]+ring_b[1:][::-1]
        return a, ring_b+[ring_b[0]]
    if math.dist(a[0], b[0])+math.dist(a[-1], b[-1]) > math.dist(a[0], b[-1])+math.dist(a[-1], b[0]):
        b = b[::-1]
    return a, b


def _fractions(rail, points):
    """Arc-length fraction of each point; exact rail vertices first, since a
    projection is ambiguous where a rail doubles back on a tight curve."""
    line = LineString(rail)
    total = line.length or 1.0
    walked = [0.0]
    for p, q in zip(rail, rail[1:]):
        walked.append(walked[-1]+math.dist(p, q))
    out = []
    for point in points:
        exact = next((walked[i] for i, v in enumerate(rail) if math.dist(v, point) < 1e-6), None)
        out.append((exact if exact is not None else line.project(Point(point)))/total)
    return out


def pairs(a, b, rungs, spacing):
    """Matched (a_i, b_i) pairs about `spacing` apart along the column."""
    a, b = _align(a, b)
    length = (path_length(a)+path_length(b))/2
    breaks = []
    ra, rb = LineString(a), LineString(b)
    for rung in rungs:
        ends = (rung[0], rung[-1])
        # The rung's own end points usually lie exactly on the rails.
        if min(math.dist(ends[0], v) for v in b) < min(math.dist(ends[0], v) for v in a):
            ends = ends[::-1]
        on_a = min(math.dist(ends[0], v) for v in a) < 1e-6
        on_b = min(math.dist(ends[1], v) for v in b) < 1e-6
        if on_a and on_b:
            pa, pb = ends
        else:
            line = LineString(rung)
            ia, ib = line.intersection(ra), line.intersection(rb)
            qa = ia if ia.geom_type == 'Point' else ra.interpolate(ra.project(line.centroid))
            qb = ib if ib.geom_type == 'Point' else rb.interpolate(rb.project(line.centroid))
            pa, pb = (qa.x, qa.y), (qb.x, qb.y)
        fa, fb = _fractions(a, [pa])[0], _fractions(b, [pb])[0]
        if 0 < fa < 1 and 0 < fb < 1:
            breaks.append((fa, fb))
    knots = [(0.0, 0.0)]
    for k in sorted(set(breaks)):
        if k[0] > knots[-1][0] and k[1] > knots[-1][1]:
            knots.append(k)
    knots.append((1.0, 1.0))
    count = max(2, int(math.ceil(length/spacing))+1)
    line_a, line_b = LineString(a), LineString(b)
    out = []
    for i in range(count):
        t = i/(count-1)
        # Piecewise-linear mapping between rail fractions through the rungs.
        for (a0, b0), (a1, b1) in zip(knots, knots[1:]):
            if t <= a1 or a1 == 1.0:
                s = 0 if a1 == a0 else (t-a0)/(a1-a0)
                out.append((_at(line_a, t), _at(line_b, b0+(b1-b0)*s)))
                break
    return out


def _at(line, fraction):
    p = line.interpolate(max(0.0, min(1.0, fraction)), normalized=True)
    return (p.x, p.y)


def compensate(pairs_, pull):
    if not pull:
        return pairs_
    left, right = (pull, pull) if not isinstance(pull, (list, tuple)) else (pull[0], pull[-1])
    out = []
    for a, b in pairs_:
        d = math.dist(a, b)
        if d < 1e-9:
            out.append((a, b)); continue
        ux, uy = (a[0]-b[0])/d, (a[1]-b[1])/d
        out.append(((a[0]+ux*left, a[1]+uy*left), (b[0]-ux*right, b[1]-uy*right)))
    return out


def indexed_pairs(a, b, spacing):
    """Rails authored as matched cross-sections: pair vertex i with vertex i and
    subdivide between neighbours, so stitches follow the author's sections."""
    middle = [lerp(p, q, .5) for p, q in zip(a, b)]
    walked = [0.0]
    for m0, m1 in zip(middle, middle[1:]):
        walked.append(walked[-1]+math.dist(m0, m1))
    total = walked[-1]
    count = max(2, int(math.ceil(total/spacing))+1)
    out, i = [], 0
    for k in range(count):
        target = total*k/(count-1)
        while i < len(a)-2 and walked[i+1] < target:
            i += 1
        span = walked[i+1]-walked[i]
        t = 0.0 if span <= 0 else min(1.0, (target-walked[i])/span)
        out.append((lerp(a[i], a[i+1], t), lerp(b[i], b[i+1], t)))
    return out


def satin(subpaths, spacing=0.4, pull=0.0, center_walk=False, contour_underlay=False,
          zigzag_underlay=False, underlay_length=1.5, walk_repeats=2, indexed=False):
    if indexed and len(subpaths) >= 2 and len(subpaths[0][0]) == len(subpaths[1][0]) >= 2:
        a, b, rungs = [tuple(p) for p in subpaths[0][0]], [tuple(p) for p in subpaths[1][0]], []
        matched = indexed_pairs(a, b, spacing)
        pairs_at = lambda step: indexed_pairs(a, b, step)
    else:
        a, b, rungs = choose_rails(subpaths)
        matched = pairs(a, b, rungs, spacing)
        pairs_at = lambda step: pairs(a, b, rungs, step)
    points = []
    if center_walk:
        middle = [lerp(p, q, .5) for p, q in pairs_at(underlay_length)]
        walk = running(middle, underlay_length, 0)
        for repeat in range(walk_repeats):
            leg = walk if repeat % 2 == 0 else walk[::-1]
            points.extend(leg if not points else leg[1:])
    if contour_underlay:
        inset = []
        for p, q in pairs_at(underlay_length):
            d = math.dist(p, q)
            k = min(.2, d/4)/d if d > 1e-9 else 0
            inset.append((lerp(p, q, k), lerp(q, p, k)))
        side = running([p for p, _ in inset], underlay_length, 0)+running([q for _, q in inset][::-1], underlay_length, 0)
        points.extend(side)
    if zigzag_underlay:
        sparse = pairs_at(3.0)
        zig = []
        for i, (p, q) in enumerate(sparse):
            zig.extend([lerp(p, q, .2), lerp(q, p, .2)] if i % 2 == 0 else [lerp(q, p, .2), lerp(p, q, .2)])
        points.extend(zig)
    # Satin starts from whichever end the underlay finished at.
    final = compensate(matched, pull)
    if points and math.dist(points[-1], final[-1][0]) < math.dist(points[-1], final[0][0]):
        final = final[::-1]
    for p, q in final:
        points.extend((p, q))
    return points


def length_of_column(subpaths):
    a, b, _ = choose_rails(subpaths)
    return (path_length(a)+path_length(b))/2
