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


def compensate(pairs_, pull, percent=0.0):
    """Widen each stitch by `pull` mm per side, plus `percent` of its width
    shared between both sides (wide columns pull in more than narrow ones)."""
    if not pull and not percent:
        return pairs_
    left, right = (pull, pull) if not isinstance(pull, (list, tuple)) else (pull[0], pull[-1])
    out = []
    for a, b in pairs_:
        d = math.dist(a, b)
        if d < 1e-9:
            out.append((a, b)); continue
        extra = d*percent/200
        ux, uy = (a[0]-b[0])/d, (a[1]-b[1])/d
        out.append(((a[0]+ux*(left+extra), a[1]+uy*(left+extra)), (b[0]-ux*(right+extra), b[1]-uy*(right+extra))))
    return out


# Auto spacing: thread fills a narrow column quickly, so narrow columns sew a
# little more open and wide ones a little denser. Our own curve, after published
# advice that satin spacing should follow column width.
def auto_spacing(base, width):
    if width < 2.0:
        return base+.06*min(1.0, (2.0-width)/1.5)
    if width > 5.0:
        return max(min(base, .25), base-.03*min(1.0, (width-5.0)/3.0))
    return base


def spaced_by_width(pairs_at, base):
    """Pairs whose distance along the column follows auto_spacing(width),
    placed between the fine samples so the spacing isn't rounded to them."""
    fine = pairs_at(.05)
    if len(fine) < 3:
        return fine
    out, walked = [fine[0]], 0.0
    for prev, here in zip(fine, fine[1:]):
        step = math.dist(lerp(*prev, .5), lerp(*here, .5))
        start = 0.0
        while step > 1e-12:
            target = auto_spacing(base, math.dist(*lerp_pair(prev, here, start/step)))
            if walked+(step-start) < target-1e-9:
                walked += step-start
                break
            start += target-walked
            out.append(lerp_pair(prev, here, start/step)); walked = 0.0
    if math.dist(lerp(*out[-1], .5), lerp(*fine[-1], .5)) > 1e-6:
        out.append(fine[-1])
    return out


def lerp_pair(p, q, t):
    return lerp(p[0], q[0], t), lerp(p[1], q[1], t)


# Underlay chosen from the column width when the author set none (auto
# underlay). Cut-offs are ours: published guidance gives centre run for columns of
# about 2–3 mm, edge run for larger shapes and zigzag added on wide ones.
def auto_underlay(width):
    if width < 1.5:
        return dict(center_walk=False, contour_underlay=False, zigzag_underlay=False)
    if width < 3.0:
        return dict(center_walk=True, contour_underlay=False, zigzag_underlay=False)
    return dict(center_walk=False, contour_underlay=True, zigzag_underlay=width >= 6.0)


