"""Native area fills: tatami (with underlay), offset (contour), wave, spiral ripple and meander.

Each function returns a list of runs (lists of points in millimetres). A new
run means the caller must cut and lock, because no inside travel was found.
Rows sit on a global grid so neighbouring objects line up; stagger offsets
avoid visible needle-hole lines, like a conventional tatami.
"""
import math
import random
import numpy as np
from shapely.affinity import affine_transform
from shapely.geometry import LineString, MultiLineString, Point, Polygon
from shapely.ops import unary_union
from .stitch_paths import Travel, dedupe, enforce_min, lerp, polygons, running, split_long


def _frame(angle_deg):
    a = math.radians(angle_deg)
    u = (math.cos(a), -math.sin(a))           # row direction, y-down screen space
    v = (math.sin(a), math.cos(a))            # row-to-row direction
    to_frame = [u[0], u[1], v[0], v[1], 0, 0]
    def back(p):
        return (p[0]*u[0]+p[1]*v[0], p[0]*u[1]+p[1]*v[1])
    return to_frame, back


def _rows(shape, spacing):
    """Horizontal scanline intervals grouped by row index (frame coordinates)."""
    left, top, right, bottom = shape.bounds
    first = math.floor(top/spacing)
    last = math.ceil(bottom/spacing)
    lines = [((left-1, (k+.5)*spacing), (right+1, (k+.5)*spacing)) for k in range(first, last+1)
             if top < (k+.5)*spacing < bottom]
    rows = {}
    if not lines:
        return rows
    hit = shape.intersection(MultiLineString(lines))
    parts = [hit] if isinstance(hit, LineString) else [g for g in getattr(hit, 'geoms', []) if isinstance(g, LineString)]
    for part in parts:
        xs = [c[0] for c in part.coords]
        if len(xs) < 2 or max(xs)-min(xs) < 1e-6:
            continue
        k = round(part.coords[0][1]/spacing-.5)
        rows.setdefault(k, []).append((min(xs), max(xs)))
    for k in rows:
        rows[k].sort()
    return rows


def _sections(rows):
    """Split scanline intervals into blocks that can be sewn back and forth."""
    open_sections, finished = [], []
    for k in sorted(rows):
        intervals = rows[k]
        links = {}
        for s_index, section in enumerate(open_sections):
            last_k, (a, b) = section[-1]
            if last_k != k-1:
                continue
            links[s_index] = [i for i, (c, d) in enumerate(intervals) if c < b and a < d]
        claimed = {}
        for s_index, targets in links.items():
            for t in targets:
                claimed.setdefault(t, []).append(s_index)
        next_open = []
        continued = set()
        for i, interval in enumerate(intervals):
            owners = claimed.get(i, [])
            if len(owners) == 1 and len(links[owners[0]]) == 1:
                section = open_sections[owners[0]]
                section.append((k, interval)); next_open.append(section); continued.add(owners[0])
            else:
                next_open.append([(k, interval)])
        for s_index, section in enumerate(open_sections):
            if s_index not in continued:
                finished.append(section)
        open_sections = next_open
    return finished+open_sections


def _row_points(k, interval, forward, max_len, staggers, minimum, spacing):
    a, b = interval
    y = (k+.5)*spacing
    # staggers: a count (even diagonal), or a tuple of offset fractions (step fill patterns).
    offset = (staggers[k % len(staggers)] if isinstance(staggers, tuple) else (k % staggers)/staggers)*max_len
    grid = []
    j = math.ceil((a-offset)/max_len)
    while offset+j*max_len < b:
        x = offset+j*max_len
        if x-a >= minimum and b-x >= minimum:
            grid.append(x)
        j += 1
    xs = [a]+grid+[b]
    if not forward:
        xs = xs[::-1]
    return [(x, y) for x in xs]


