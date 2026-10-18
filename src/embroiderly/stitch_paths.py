"""Needle-path building blocks for the native stitch engine. Units: millimetres.

Every helper is deterministic. Travel stays inside the object it serves; when
no inside route exists the caller receives None and must cut instead.
"""
import heapq
import math
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.prepared import prep


def lerp(a, b, t):
    return (a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t)


def dedupe(points, epsilon=1e-6):
    out = []
    for p in points:
        p = (float(p[0]), float(p[1]))
        if not out or math.dist(out[-1], p) > epsilon:
            out.append(p)
    return out


def polygons(shape):
    if shape is None or shape.is_empty:
        return []
    if isinstance(shape, Polygon):
        return [shape]
    if isinstance(shape, MultiPolygon):
        return list(shape.geoms)
    return [g for part in getattr(shape, 'geoms', []) for g in polygons(part)]


def split_long(points, maximum):
    """Divide legs longer than maximum into equal parts; never moves a point."""
    if len(points) < 2:
        return list(points)
    out = [points[0]]
    for a, b in zip(points, points[1:]):
        n = max(1, math.ceil(math.dist(a, b)/maximum-1e-9))
        out.extend(lerp(a, b, i/n) for i in range(1, n+1))
    return out


def running(points, length, tolerance=0.1):
    """Running stitch: keep real corners, divide legs evenly at most `length`."""
    pts = dedupe(points)
    if len(pts) > 2 and tolerance > 0:
        pts = dedupe(LineString(pts).simplify(tolerance, preserve_topology=False).coords)
    return split_long(pts, length)


def enforce_min(points, minimum):
    """Drop penetrations closer than `minimum` to the previous one; keep both ends."""
    pts = dedupe(points)
    if len(pts) < 2:
        return pts
    out = [pts[0]]
    for p in pts[1:-1]:
        if math.dist(out[-1], p) >= minimum:
            out.append(p)
    last = pts[-1]
    if len(out) > 1 and math.dist(out[-1], last) < minimum:
        out[-1] = last
    else:
        out.append(last)
    while len(out) > 2 and math.dist(out[-2], out[-1]) < minimum:
        del out[-2]
    return out


def bean(points, repeats):
    """Each stitch sewn 1+2*repeats times (a→b→a→b ...)."""
    if repeats <= 0 or len(points) < 2:
        return list(points)
    out = [points[0]]
    for a, b in zip(points, points[1:]):
        out.append(b)
        for _ in range(repeats):
            out.extend((a, b))
    return out


def path_length(points):
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def resample(points, count):
    """`count` points evenly spaced by arc length along a polyline."""
    pts = dedupe(points)
    if len(pts) == 1 or count < 2:
        return [pts[0]]*max(count, 1)
    cumulative = [0.0]
    for a, b in zip(pts, pts[1:]):
        cumulative.append(cumulative[-1]+math.dist(a, b))
    total = cumulative[-1]
    out, j = [], 0
    for i in range(count):
        target = total*i/(count-1)
        while j < len(pts)-2 and cumulative[j+1] < target:
            j += 1
        span = cumulative[j+1]-cumulative[j]
        out.append(lerp(pts[j], pts[j+1], 0 if span <= 0 else (target-cumulative[j])/span))
    return out


def chain(paths, tolerance=0.05):
    """Join polylines whose ends meet into longer ones (fewer starts and cuts)."""
    pieces = [dedupe(p) for p in paths]
    pieces = [p for p in pieces if len(p) >= 2]
    merged = True
    while merged and len(pieces) > 1:
        merged = False
        ends = {}
        for i, p in enumerate(pieces):
            for which, point in ((0, p[0]), (1, p[-1])):
                ends.setdefault((round(point[0]/tolerance), round(point[1]/tolerance)), []).append((i, which))
        used = set()
        result = []
        for i, p in enumerate(pieces):
            if i in used:
                continue
            used.add(i)
            current = list(p)
            for _ in range(len(pieces)):
                key = (round(current[-1][0]/tolerance), round(current[-1][1]/tolerance))
                match = next(((j, w) for j, w in ends.get(key, []) if j not in used), None)
                if match is None:
                    break
                j, which = match
                used.add(j); merged = True
                current.extend((pieces[j] if which == 0 else pieces[j][::-1])[1:])
            result.append(current)
        pieces = result
    return pieces


