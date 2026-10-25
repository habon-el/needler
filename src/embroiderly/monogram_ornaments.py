"""Monogram ornaments: crown, laurel, swirls and divider, drawn here in code.

Each ornament is satin columns (matched rails, sewn rung i to rung i) built
along a centre line with a width profile, scaled to the capital height and
placed around the letters' bounds (the frame's, when there is one). A piece is
a group of columns that overlap; embroidery_fonts.layout routes between them
inside the piece and cuts between pieces. No column is narrower than
MIN_WIDTH_MM (short zigzag stitches) or wider than MAX_WIDTH_MM.
"""
import math

PX_MM = 25.4/96
ORNAMENTS = ('none', 'crown', 'laurel', 'swirls', 'divider')
MIN_WIDTH_MM = .8
MAX_WIDTH_MM = 3.5


def _width(fraction, cap_px, low_mm, high_mm):
    """A satin width (px) that follows the letters, inside a sewable range."""
    return min(max(fraction*cap_px, low_mm/PX_MM), high_mm/PX_MM)


def _resample(points, step):
    """The centre line with a point about every `step` px (a rung each)."""
    out = [points[0]]
    for p, q in zip(points, points[1:]):
        n = max(1, math.ceil(math.dist(p, q)/step))
        out += [(p[0]+(q[0]-p[0])*k/n, p[1]+(q[1]-p[1])*k/n) for k in range(1, n+1)]
    return [p for i, p in enumerate(out) if i == 0 or math.dist(p, out[i-1]) > 1e-6]


def column(centre, profile):
    """Matched satin rails along a centre line; profile(u) is the width (px) at u in 0..1."""
    from shapely.geometry import Polygon
    points = _resample(centre, .6/PX_MM)
    if len(points) < 3:
        raise ValueError('An ornament does not fit at this size. Choose bigger letters or no ornament.')
    total = sum(math.dist(p, q) for p, q in zip(points, points[1:]))
    a, b, run = [], [], 0.0
    for i, p in enumerate(points):
        if i:
            run += math.dist(points[i-1], p)
        before, after = points[max(0, i-1)], points[min(len(points)-1, i+1)]
        dx, dy = after[0]-before[0], after[1]-before[1]
        length = math.hypot(dx, dy)
        nx, ny = -dy/length, dx/length
        half = profile(run/total)/2
        a.append((p[0]+nx*half, p[1]+ny*half))
        b.append((p[0]-nx*half, p[1]-ny*half))
    # A rail that folds back on itself (a bend tighter than half the width) cannot be satin.
    if not Polygon(a+b[::-1]).is_valid:
        raise ValueError('An ornament does not fit at this size. Choose bigger letters or no ornament.')
    return a, b


def _taper(wide, thin, ends=.18):
    """Width profile: `thin` at both ends, `wide` in the middle, eased."""
    return lambda u: thin+(wide-thin)*min(1.0, math.sin(math.pi*min(max(u, 0), 1))/math.sin(math.pi*ends))


def _point(width, thin):
    """Width profile from `width` at the base (u=0) down to `thin` at the tip (u=1)."""
    return lambda u: thin+(width-thin)*(1-u)**.8


def _leaf(width, thin):
    """Leaf, sewn tip (u=0) to base (u=1): narrow tip, widest past the middle."""
    return lambda u: thin+(width-thin)*math.sin(math.pi*.85*min(max(u, 0), 1))**.7


def _arc(start, direction, length, bend, steps=12):
    """A gently curved line from start: heading `direction` (radians), turning `bend` radians in all."""
    points, (x, y) = [start], start
    for k in range(steps):
        heading = direction+bend*(k+.5)/steps
        x, y = x+math.cos(heading)*length/steps, y+math.sin(heading)*length/steps
        points.append((x, y))
    return points


def crown(bounds, cap, avoid=None):
    """Five points on a band, each with a bead on top, above the words."""
    left, top, right, bottom = bounds
    cx, gap = (left+right)/2, max(.35*cap, 1.5/PX_MM)
    band, thin = _width(.2, cap, 1.2, MAX_WIDTH_MM), MIN_WIDTH_MM/PX_MM
    prong, bead = _width(.34, cap, 1.0, MAX_WIDTH_MM), _width(.22, cap, 1.2, 3.0)
    wide, tall = 1.9*cap, 1.0*cap
    y = top-gap-band/2
    columns = []
    # Prongs right to left, each bead then point sewn tip to base: the travel to the next
    # prong runs along the band and up the point, both sewn over afterwards; band last.
    for spread, rise in ((.5, .8), (.25, .55), (0, 1), (-.25, .55), (-.5, .8)):
        foot = (cx+spread*.84*wide, y)
        tip = (cx+spread*1.06*wide, y-band/2-rise*tall)
        heading = math.atan2(tip[1]-foot[1], tip[0]-foot[0])
        cap_top = (tip[0]+math.cos(heading)*1.1*bead, tip[1]+math.sin(heading)*1.1*bead)
        start = (tip[0]-math.cos(heading)*.15*bead, tip[1]-math.sin(heading)*.15*bead)
        columns.append(column([cap_top, start], _taper(bead, thin, .5)))
        columns.append(column([tip, foot], lambda u, p=_point(prong, thin): p(1-u)))
    columns.append(column([(cx-wide/2-band, y), (cx+wide/2+band, y)], lambda u: band))
    return [columns]