def tatami(shape, angle=0.0, spacing=0.4, max_len=3.0, staggers=4, minimum=0.45, start=None,
           travel_len=2.0, underlay=True, underlay_angle=None, underlay_spacing=None, underlay_inset=0.3,
           underlay_max_len=3.0, join=True):
    """join=False leaves separate sections as separate runs (open fills, where a
    travel line across the area would show)."""
    runs = _underlay(shape, angle, spacing, minimum, start, travel_len, underlay_angle, underlay_spacing,
                     underlay_inset, underlay_max_len) if underlay else []
    position = runs[-1][-1] if runs else start
    top_runs = []
    for piece in sorted(polygons(shape), key=lambda p: -p.area):
        top_runs.extend(_tatami_layer(piece, angle, spacing, max_len, staggers, minimum,
                                      position, travel_len, Travel(piece), join))
        if top_runs:
            position = top_runs[-1][-1]
    return join_runs(runs+top_runs, shape, travel_len) if join else runs+top_runs


def _underlay(shape, angle, spacing, minimum, start=None, travel_len=2.0, underlay_angle=None,
              underlay_spacing=None, inset=0.3, max_len=3.0):
    """Open rows across the top stitches, kept `inset` inside the edge, that hold the fabric."""
    runs, position = [], start
    inner = shape.buffer(-inset)
    if not inner.is_empty and inner.area > 2*(underlay_spacing or spacing*3)**2:
        for piece in polygons(inner):
            for run in _tatami_layer(piece, angle+90 if underlay_angle is None else underlay_angle,
                                     underlay_spacing or max(spacing*3, 1.2), max_len, 1,
                                     minimum, position, travel_len, Travel(piece)):
                runs.append(run); position = run[-1]
    return runs


def join_runs(runs, shape, travel_len):
    """Connect consecutive runs with inside travel where possible."""
    if not runs:
        return []
    travel = None
    out = [list(runs[0])]
    for run in runs[1:]:
        if travel is None:
            travel = Travel(shape)
        route = travel.route(out[-1][-1], run[0])
        if route is None:
            out.append(list(run))
        else:
            out[-1].extend(running(route, travel_len, 0)[1:])
            out[-1].extend(run[1:])
    return out


def _tatami_layer(piece, angle, spacing, max_len, staggers, minimum, start, travel_len, travel, join=True):
    to_frame, back = _frame(angle)
    framed = affine_transform(piece, to_frame)
    rows = _rows(framed, spacing)
    if not rows:
        return _tiny(piece, minimum)
    sections = _sections(rows)
    position = None
    if start is not None:
        position = (start[0]*to_frame[0]+start[1]*to_frame[1], start[0]*to_frame[2]+start[1]*to_frame[3])
    runs, remaining = [], list(sections)
    while remaining:
        def corners(section):
            (k0, (a0, b0)), (k1, (a1, b1)) = section[0], section[-1]
            y0, y1 = (k0+.5)*spacing, (k1+.5)*spacing
            return [((a0, y0), False, True), ((b0, y0), False, False),
                    ((a1, y1), True, True), ((b1, y1), True, False)]
        if position is None:
            index, choice = 0, corners(remaining[0])[0]
        else:
            index, choice = min(((i, c) for i, s in enumerate(remaining) for c in corners(s)),
                                key=lambda item: math.dist(item[1][0], position))
        section = remaining.pop(index)
        _, reverse, forward = choice
        if reverse:
            section = section[::-1]
        points = []
        for row, (k, interval) in enumerate(section):
            row_points = _row_points(k, interval, forward, max_len, staggers, minimum, spacing)
            if points and math.dist(points[-1], row_points[0]) < minimum:
                # A turn shorter than the minimum stitch would be dropped and cut
                # the corner; start the row just far enough in instead.
                end, first = points[-1], row_points[0]
                step = math.sqrt(max(0.0, minimum**2-(first[1]-end[1])**2))+.02
                x = end[0]+step if forward else end[0]-step
                x = max(first[0], x) if forward else min(first[0], x)
                if len(row_points) > 1 and abs(x-row_points[-1][0]) >= minimum:
                    row_points[0] = (x, first[1])
                    if len(row_points) > 2 and abs(row_points[1][0]-x) < minimum:
                        del row_points[1]
            if points:
                # Edge connection between rows stays inside the object.
                link = travel.route(back(points[-1]), back(row_points[0]))
                if link is not None and len(link) > 2:
                    points.extend(_to_frame_points(running(link, travel_len, 0)[1:-1], to_frame))
            points.extend(row_points)
            forward = not forward
        run = [back(p) for p in points]
        runs.append(split_long(run, max_len))
        position = points[-1]
    return join_runs(runs, piece, travel_len) if join else runs