def order_runs(runs, start=None):
    """Nearest-neighbour sewing order; a run may be sewn in either direction."""
    remaining = [list(r) for r in runs if len(r) >= 2]
    ordered = []
    position = start
    while remaining:
        if position is None:
            ordered.append(remaining.pop(0))
        else:
            index, reverse = min(((i, rev) for i in range(len(remaining)) for rev in (False, True)),
                                 key=lambda item: math.dist(position, remaining[item[0]][-1 if item[1] else 0]))
            run = remaining.pop(index)
            ordered.append(run[::-1] if reverse else run)
        position = ordered[-1][-1]
    return ordered


class Travel:
    """Shortest route between two points that stays inside a filled shape."""

    def __init__(self, shape, inset=0.15, slack=0.02):
        self.zone = prep(shape.buffer(slack))
        self._shape, self._inset, self.rings = shape, inset, None

    def _build(self):
        shape, inset = self._shape, self._inset
        inner = shape.buffer(-inset) if inset else shape
        if inner.is_empty:
            inner = shape
        self.rings = []
        for polygon in polygons(inner):
            for ring in (polygon.exterior, *polygon.interiors):
                coords = dedupe(ring.simplify(max(inset/2, .03)).coords)
                if len(coords) >= 4:
                    self.rings.append(coords[:-1] if coords[0] == coords[-1] else coords)
        self.lines = [LineString(r+[r[0]]) for r in self.rings]
        self.graph = {}
        for ring in self.rings:
            for a, b in zip(ring, ring[1:]+ring[:1]):
                self._edge(a, b)
        # Bridges let a route cross from an outer boundary to a hole boundary.
        # Each ring bridges to its nearest neighbour and to any ring within 3 mm.
        from shapely.ops import nearest_points
        pairs = set()
        for i in range(len(self.lines)):
            gaps = sorted((self.lines[i].distance(self.lines[j]), j) for j in range(len(self.lines)) if j != i)
            for rank, (gap, j) in enumerate(gaps):
                if rank == 0 or gap <= 3.0:
                    pairs.add((min(i, j), max(i, j)))
        for i, j in sorted(pairs):
            p, q = nearest_points(self.lines[i], self.lines[j])
            a, b = (p.x, p.y), (q.x, q.y)
            if self.inside(a, b):
                self._attach(i, a); self._attach(j, b); self._edge(a, b)

    def _edge(self, a, b):
        d = math.dist(a, b)
        self.graph.setdefault(a, {})[b] = d
        self.graph.setdefault(b, {})[a] = d

    def _attach(self, index, point):
        """Insert a point lying on ring `index` between its neighbouring vertices."""
        ring, line = self.rings[index], self.lines[index]
        distance = line.project(Point(point))
        walked = 0.0
        for a, b in zip(ring, ring[1:]+ring[:1]):
            step = math.dist(a, b)
            if walked+step >= distance-1e-9:
                self._edge(point, a); self._edge(point, b)
                return
            walked += step

    def inside(self, a, b):
        if math.dist(a, b) < 1e-9:
            return True
        return self.zone.contains(LineString([a, b]))

    def route(self, a, b, direct_mm=1.5, shortcut_penalty=3.0):
        """Prefer edge-following travel (hidden under row ends); straight only when short."""
        straight = self.inside(a, b)
        if straight and math.dist(a, b) <= direct_mm:
            return [a, b]
        if self.rings is None:
            self._build()
        if not self.rings:
            return [a, b] if straight else None
        saved = {k: dict(v) for k, v in self.graph.items()}
        try:
            if straight:
                d = math.dist(a, b)*shortcut_penalty
                self.graph.setdefault(a, {})[b] = d; self.graph.setdefault(b, {})[a] = d
            for point in (a, b):
                for index, line in enumerate(self.lines):
                    projected = line.interpolate(line.project(Point(point)))
                    entry = (projected.x, projected.y)
                    if self.inside(point, entry):
                        self._attach(index, entry); self._edge(point, entry)
            if a not in self.graph or b not in self.graph:
                return None
            best = {a: 0.0}; previous = {}; queue = [(0.0, a)]
            while queue:
                cost, node = heapq.heappop(queue)
                if node == b:
                    break
                if cost > best.get(node, math.inf):
                    continue
                for other, d in self.graph[node].items():
                    total = cost+d
                    if total < best.get(other, math.inf)-1e-12:
                        best[other] = total; previous[other] = node
                        heapq.heappush(queue, (total, other))
            if b not in best:
                return None
            path = [b]
            while path[-1] != a:
                path.append(previous[path[-1]])
            return path[::-1]
        finally:
            self.graph = saved