def median_width(pairs_):
    widths = sorted(math.dist(p, q) for p, q in pairs_)
    return widths[len(widths)//2] if widths else 0.0


# Shortening (automatic corners): on the inside of a tight curve the needle
# holes crowd together. Where one rail advances less than half as far as the
# other, every other stitch stops this share of the width short of the inner rail.
SHORTEN_SHARE = .35


def shorten_inner(final):
    out = list(final)
    for i in range(1, len(final)-1, 2):
        (pa, pb), (a, b), (na, nb) = final[i-1], final[i], final[i+1]
        step_a, step_b = math.dist(pa, na), math.dist(pb, nb)
        if max(step_a, step_b) < 1e-9 or min(step_a, step_b) >= .5*max(step_a, step_b):
            continue
        out[i] = (lerp(a, b, SHORTEN_SHARE), b) if step_a < step_b else (a, lerp(b, a, SHORTEN_SHARE))
    return out


# Auto Split: a satin stitch longer than this is split into shorter stitches.
# The split points move from row to row, so the needle holes don't line up into
# a visible groove down the column (splitting every stitch at its middle did).
SPLIT_MM = 7.0
_SPLIT_SHIFT = (0.0, 1/3, -1/3, 1/6, -1/6)


def split_rows(final, limit=SPLIT_MM):
    """Sewing order p0, q0, p1, q1… where every leg across the column (there
    and back) longer than `limit` is divided at staggered points."""
    order = [point for pair in final for point in pair]
    points = order[:1]
    for leg, (p, q) in enumerate(zip(order, order[1:])):
        d = math.dist(p, q)
        if limit and d > limit:
            shift = _SPLIT_SHIFT[leg % len(_SPLIT_SHIFT)]
            # The longest part is (1+|shift|)/n of the leg; pick n so it fits, with
            # room for the 0.1 mm machine grid moving both ends.
            n = int(math.ceil(d*(1+1/3)/max(.5, limit-.15)))
            # Positions are measured from the same rail on every leg (legs run there
            # and back), so neighbouring legs never share a hole.
            spots = [(k+shift)/n for k in range(1, n)]
            if leg % 2:
                spots = [1-s for s in reversed(spots)]
            points.extend(lerp(p, q, s) for s in spots)
        points.append(q)
    return points


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


# 3D puff over foam, after the usual puff method: short running stitches tack the
# foam, narrow caps close the open ends, a zigzag underlay holds and cuts the
# foam, then dense satin covers all of it. One stitch never crosses more than
# PUFF_LONGEST_MM: a split stitch would cut the foam into loose pieces.
PUFF_TACK_MM, PUFF_ZIGZAG_MM, PUFF_CAP_MM, PUFF_LONGEST_MM = 1.7, 1.8, 1.0, 6.9


def _cap(p, q, r, s, spacing):
    """A narrow column across the open end p-q: short stitches from the end edge
    into the column, side by side, so the needle cuts the foam along the end.
    Each stitch goes to the same place across the stitch line r-s about a cap
    depth further in, so it stays inside the column even where the end is slanted
    (one fixed direction ran past the column's side, into the letter's hole)."""
    count = max(2, int(math.ceil(math.dist(p, q)/spacing))+1)
    out = []
    for k in range(count):
        e, i = lerp(p, q, k/(count-1)), lerp(r, s, k/(count-1))
        out.extend([i, e] if k % 2 else [e, i])
    return out


def _shorten(p, q, limit):
    d = math.dist(p, q)
    if d <= limit:
        return p, q
    k = (d-limit)/2/d
    return lerp(p, q, k), lerp(q, p, k)


def _puff_satin(matched, pull, spacing, closed, pairs_at, outline=None, caps=('start', 'end')):
    longest = max((math.dist(p, q) for p, q in matched), default=0)
    pull = max(pull) if isinstance(pull, (list, tuple)) else pull
    # The given pull is the outer edge; stay 0.05 mm inside it so rounding to the
    # 0.1 mm machine grid never puts a needle hole past the edge.
    pull = max(0.0, pull-.05)
    # Pull compensation keeps the satin from narrowing over the foam, within the machine limit.
    pull = max(0.0, min(pull, (PUFF_LONGEST_MM-longest)/2))
    final = compensate(matched, pull)
    # Where the column itself is wider than the limit (a slanted stitch across a
    # joint), shorten the stitch evenly at both ends: rounding to the 0.1 mm machine
    # grid can add up to 0.14 mm, which pushed 6.98 mm stitches to 7.02 mm.
    final = [_shorten(p, q, PUFF_LONGEST_MM-.05) for p, q in final]
    # The satin also sews from each stitch's end to the next one's start; where
    # the stitches fan out that diagonal is the longest: start the next one a
    # little further in along its own line.
    for i in range(1, len(final)):
        (_, back), (p, q) = final[i-1], final[i]
        if math.dist(back, p) > PUFF_LONGEST_MM-.05:
            lo, hi = 0.0, .5
            for _ in range(30):
                t = (lo+hi)/2
                lo, hi = (lo, t) if math.dist(back, lerp(p, q, t)) <= PUFF_LONGEST_MM-.05 else (t, hi)
            final[i] = (lerp(p, q, hi), q)
    middle = [lerp(p, q, .5) for p, q in pairs_at(PUFF_TACK_MM)]
    points = running(middle, PUFF_TACK_MM, 0)
    def cap(index, step):
        p, q = final[index]
        if ('start' if index == 0 else 'end') not in caps:
            return []
        if closed or math.dist(p, q) < 1.0 or len(final) < 3:
            return []
        m, far = lerp(p, q, .5), None
        for r, s in final[index::step]:
            if math.dist(m, lerp(r, s, .5)) >= PUFF_CAP_MM:
                far, rung = lerp(r, s, .5), (r, s); break
        if far is None:
            return []
        d = math.dist(m, far)
        # Where the column joins another inside the shape there is no open end to close:
        # a cap there only piles thread on the joint.
        if outline is not None and outline.contains(Point(m[0]-(far[0]-m[0])/d*.6, m[1]-(far[1]-m[1])/d*.6)):
            return []
        return _cap(p, q, *rung, max(spacing, .3))
    points += cap(-1, -1)
    sparse = pairs_at(PUFF_ZIGZAG_MM)[::-1]
    for i, (p, q) in enumerate(sparse):
        points.extend([lerp(p, q, .15), lerp(q, p, .15)] if i % 2 == 0 else [lerp(q, p, .15), lerp(p, q, .15)])
    points += cap(0, 1)
    for p, q in final:
        points.extend((p, q))
    return points


def satin(subpaths, spacing=0.4, pull=0.0, center_walk=False, contour_underlay=False,
          zigzag_underlay=False, underlay_length=1.5, walk_repeats=2, indexed=False, puff=False, outline=None,
          caps=('start', 'end'), auto_space=False, underlay=None, pull_percent=0.0, split=0.0, shorten=False):
    """underlay='auto' picks the underlay from the column width (auto_underlay);
    auto_space varies spacing with width; split > 0 divides longer stitches."""
    if indexed and len(subpaths) >= 2 and len(subpaths[0][0]) == len(subpaths[1][0]) >= 2:
        a, b, rungs = [tuple(p) for p in subpaths[0][0]], [tuple(p) for p in subpaths[1][0]], []
        matched = indexed_pairs(a, b, spacing)
        pairs_at = lambda step: indexed_pairs(a, b, step)
    else:
        a, b, rungs = choose_rails(subpaths)
        matched = pairs(a, b, rungs, spacing)
        pairs_at = lambda step: pairs(a, b, rungs, step)
    if puff:
        # Tack-down walk to the far end, cap, zigzag back, cap, satin to the far end:
        # the column still ends where plain satin does.
        return _puff_satin(matched, pull, spacing, bool(subpaths[0][1]), pairs_at, outline, caps)
    if auto_space:
        matched = spaced_by_width(pairs_at, spacing)
    if underlay == 'auto':
        chosen = auto_underlay(median_width(matched))
        center_walk, contour_underlay, zigzag_underlay = (
            chosen['center_walk'], chosen['contour_underlay'], chosen['zigzag_underlay'])
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
    final = compensate(matched, pull, pull_percent)
    if shorten:
        final = shorten_inner(final)
    if points and math.dist(points[-1], final[-1][0]) < math.dist(points[-1], final[0][0]):
        final = final[::-1]
    if split:
        points.extend(split_rows(final, split))
    else:
        for p, q in final:
            points.extend((p, q))
    return points


def length_of_column(subpaths):
    a, b, _ = choose_rails(subpaths)
    return (path_length(a)+path_length(b))/2