def _to_frame_points(points, m):
    return [(p[0]*m[0]+p[1]*m[1], p[0]*m[2]+p[1]*m[3]) for p in points]


def _tiny(shape, minimum):
    """Areas thinner than one row: a single pass along their long axis."""
    if shape.is_empty:
        return []
    box = shape.minimum_rotated_rectangle
    coords = list(box.exterior.coords) if hasattr(box, 'exterior') else list(box.coords)
    if len(coords) < 3:
        if len(coords) == 2 and math.dist(*coords) >= minimum:
            return [[coords[0], coords[1]]]
        center = shape.centroid
        return [_tack((center.x, center.y), minimum)]
    edges = [(coords[i], coords[i+1]) for i in range(len(coords)-1)]
    a, b = max(edges, key=lambda e: math.dist(*e))
    c, d = min(edges, key=lambda e: math.dist(*e))
    shift = ((c[0]+d[0])/2-(a[0]+b[0])/2, (c[1]+d[1])/2-(a[1]+b[1])/2)
    p, q = (a[0]+shift[0]/2, a[1]+shift[1]/2), (b[0]+shift[0]/2, b[1]+shift[1]/2)
    if math.dist(p, q) < minimum:
        return [_tack(lerp(p, q, .5), minimum)]
    return [[p, q, p]]


def _tack(point, minimum):
    step = minimum+.05
    return [point, (point[0]+step, point[1]), point]


def contour(shape, spacing=0.4, length=2.0, minimum=0.45, start=None, tolerance=0.1, underlay=False, angle=0.0):
    """Offset fill: concentric outlines from the boundary inward, each an inset of
    the area by one more row spacing (holes grow outward the same way), joined
    by short inside steps. underlay: open rows along `angle` first, inset 0.3 mm."""
    rings = []
    level = 0
    current = shape
    base = shape.simplify(min(.05, spacing/4))
    while not current.is_empty and level < 400:
        for piece in polygons(current):
            for ring in (piece.exterior, *piece.interiors):
                coords = dedupe(ring.coords)
                if len(coords) >= 3 and LineString(coords).length >= minimum*2:
                    rings.append(coords)
        level += 1
        current = base.buffer(-spacing*level, quad_segs=4, join_style='mitre' if level < 2 else 'round')
    if not rings:
        return _tiny(shape, minimum)
    runs = _underlay(shape, angle, spacing, minimum, start, length, underlay_angle=angle) if underlay else []
    position = runs[-1][-1] if runs else start
    remaining = [(ring, np.asarray(ring)) for ring in rings]
    while remaining:
        if position is None:
            index, offset = 0, 0
        else:
            best = None
            for i, (_, array) in enumerate(remaining[:50]):
                distances = np.hypot(array[:, 0]-position[0], array[:, 1]-position[1])
                j = int(np.argmin(distances))
                if best is None or distances[j] < best[0]:
                    best = (distances[j], i, j)
            _, index, offset = best
        ring = remaining.pop(index)[0]
        loop = ring[:-1] if ring[0] == ring[-1] else ring
        loop = loop[offset:]+loop[:offset]
        runs.append(running(loop+[loop[0]], length, tolerance))
        position = runs[-1][-1]
    return join_runs(runs, shape, length)


def spiral(shape, spacing=1.2, length=1.0, minimum=0.45, start=None, tolerance=0.15):
    """Archimedean spiral from the area's visual centre, clipped to the area."""
    center = shape.representative_point() if not shape.centroid.within(shape) else shape.centroid
    cx, cy = center.x, center.y
    left, top, right, bottom = shape.bounds
    radius = max(math.dist((cx, cy), corner) for corner in ((left, top), (right, top), (left, bottom), (right, bottom)))
    points = []
    theta = 0.0
    while True:
        r = spacing*theta/(2*math.pi)
        if r > radius+spacing:
            break
        points.append((cx+r*math.cos(theta), cy+r*math.sin(theta)))
        theta += min(.5, max(.02, length*.5/max(r, .1)))
    clipped = shape.intersection(LineString(points))
    pieces = [clipped] if isinstance(clipped, LineString) else [g for g in getattr(clipped, 'geoms', []) if isinstance(g, LineString)]
    # Intersection keeps spiral order; drop fragments too short to stitch.
    pieces = [p for p in pieces if p.length >= minimum]
    if not pieces:
        return _tiny(shape, minimum)
    runs = [running(list(p.coords), length, tolerance) for p in pieces]
    return join_runs(runs, shape, length)