def laurel(bounds, cap, avoid=None):
    """Two leafy branches round the sides and bottom, meeting under the words."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    left, top, right, bottom = bounds
    leaf_long, gap = .75*cap, max(.35*cap, 1.5/PX_MM)
    margin = gap+.6*leaf_long
    # Round the words like the oval frame (an ellipse that holds the whole box), drawn
    # in closer while the leaves stay clear of the letters and any frame.
    best = None
    for grow in (1.0, 1.08, 1.16, 1.26, 1.41):
        pieces = _laurel(bounds, cap, leaf_long, margin, grow)
        if avoid is None or avoid.is_empty:
            return pieces
        best = pieces
        shape = unary_union([Polygon(list(a)+list(b)[::-1]).buffer(0) for piece in pieces for a, b in piece])
        if shape.distance(avoid) >= gap*.8:
            return pieces
    return best


def _laurel(bounds, cap, leaf_long, margin, grow):
    left, top, right, bottom = bounds
    cx, cy = (left+right)/2, (top+bottom)/2
    stem, leaf_wide, thin = _width(.09, cap, .9, 2.0), _width(.3, cap, 1.2, MAX_WIDTH_MM), MIN_WIDTH_MM/PX_MM
    rx, ry = ((right-left)/2+margin)*grow, ((bottom-top)/2+margin)*grow
    pieces = []
    for side in (-1, 1):
        # Angles from just beside the bottom middle, round the side to above half height.
        angles = [math.radians(90-side*(8+k*(117/40))) for k in range(41)]
        line = [(cx+rx*math.cos(t), cy+ry*math.sin(t)) for t in angles]
        leaves = []
        for k in range(4):
            i = round((k+.6)/4.5*(len(line)-1))
            p, q = line[i], line[min(i+1, len(line)-1)]
            heading = math.atan2(q[1]-p[1], q[0]-p[0])
            # Out and in leaves, leaning 32° forward from the stem.
            for turn in (math.radians(32), -math.radians(32)):
                direction = heading+turn
                leaves.append((k, _arc(p, direction, leaf_long, -turn*.4)[::-1]))
        end = line[-1]
        heading = math.atan2(end[1]-line[-2][1], end[0]-line[-2][0])
        leaves.append((4, _arc(end, heading, leaf_long*.9, 0)[::-1]))
        columns = [column(points, _leaf(leaf_wide, thin)) for _, points in sorted(leaves, key=lambda l: -l[0])]
        # Stem from the bottom up, sewn last over the travel between the leaves.
        columns.append(column(line, lambda u: stem))
        pieces.append(columns)
    return pieces


def swirls(bounds, cap, avoid=None):
    """A flourish each side: out from the words, then curling up."""
    left, top, right, bottom = bounds
    cy, gap = (top+bottom)/2, max(.35*cap, 1.5/PX_MM)
    wide, thin = _width(.14, cap, 1.0, 3.0), MIN_WIDTH_MM/PX_MM
    length, turn, steps = 2.4*cap, 1.75*math.pi, 120
    # Curvature grows along the line (a clothoid-like curl), with a slight dip first.
    strength = turn/(length*(1/3-.1))
    pieces = []
    for side in (-1, 1):
        x, y, heading = (right+gap if side > 0 else left-gap), cy+.15*cap, 0.0
        points = [(x, y)]
        for k in range(steps):
            u = (k+.5)/steps
            heading += strength*(u*u-.1)*length/steps
            x += side*math.cos(heading)*length/steps
            y -= math.sin(heading)*length/steps
            points.append((x, y))
        pieces.append([column(points, lambda u: thin+(wide-thin)*math.sin(math.pi*min(1, u*1.15))**.8
                              if u < .87 else thin)])
    return pieces


def divider(bounds, cap, avoid=None):
    """A pointed line under the words, widest in the middle."""
    left, top, right, bottom = bounds
    cx, gap = (left+right)/2, max(.35*cap, 1.5/PX_MM)
    wide, thin = _width(.13, cap, .9, 2.5), MIN_WIDTH_MM/PX_MM
    half = max((right-left)/2, cap)
    y = bottom+gap+wide/2
    return [[column([(cx-half, y), (cx+half, y)], _taper(wide, thin, .5))]]


def ornament(kind, bounds, cap, avoid=None):
    """Pieces (lists of (rail a, rail b) columns in sewing order) of this ornament
    around `bounds` (px); `avoid` (the letters and frame) must stay clear of it."""
    if kind not in ORNAMENTS:
        raise ValueError('Choose a listed ornament.')
    if kind == 'none':
        return []
    pieces = dict(crown=crown, laurel=laurel, swirls=swirls, divider=divider)[kind](bounds, cap, avoid)
    if avoid is not None and not avoid.is_empty:
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
        shape = unary_union([Polygon(list(a)+list(b)[::-1]).buffer(0) for piece in pieces for a, b in piece])
        if shape.distance(avoid) < .5/PX_MM:
            raise ValueError('This ornament touches the letters at this size. Choose another ornament, '
                             'bigger letters or no ornament.')
    return pieces
