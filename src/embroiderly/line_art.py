"""Line-art digitizing: drawn strokes become continuous running-stitch routes.

Each colour's strokes are reduced to centre lines, joined across tiny gaps,
and every connected network is sewn as ONE path (redwork technique): an
Euler route that re-sews only the shortest connections it has to go back
over. Thread cuts are needed only between separate networks.
Units: pixels in, millimetres out.
"""
import heapq
import math
from collections import defaultdict
import numpy as np
from scipy.spatial import cKDTree
from skimage.morphology import skeletonize, remove_small_objects
from .satin_font import _graph
from .stitch_paths import dedupe, order_runs, path_length


class Network:
    """Undirected multigraph of centre-line edges between node ids."""

    def __init__(self):
        self.position = {}
        self.edges = []          # [u, v, points]
        self.counter = 0

    def node(self, point):
        self.counter += 1
        self.position[self.counter] = (float(point[0]), float(point[1]))
        return self.counter

    def add(self, u, v, points):
        self.edges.append([u, v, [tuple(map(float, p)) for p in points]])


def trace(mask):
    """Centre-line network of a binary stroke mask."""
    net = Network()
    nodes, edges = _graph(skeletonize(mask))
    ids = {key: net.node(point) for key, point in nodes.items()}
    for edge in edges:
        points = [(float(x), float(y)) for x, y in edge['pixels']]
        if edge.get('closed'):
            node = net.node(points[0])
            net.add(node, node, points+[points[0]])
        else:
            points[0], points[-1] = nodes[edge['a']], nodes[edge['b']]
            net.add(ids[edge['a']], ids[edge['b']], points)
    return net


def _components(net):
    parent = {n: n for n in net.position}

    def find(n):
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n
    for u, v, _ in net.edges:
        parent[find(u)] = find(v)
    return find


def bridge(net, gap):
    """Join a loose stroke end to the nearest stroke of another network."""
    joined = 0
    while True:
        find = _components(net)
        degree = defaultdict(int)
        for u, v, _ in net.edges:
            degree[u] += 1; degree[v] += 1
        samples, owner = [], []
        for index, (u, v, points) in enumerate(net.edges):
            for k, p in enumerate(points):
                samples.append(p); owner.append((index, k))
        if not samples:
            return joined
        tree = cKDTree(samples)
        best = None
        for node, count in degree.items():
            if count != 1:
                continue
            point = net.position[node]
            for distance, i in zip(*tree.query(point, k=min(24, len(samples)), distance_upper_bound=gap)):
                if not math.isfinite(distance):
                    break
                index, k = owner[i]
                u, v, _ = net.edges[index]
                if find(u) != find(node) and (best is None or distance < best[0]):
                    best = (distance, node, index, k)
                    break
        if best is None:
            return joined
        _, node, index, k = best
        u, v, points = net.edges[index]
        if 0 < k < len(points)-1:
            middle = net.node(points[k])
            net.edges[index] = [u, middle, points[:k+1]]
            net.add(middle, v, points[k:])
        else:
            middle = u if k == 0 else v
        net.add(node, middle, [net.position[node], net.position[middle]])
        joined += 1


def _nearby(adjacent, start, limit):
    """Graph distances (and the edges used) from start, up to `limit`."""
    best = {start: 0.0}; previous = {}; queue = [(0.0, start)]
    while queue:
        cost, node = heapq.heappop(queue)
        if cost > best.get(node, math.inf):
            continue
        for other, index, length in adjacent[node]:
            total = cost+length
            if total <= limit and total < best.get(other, math.inf):
                best[other] = total; previous[other] = (node, index)
                heapq.heappush(queue, (total, other))
    return best, previous