def meander(shape, cell=2.0, length=1.0, minimum=0.45, seed=1, smooth=2, tolerance=0.1):
    """Single-line stipple: trace around a random spanning tree of grid cells."""
    zone = shape.buffer(-cell*.25)
    if zone.is_empty:
        return _tiny(shape, minimum)
    left, top, right, bottom = zone.bounds
    cols, rows = int(math.ceil((right-left)/cell))+1, int(math.ceil((bottom-top)/cell))+1
    if cols*rows > 40000:
        cell *= math.sqrt(cols*rows/40000)
        cols, rows = int(math.ceil((right-left)/cell))+1, int(math.ceil((bottom-top)/cell))+1
    from shapely.prepared import prep
    inside_zone = prep(zone)
    cells = {(i, j) for i in range(cols) for j in range(rows)
             if inside_zone.contains(Point(left+(i+.5)*cell, top+(j+.5)*cell))}
    if not cells:
        return _tiny(shape, minimum)
    rng = random.Random(seed)
    runs = []
    unvisited = set(cells)
    while unvisited:
        root = min(unvisited)
        tree = {root: []}
        stack = [root]; unvisited.discard(root)
        while stack:
            node = stack[-1]
            options = [(node[0]+dx, node[1]+dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                       if (node[0]+dx, node[1]+dy) in unvisited]
            if not options:
                stack.pop(); continue
            nxt = rng.choice(options)
            unvisited.discard(nxt)
            tree[node].append(nxt); tree[nxt] = [node]
            stack.append(nxt)
        loop = _tree_cycle(tree)
        points = [(left+(x+.5)*cell/2, top+(y+.5)*cell/2) for x, y in loop]
        for _ in range(smooth):
            points = _chaikin(points)
        runs.append(running(points+[points[0]], length, tolerance))
    return join_runs(runs, shape, length)


def _tree_cycle(tree):
    """Spanning-tree coverage: every half-cell node gets degree two (one loop)."""
    graph = {}
    def link(a, b):
        graph.setdefault(a, set()).add(b); graph.setdefault(b, set()).add(a)
    connected = {(a, b) for a, children in tree.items() for b in children}
    for (i, j) in tree:
        x, y = 2*i, 2*j
        tl, tr, bl, br = (x, y), (x+1, y), (x, y+1), (x+1, y+1)
        if ((i, j), (i, j-1)) not in connected:
            link(tl, tr)
        if ((i, j), (i, j+1)) not in connected:
            link(bl, br)
        if ((i, j), (i-1, j)) not in connected:
            link(tl, bl)
        if ((i, j), (i+1, j)) not in connected:
            link(tr, br)
        if ((i, j), (i+1, j)) in connected:
            link(tr, (x+2, y)); link(br, (x+2, y+1))
        if ((i, j), (i, j+1)) in connected:
            link(bl, (x, y+2)); link(br, (x+1, y+2))
    start = min(graph)
    loop, previous, node = [start], None, start
    while True:
        options = sorted(graph[node]-{previous}) if previous is not None else sorted(graph[node])
        if not options:
            break
        previous, node = node, options[0]
        if node == start:
            break
        loop.append(node)
        if len(loop) > len(graph)+1:
            break
    return loop


def _chaikin(points):
    out = []
    n = len(points)
    for i in range(n):
        a, b = points[i], points[(i+1) % n]
        out.append(lerp(a, b, .25)); out.append(lerp(a, b, .75))
    return out


def fill_shape(subpaths, rule='nonzero'):
    """Area from closed subpaths (mm). Even-odd XOR, or orientation for nonzero."""
    from shapely import make_valid
    rings = []
    for points, _ in subpaths:
        pts = dedupe(points)
        if len(pts) >= 3:
            polygon = Polygon(pts)
            if not polygon.is_valid:
                polygon = unary_union(polygons(make_valid(polygon)))
            if not polygon.is_empty and polygon.area > 1e-9:
                signed = sum(a[0]*b[1]-b[0]*a[1] for a, b in zip(pts, pts[1:]+pts[:1]))
                rings.append((polygon, signed))
    if not rings:
        return Polygon()
    if rule == 'evenodd' or len({s > 0 for _, s in rings}) == 1:
        if rule == 'evenodd':
            result = Polygon()
            for polygon, _ in rings:
                result = result.symmetric_difference(polygon)
            return unary_union(polygons(make_valid(result)))
        return unary_union([p for p, _ in rings])
    positive = unary_union([p for p, s in rings if s > 0])
    negative = unary_union([p for p, s in rings if s <= 0])
    # Fonts and drawings disagree about which direction is outer; choose the
    # interpretation where holes lie inside outlines.
    if negative.area > positive.area:
        positive, negative = negative, positive
    return unary_union(polygons(make_valid(positive.difference(negative))))


# Specialty fills. Patterns and proportions are our own.

# Step fill: tatami whose needle offsets climb and fall, so the holes form
# chevron steps across the area instead of one even diagonal.
STEP_PATTERN = (0.0, .2, .4, .6, .8, .6, .4, .2)


def step_fill(shape, angle=0.0, spacing=0.4, max_len=3.5, minimum=0.45, start=None, underlay=True):
    return tatami(shape, angle, spacing, max_len, STEP_PATTERN, minimum, start, underlay=underlay)


def gradient(shape, angle=0.0, spacing=0.4, open_spacing=1.6, max_len=3.0, staggers=4, minimum=0.45, start=None):
    """Rows from dense (`spacing`) on one side to open (`open_spacing`) on the
    other. The area is stretched across the rows so that ordinary, evenly spaced
    tatami rows land at the growing spacing once mapped back."""
    if shape.is_empty:
        return []
    to_frame, back = _frame(angle)
    framed = affine_transform(shape, to_frame)
    top, bottom = framed.bounds[1], framed.bounds[3]
    if bottom-top < spacing*2:
        return tatami(shape, angle, spacing, max_len, staggers, minimum, start, underlay=False)
    ys = np.linspace(top, bottom, 512)
    local = spacing+(open_spacing-spacing)*(ys-top)/(bottom-top)
    # Stretched coordinate: one row every `spacing` there is one real row every local spacing.
    us = top+np.concatenate(([0.0], np.cumsum((ys[1:]-ys[:-1])*spacing/((local[1:]+local[:-1])/2))))
    def warp(p):
        f = (p[0]*to_frame[0]+p[1]*to_frame[1], p[0]*to_frame[2]+p[1]*to_frame[3])
        return back((f[0], float(np.interp(f[1], ys, us))))
    def unwarp(p):
        f = (p[0]*to_frame[0]+p[1]*to_frame[1], p[0]*to_frame[2]+p[1]*to_frame[3])
        return back((f[0], float(np.interp(f[1], us, ys))))
    import shapely
    stretched = shapely.transform(shapely.segmentize(shape, .2),
                                  lambda xy: np.array([warp(p) for p in xy]).reshape(-1, 2))
    runs = tatami(stretched, angle, spacing, max_len, staggers, minimum,
                  None if start is None else warp(start), underlay=False, join=False)
    # Row-to-row links found inside the stretched area stay inside the real one to
    # within the 0.2 mm segment length; long legs are re-split after mapping back.
    # Sections stay separate: a travel line across the open side would show.
    return [split_long([unwarp(p) for p in run], max_len) for run in runs]


# Wave fill: tatami rows that rise and fall along a sine wave. One wavelength in
# millimetres for every area, on the global grid, so neighbouring wave areas line up.
WAVE_LENGTH_MM = 10.0
WAVE_AMPLITUDE_MM = 1.2


def wave(shape, angle=0.0, spacing=0.4, max_len=3.0, minimum=0.45, start=None, underlay=True,
         amplitude=WAVE_AMPLITUDE_MM, wavelength=WAVE_LENGTH_MM, tolerance=0.05):
    """Rows `spacing` apart (measured across the row direction) that follow
    y + amplitude*sin(2*pi*x/wavelength) in the row frame. Like `gradient`, the
    area is bent so the wave becomes straight rows, filled as tatami (inside
    travel, row turns), and the stitches are bent back. Each straight stitch is
    re-cut along the curve, at most `max_len` and within `tolerance` of it."""
    if shape.is_empty:
        return []
    import shapely
    to_frame, back = _frame(angle)
    k = 2*math.pi/max(1.0, wavelength)
    def bend(p, sign):
        f = (p[0]*to_frame[0]+p[1]*to_frame[1], p[0]*to_frame[2]+p[1]*to_frame[3])
        return back((f[0], f[1]+sign*amplitude*math.sin(k*f[0])))
    flat = shapely.transform(shapely.segmentize(shape, .2),
                             lambda xy: np.array([bend(p, -1) for p in xy]).reshape(-1, 2))
    if not flat.is_valid:
        flat = flat.buffer(0)
    runs = _underlay(shape, angle, spacing, minimum, start) if underlay else []
    position = runs[-1][-1] if runs else start
    top = tatami(flat, angle, spacing, max_len, 4, minimum,
                 None if position is None else bend(position, -1), underlay=False)
    for run in top:
        # Short pieces before bending, so the curve between stitches is kept.
        dense = split_long(run, .25)
        runs.append(running([bend(p, 1) for p in dense], max_len, tolerance))
    return join_runs(runs, shape, 2.0)


def radial(shape, spacing=0.4, max_len=3.0, minimum=0.45, start=None, center=None):
    """Stitches radiating from the centre. Rays start at staggered distances so
    the centre isn't buried under every ray: a ray only begins where its
    neighbours are a full `spacing` apart. Returns None when the rays from the
    centre cannot reach most of the area (very concave shapes): use tatami."""
    if shape.is_empty:
        return []
    if center is None:
        c = shape.centroid
        if not shape.contains(c):
            c = shape.representative_point()
        center = (c.x, c.y)
    cx, cy = center
    reach = max(math.dist(center, p) for piece in polygons(shape) for p in piece.exterior.coords)
    count = 2**max(3, int(math.ceil(math.log2(max(8.0, 2*math.pi*reach/spacing)))))
    from shapely.prepared import prep
    inside = prep(shape)
    rays = []
    for k in range(count):
        level = count if k == 0 else k & -k   # largest power of two dividing k
        begin = max(minimum, (count/level)*spacing/(2*math.pi))
        theta = 2*math.pi*k/count
        ux, uy = math.cos(theta), math.sin(theta)
        hit = shape.intersection(LineString([(cx, cy), (cx+ux*(reach+1), cy+uy*(reach+1))]))
        pieces = [hit] if hit.geom_type == 'LineString' else [g for g in getattr(hit, 'geoms', []) if g.geom_type == 'LineString']
        # Only the stretch connected to the centre: a ray never jumps across a gap.
        near = [g for g in pieces if g.distance(Point(cx, cy)) < 1e-6]
        if not near:
            continue
        end = max(math.dist(center, p) for p in near[0].coords)
        if end-begin < minimum:
            continue
        rays.append(((cx+ux*begin, cy+uy*begin), (cx+ux*end, cy+uy*end)))
    if not rays:
        return None
    sewn = unary_union([LineString(r).buffer(spacing) for r in rays])
    if sewn.intersection(shape).area < .85*shape.area:
        return None
    points = []
    for i, (inner, outer) in enumerate(rays):
        leg = [inner, outer] if i % 2 == 0 else [outer, inner]
        points.extend(split_long(leg, max_len) if not points else split_long(leg, max_len))
    # Neighbouring rays are joined at the rim or near the centre; a join that
    # would leave the area (a notch between rays) is cut by join_runs instead.
    runs, current = [], [points[0]]
    for p, q in zip(points, points[1:]):
        if not inside.contains(LineString([p, q]).interpolate(.5, normalized=True)):
            runs.append(current); current = [q]
        else:
            current.append(q)
    runs.append(current)
    return join_runs([enforce_min(r, minimum) for r in runs if len(r) >= 2], shape, 2.0)