def routes(net, retrace_limit):
    """Continuous polylines per connected network (Euler routes).

    Loose ends are paired through the network when the way back is at most
    `retrace_limit` long; those edges are sewn twice. Other ends are joined by
    virtual moves, which become thread cuts, instead of long re-sewn stretches.
    """
    find = _components(net)
    groups = defaultdict(list)
    for index, (u, v, _) in enumerate(net.edges):
        groups[find(u)].append(index)
    result = []
    for indices in groups.values():
        edges = [list(net.edges[i])+[False] for i in indices]      # [u, v, points, virtual]
        lengths = [path_length(p) for _, _, p, _ in edges]
        adjacent = defaultdict(list)
        for i, (u, v, _, _) in enumerate(edges):
            adjacent[u].append((v, i, lengths[i])); adjacent[v].append((u, i, lengths[i]))
        degree = defaultdict(int)
        for u, v, _, _ in edges:
            degree[u] += 1; degree[v] += 1
        odd = sorted(n for n, d in degree.items() if d % 2)
        candidates = []
        odd_set = set(odd)
        for node in odd:
            best, previous = _nearby(adjacent, node, retrace_limit)
            for other, cost in best.items():
                if other in odd_set and other > node:
                    candidates.append((cost, node, other, previous))
        candidates.sort(key=lambda c: (c[0], c[1], c[2]))
        matched = set()
        base = len(edges)
        for cost, a, b, previous in candidates:
            if a in matched or b in matched:
                continue
            matched.update((a, b))
            node = b
            while node != a:
                before, index = previous[node]
                edges.append(list(edges[index][:3])+[False]); lengths.append(lengths[index])
                node = before
        # Remaining loose ends: virtual moves (cuts), leaving two as start/end.
        left = [n for n in odd if n not in matched]
        while len(left) > 2:
            a = left.pop(0)
            b = min(left, key=lambda n: math.dist(net.position[a], net.position[n]))
            left.remove(b)
            edges.append([a, b, [net.position[a], net.position[b]], True])
        # Hierholzer: walk every (possibly duplicated) edge exactly once.
        incident = defaultdict(list)
        for i, (u, v, _, _) in enumerate(edges):
            incident[u].append(i); incident[v].append(i)
        used = [False]*len(edges)
        start = left[0] if left else edges[0][0]
        stack, trail = [(start, None)], []
        while stack:
            node, via = stack[-1]
            while incident[node] and used[incident[node][-1]]:
                incident[node].pop()
            if incident[node]:
                i = incident[node].pop(); used[i] = True
                u, v = edges[i][:2]
                stack.append((v if u == node else u, (i, node)))
            else:
                stack.pop()
                if via is not None:
                    trail.append(via)
        points = []
        for i, origin in reversed(trail):
            u, v, p, virtual = edges[i]
            if virtual:
                if len(points) >= 2:
                    result.append(points)
                points = []
                continue
            segment = p if u == origin else p[::-1]
            points.extend(segment if not points else segment[1:])
        if len(points) >= 2:
            result.append(points)
        del base
    return result


def _tone(pixels):
    """Thread tone from the bright core of strokes, not their dark blended edges."""
    value = pixels.max(axis=1)
    core = pixels[value >= np.percentile(value, 75)]
    return '#%02x%02x%02x' % tuple(np.median(core, axis=0).astype(int))


def colour_layers(rgb, background_max=70):
    """Split light strokes on a dark background into thread colours.

    Colourfulness is measured relative to brightness, so the dim antialiased
    edge of a red stroke is still red. Returns [(hex, mask)]."""
    a = rgb.astype(int)
    value = a.max(axis=2)
    stroke = value > background_max
    saturation = (value-a.min(axis=2))/np.maximum(value, 1)
    neutral = stroke & (saturation < .25)
    coloured = stroke & ~neutral
    layers = []
    hue = np.argmax(a, axis=2)  # dominant channel: 0 red, 1 green, 2 blue
    for channel in range(3):
        mask = coloured & (hue == channel)
        if mask.sum() > 50:
            layers.append((_tone(a[mask]), mask))
    if neutral.sum() > 50:
        layers.append((_tone(a[neutral]), neutral))
    return layers


def digitize_lines(layers, mm_per_px, bridge_mm=1.0, retrace_mm=6.0, minimum_mm=.8, speck_px=6,
                   isolated_mm=(6.0, 3.0)):
    """[(hex, mask)] -> [(hex, [polyline mm])]; each polyline is sewn without a cut."""
    result = []
    for colour, mask in layers:
        mask = remove_small_objects(mask, max_size=speck_px)
        net = trace(mask)
        bridge(net, bridge_mm/mm_per_px)
        paths = [[(x*mm_per_px, y*mm_per_px) for x, y in dedupe(p)] for p in routes(net, retrace_mm/mm_per_px)]
        paths = [p for p in paths if path_length(p) >= minimum_mm]
        result.append((colour, paths))
    # A short mark far from all other strokes is scanner dust or interface
    # residue (icons in a screenshot), not part of the drawing.
    every = [(i, j, np.asarray(p)) for i, (_, paths) in enumerate(result) for j, p in enumerate(paths)]
    if len(every) > 1:
        points = np.vstack([a for _, _, a in every])
        owner = np.concatenate([np.full(len(a), k) for k, (_, _, a) in enumerate(every)])
        tree = cKDTree(points)
        drop = set()
        for k, (i, j, a) in enumerate(every):
            if path_length(a.tolist()) >= isolated_mm[1]:
                continue
            near = tree.query_ball_point(a, isolated_mm[0])
            if all(owner[n] == k for group in near for n in group):
                drop.add((i, j))
        result = [(colour, [p for j, p in enumerate(paths) if (i, j) not in drop]) for i, (colour, paths) in enumerate(result)]
    return [(colour, order_runs(paths)) for colour, paths in result]
