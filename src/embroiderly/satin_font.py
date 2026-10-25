"""Automatic satin columns from TrueType glyph outlines (our embroidery fonts).

Pipeline per glyph: outline -> raster -> medial skeleton -> stroke graph ->
pruned, straight-through merged strokes -> cross-sections against the true
outline -> paired rails with rungs. Columns are returned in em units (y down).
Sewing order hides connectors under strokes that are sewn later.
"""
from functools import lru_cache
import math
import numpy as np
import cv2
from PIL import Image, ImageDraw
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from shapely.affinity import affine_transform
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from skimage.morphology import skeletonize
from . import svg_geometry as sg
from .stitch_fills import fill_shape
from .stitch_paths import dedupe, path_length, polygons, resample

RESOLUTION = 420       # raster pixels per em
NEIGHBOURS = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]


@lru_cache(maxsize=8)
def _font(path):
    return TTFont(path, lazy=False)


def glyph_outline(path, char):
    """Glyph polygon in em units, y down, origin at the pen position."""
    font = _font(path)
    cmap = font.getBestCmap()
    if ord(char) not in cmap:
        raise KeyError(char)
    glyphs = font.getGlyphSet()
    name = cmap[ord(char)]
    pen = SVGPathPen(glyphs)
    glyphs[name].draw(pen)
    em = font['head'].unitsPerEm
    paths = [([(x/em, -y/em) for x, y in pts], True) for pts, _ in sg.parse_path(pen.getCommands(), em*.002)]
    shape = fill_shape(paths, 'nonzero') if paths else Polygon()
    return shape, glyphs[name].width/em


def _raster(shape):
    left, top, right, bottom = shape.bounds
    pad = 4
    k = RESOLUTION
    width, height = int(math.ceil((right-left)*k))+2*pad, int(math.ceil((bottom-top)*k))+2*pad
    image = Image.new('L', (width, height), 0)
    draw = ImageDraw.Draw(image)
    def px(ring):
        return [((x-left)*k+pad, (y-top)*k+pad) for x, y in ring.coords]
    for polygon in polygons(shape):
        draw.polygon(px(polygon.exterior), fill=1)
        for hole in polygon.interiors:
            draw.polygon(px(hole), fill=0)
    mask = np.asarray(image, bool)
    to_px = lambda x, y: ((x-left)*k+pad, (y-top)*k+pad)
    to_em = lambda x, y: ((x-pad)/k+left, (y-pad)/k+top)
    return mask, to_px, to_em


def _graph(skeleton):
    """Skeleton pixels -> (nodes, edges); junction pixel clusters become one node."""
    ys, xs = np.nonzero(skeleton)
    pixels = set(zip(xs.tolist(), ys.tolist()))
    def neighbours(p):
        return [(p[0]+dx, p[1]+dy) for dx, dy in NEIGHBOURS if (p[0]+dx, p[1]+dy) in pixels]
    degree = {p: len(neighbours(p)) for p in pixels}
    special = {p for p, d in degree.items() if d != 2}
    cluster = {}
    for p in special:
        if p in cluster:
            continue
        stack, members = [p], []
        cluster[p] = p
        while stack:
            q = stack.pop(); members.append(q)
            for r in neighbours(q):
                if r in special and r not in cluster:
                    cluster[r] = p; stack.append(r)
    nodes = {}
    for p, root in cluster.items():
        nodes.setdefault(root, []).append(p)
    nodes = {root: (float(np.mean([m[0] for m in members])), float(np.mean([m[1] for m in members])))
             for root, members in nodes.items()}
    edges, visited = [], set()
    for start in special:
        for step in neighbours(start):
            if step in special and cluster[step] == cluster[start]:
                continue
            if (start, step) in visited:
                continue
            path = [start, step]; previous, current = start, step
            visited.add((start, step))
            while current not in special:
                options = [r for r in neighbours(current) if r != previous and r not in path[-3:]]
                if not options:
                    break
                previous, current = current, options[0]
                path.append(current)
            if current in special:
                visited.add((current, previous))
                edges.append(dict(a=cluster[start], b=cluster[current], pixels=path))
    # One lookup set instead of searching every edge's pixel list for every pixel
    # (quadratic: detailed ink drawings took minutes). Same result.
    covered = {p for e in edges for p in e['pixels']}
    remaining = {p for p in pixels if p not in special and p not in covered}
    while remaining:
        start = min(remaining)
        path, previous, current = [start], None, start
        while True:
            options = [r for r in neighbours(current) if r != previous and r in remaining]
            remaining.discard(current)
            if not options:
                break
            previous, current = current, options[0]
            if current == start:
                break
            path.append(current)
        if len(path) > 3:
            edges.append(dict(a=None, b=None, pixels=path, closed=True))
    return nodes, edges


def _smooth(points, window=5):
    pts = np.asarray(points, float)
    if len(pts) < window:
        return [tuple(p) for p in pts]
    kernel = np.ones(window)/window
    pad = window//2
    padded = np.vstack([np.repeat(pts[:1], pad, 0), pts, np.repeat(pts[-1:], pad, 0)])
    out = np.column_stack([np.convolve(padded[:, i], kernel, 'valid') for i in (0, 1)])
    out[0], out[-1] = pts[0], pts[-1]
    return [tuple(p) for p in out]


def _tangent(points, index):
    a = points[max(0, index-1)]; b = points[min(len(points)-1, index+1)]
    d = math.dist(a, b)
    return ((b[0]-a[0])/d, (b[1]-a[1])/d) if d > 1e-9 else (1.0, 0.0)


def _strokes(nodes, edges, distance):
    """Prune spurs and merge straight-through strokes at junctions."""
    def width_at(p):
        x, y = int(round(p[0])), int(round(p[1]))
        return float(distance[min(max(y, 0), distance.shape[0]-1), min(max(x, 0), distance.shape[1]-1)])
    strokes = []
    for e in edges:
        pts = [(float(x), float(y)) for x, y in e['pixels']]
        if e.get('closed'):
            strokes.append(dict(points=pts, a=None, b=None, closed=True)); continue
        if e['a'] is not None:
            pts[0] = nodes[e['a']]
        if e['b'] is not None:
            pts[-1] = nodes[e['b']]
        strokes.append(dict(points=pts, a=e['a'], b=e['b'], closed=False))
    for _ in range(3):
        degree = {}
        for s in strokes:
            for end in (s['a'], s['b']):
                if end is not None:
                    degree[end] = degree.get(end, 0)+1
        kept = []
        for s in strokes:
            if s['closed']:
                kept.append(s); continue
            length = path_length(s['points'])
            ends = [degree.get(s['a'], 0), degree.get(s['b'], 0)]
            spur = (ends[0] == 1) != (ends[1] == 1) and max(ends) >= 3
            junction = s['a'] if ends[0] >= 3 else s['b']
            if spur and length < 1.0*width_at(nodes[junction]):
                continue
            if length < 1.0 and min(ends) >= 3:
                continue
            kept.append(s)
        strokes = kept
    # Two junctions joined by a stroke shorter than the stroke width are one
    # crossing (X, k): contract them so straight strokes can pass through.
    contracted = True
    while contracted:
        contracted = False
        degree = {}
        for s in strokes:
            for end in (s['a'], s['b']):
                if end is not None:
                    degree[end] = degree.get(end, 0)+1
        for i, s in enumerate(strokes):
            if s['closed'] or s['a'] is None or s['b'] is None or s['a'] == s['b']:
                continue
            if degree.get(s['a'], 0) < 3 or degree.get(s['b'], 0) < 3:
                continue
            reach = 1.3*max(width_at(nodes[s['a']]), width_at(nodes[s['b']]))
            if path_length(s['points']) > reach:
                continue
            keep, gone = s['a'], s['b']
            middle = ((nodes[keep][0]+nodes[gone][0])/2, (nodes[keep][1]+nodes[gone][1])/2)
            nodes[keep] = middle
            rest = []
            for j, t in enumerate(strokes):
                if j == i:
                    continue
                t = dict(t)
                if t['a'] in (keep, gone):
                    t['a'] = keep; t['points'] = [middle]+list(t['points'])
                if t['b'] in (keep, gone):
                    t['b'] = keep; t['points'] = list(t['points'])+[middle]
                rest.append(t)
            strokes = rest
            contracted = True
            break
    # Merge pairs meeting at a node: degree-2 nodes always, junctions when
    # the strokes continue nearly straight (bars of T, stems of H).
    merged = True
    while merged:
        merged = False
        by_node = {}
        for i, s in enumerate(strokes):
            if s['closed']:
                continue
            for end in ('a', 'b'):
                if s[end] is not None:
                    by_node.setdefault(s[end], []).append((i, end))
        for node, members in by_node.items():
            if len(members) < 2:
                continue
            best = None
            for x in range(len(members)):
                for y in range(x+1, len(members)):
                    (i, ei), (j, ej) = members[x], members[y]
                    if i == j:
                        continue
                    skip = width_at(nodes[node])
                    di = _away(strokes[i]['points'], ei, skip); dj = _away(strokes[j]['points'], ej, skip)
                    straightness = -(di[0]*dj[0]+di[1]*dj[1])
                    if len(members) == 2 or straightness > .82:
                        if best is None or straightness > best[0]:
                            best = (straightness, i, ei, j, ej)
            if best is None:
                continue
            _, i, ei, j, ej = best
            pi = strokes[i]['points'] if ei == 'b' else strokes[i]['points'][::-1]
            pj = strokes[j]['points'] if ej == 'a' else strokes[j]['points'][::-1]
            start = strokes[i]['a'] if ei == 'b' else strokes[i]['b']
            end = strokes[j]['b'] if ej == 'a' else strokes[j]['a']
            joined = dict(points=pi+pj[1:], a=start, b=end, closed=False)
            if start is not None and start == end and len(by_node[node]) == 2:
                joined.update(closed=True, a=None, b=None)
            strokes = [s for k, s in enumerate(strokes) if k not in (i, j)]+[joined]
            merged = True
            break
    return strokes


def _away(points, end, skip=0.0, reach=None):
    """Unit direction leaving the stroke from `end`, ignoring the bent part
    of the skeleton within one stroke width of the junction."""
    seq = points if end == 'a' else points[::-1]
    total = path_length(seq)
    skip = min(skip, total*.4)
    reach = reach or max(12.0, skip*1.5)
    walked, start = 0.0, seq[0]
    previous = seq[0]
    for p in seq[1:]:
        walked += math.dist(previous, p); previous = p
        if walked >= skip:
            start = p
            break
    target = seq[-1]
    walked = 0.0; previous = seq[0]
    for p in seq[1:]:
        walked += math.dist(previous, p); previous = p
        if walked >= skip+reach:
            target = p
            break
    if math.dist(start, target) < 1e-6:
        start, target = seq[0], seq[-1]
    d = math.dist(start, target) or 1.0
    return ((target[0]-start[0])/d, (target[1]-start[1])/d)


def _sections(points, outline, distance, closed, ends):
    """Rails from perpendicular cross-sections clipped to the true outline."""
    def width_at(p):
        x, y = int(round(p[0])), int(round(p[1]))
        return float(distance[min(max(y, 0), distance.shape[0]-1), min(max(x, 0), distance.shape[1]-1)])
    samples = [width_at(p) for p in points]
    typical = float(np.median(samples)) if samples else 1.0
    step = max(1.5, typical*.35)
    points = list(points)
    if not closed:
        # Near a junction the skeleton bends toward the junction centre and
        # cross-sections measure the junction, not the stroke: cut that part.
        for which in (0, 1):
            if ends[which] != 'junction':
                continue
            seq = points if which == 0 else points[::-1]
            reach = width_at(seq[0])*1.1
            if path_length(seq) <= reach*2.5:
                continue
            k = next((i for i, p in enumerate(seq) if math.dist(p, seq[0]) >= reach), 0)
            seq = seq[k:]
            points = seq if which == 0 else seq[::-1]
    line = _smooth(points, 7)
    count = max(3, int(path_length(line)/step)+1)
    line = resample(line, count) if not closed else resample(line+[line[0]], count+1)[:-1]
    fixed = set()
    # Extend open ends: to the outline at terminals; straight into junctions
    # at the stroke's own width, so neighbouring columns overlap cleanly.
    if not closed:
        for which in (0, 1):
            seq = line if which == 0 else line[::-1]
            u = (seq[0][0]-seq[1][0], seq[0][1]-seq[1][1]); d = math.hypot(*u) or 1.0
            u = (u[0]/d, u[1]/d)
            extra = []
            limit = typical*1.0 if ends[which] == 'terminal' else typical*1.6
            t = step*.5
            while t <= limit:
                p = (seq[0][0]+u[0]*t, seq[0][1]+u[1]*t)
                if not outline.contains(Point(p)):
                    break
                extra.append(p); t += step*.5
            if extra:
                if which == 0:
                    line = extra[::-1]+line
                    fixed = {i+len(extra) for i in fixed}
                    if ends[0] == 'junction':
                        fixed |= set(range(len(extra)))
                else:
                    if ends[1] == 'junction':
                        fixed |= set(range(len(line), len(line)+len(extra)))
                    line = line+extra
    cap = typical*1.35
    rails_a, rails_b = [], []
    n = len(line)
    for i, c in enumerate(line):
        # Junction extensions keep the stroke's own width, never the junction's.
        limit = typical if i in fixed else cap
        if closed:
            a0, b0 = line[(i-1) % n], line[(i+1) % n]
            d = math.dist(a0, b0) or 1.0; t = ((b0[0]-a0[0])/d, (b0[1]-a0[1])/d)
        else:
            t = _tangent(line, i)
        nrm = (-t[1], t[0])
        reach = cap*1.6+2
        cut = LineString([(c[0]-nrm[0]*reach, c[1]-nrm[1]*reach), (c[0]+nrm[0]*reach, c[1]+nrm[1]*reach)])
        hit = outline.intersection(cut)
        pieces = [hit] if isinstance(hit, LineString) else [g for g in getattr(hit, 'geoms', []) if isinstance(g, LineString)]
        pieces = [g for g in pieces if not g.is_empty]
        center = Point(c)
        piece = min(pieces, key=lambda g: g.distance(center)) if pieces else None
        if piece is None or piece.distance(center) > 1.5:
            lo, hi = -min(limit, width_at(c) or typical), min(limit, width_at(c) or typical)
        else:
            ends_ = [((x-c[0])*nrm[0]+(y-c[1])*nrm[1]) for x, y in piece.coords]
            lo, hi = min(ends_), max(ends_)
            lo, hi = max(lo, -limit), min(hi, limit)
            if hi-lo < typical*.3:
                lo, hi = -typical*.15, typical*.15
        rails_a.append((c[0]+nrm[0]*hi, c[1]+nrm[1]*hi))
        rails_b.append((c[0]+nrm[0]*lo, c[1]+nrm[1]*lo))
    return _monotone(rails_a, line), _monotone(rails_b, line), typical


def _clean_column(a, b, outline, tolerance=1.0):
    """Keep the longest run of cross-sections that lie inside the outline and
    trim end sections until the ribbon no longer twists (bow-ties)."""
    zone = outline.buffer(tolerance)
    good = [zone.contains(LineString([p, q])) if math.dist(p, q) > 1e-9 else zone.contains(Point(p))
            for p, q in zip(a, b)]
    best, start = (0, 0), None
    for i, ok in enumerate(good+[False]):
        if ok and start is None:
            start = i
        elif not ok and start is not None:
            if i-start > best[1]-best[0]:
                best = (start, i)
            start = None
    a, b = a[best[0]:best[1]], b[best[0]:best[1]]
    budget = len(a)//4
    while len(a) > 4 and budget > 0 and not Polygon(list(a)+list(b)[::-1]).is_valid:
        # Remove whichever end section leaves the straighter ribbon.
        head = Polygon(list(a[1:])+list(b[1:])[::-1]).is_valid
        a, b = (a[1:], b[1:]) if head or len(a) % 2 else (a[:-1], b[:-1])
        budget -= 1
    return a, b


def _split_sharp(points, reach, closed, limit_deg=70):
    """Split a stroke where it turns sharply within one stroke width, so each
    satin column stays roughly straight. Returns [(points, start_kind, end_kind)]."""
    line = _smooth(points, 7)
    total = path_length(line+[line[0]] if closed else line)
    if total < reach*3:
        return None
    step = max(1.0, reach*.25)
    count = max(5, int(total/step))
    line = resample(line+[line[0]], count+1)[:-1] if closed else resample(line, count)
    k = max(2, int(round(reach/step)))
    n = len(line)
    turns = []
    for i in range(n):
        if not closed and (i < k or i >= n-k):
            continue
        p, c, q = line[(i-k) % n], line[i], line[(i+k) % n]
        u = (c[0]-p[0], c[1]-p[1]); v = (q[0]-c[0], q[1]-c[1])
        nu, nv = math.hypot(*u), math.hypot(*v)
        if nu < 1e-9 or nv < 1e-9:
            continue
        angle = math.degrees(math.acos(max(-1, min(1, (u[0]*v[0]+u[1]*v[1])/(nu*nv)))))
        if angle > limit_deg:
            turns.append((angle, i))
    cuts = []
    for angle, i in sorted(turns, reverse=True):
        if all(min(abs(i-j), n-abs(i-j) if closed else abs(i-j)) > 2*k for j in cuts):
            if closed or (i > 2*k and i < n-2*k):
                cuts.append(i)
    if not cuts:
        return None
    cuts.sort()
    if closed:
        pieces = [line[cuts[j]:cuts[(j+1) % len(cuts)]+1] if cuts[(j+1) % len(cuts)] > cuts[j]
                  else line[cuts[j]:]+line[:cuts[(j+1) % len(cuts)]+1] for j in range(len(cuts))]
        return [(piece, 'junction', 'junction') for piece in pieces if len(piece) >= 3]
    bounds = [0]+cuts+[n-1]
    out = []
    for j in range(len(bounds)-1):
        piece = line[bounds[j]:bounds[j+1]+1]
        out.append((piece, 'start' if j == 0 else 'junction', 'end' if j == len(bounds)-2 else 'junction'))
    return out


def _ring_rails(points, outline, width):
    """A pure loop (O, o, 0) sews between its own outer edge and counter edge.
    Only when the whole part lies within the loop's stroke (no tails or bars)."""
    loop = LineString(points+[points[0]])
    for component in polygons(outline):
        if len(component.interiors) != 1 or not component.buffer(1).contains(loop):
            continue
        if component.difference(loop.buffer(width*1.6)).area > component.area*.03:
            return None
        outer = dedupe(LineString(component.exterior.coords).simplify(.4).coords)[:-1]
        inner = dedupe(LineString(component.interiors[0].coords).simplify(.4).coords)[:-1]
        if len(outer) < 4 or len(inner) < 4:
            return None
        def signed(ring):
            return sum(p[0]*q[1]-q[0]*p[1] for p, q in zip(ring, ring[1:]+ring[:1]))
        if (signed(outer) > 0) != (signed(inner) > 0):
            inner = inner[::-1]
        # Both rails start on the same side, nearest the stroke's own start.
        start = points[0]
        i = min(range(len(outer)), key=lambda k: math.dist(outer[k], start))
        outer = outer[i:]+outer[:i]
        j = min(range(len(inner)), key=lambda k: math.dist(inner[k], outer[0]))
        inner = inner[j:]+inner[:j]
        return outer, inner
    return None


def _monotone(rail, line):
    """Fan inside tight curves instead of letting a rail run backwards."""
    out = [rail[0]]
    for i in range(1, len(rail)):
        t = _tangent(line, i)
        step = (rail[i][0]-out[-1][0], rail[i][1]-out[-1][1])
        out.append(rail[i] if step[0]*t[0]+step[1]*t[1] > 0 else out[-1])
    return out


def _dot(component, k):
    """Single column along the long axis of a compact mark (dots, commas)."""
    box = component.minimum_rotated_rectangle
    coords = list(box.exterior.coords)[:4] if hasattr(box, 'exterior') else []
    if len(coords) < 4:
        return None
    edges = [(coords[i], coords[(i+1) % 4]) for i in range(4)]
    long_edge = max(edges, key=lambda e: math.dist(*e))
    u = (long_edge[1][0]-long_edge[0][0], long_edge[1][1]-long_edge[0][1]); d = math.hypot(*u)
    u = (u[0]/d, u[1]/d); nrm = (-u[1], u[0])
    c = component.centroid
    reach = d
    axis = component.intersection(LineString([(c.x-u[0]*reach, c.y-u[1]*reach), (c.x+u[0]*reach, c.y+u[1]*reach)]))
    if axis.is_empty or not isinstance(axis, LineString):
        return None
    p, q = axis.coords[0], axis.coords[-1]
    count = max(4, int(axis.length/1.5))
    a, b = [], []
    for i in range(count):
        t = (i+.5)/count
        center = (p[0]+(q[0]-p[0])*t, p[1]+(q[1]-p[1])*t)
        cut = LineString([(center[0]-nrm[0]*reach, center[1]-nrm[1]*reach), (center[0]+nrm[0]*reach, center[1]+nrm[1]*reach)])
        hit = component.intersection(cut)
        if hit.is_empty:
            continue
        # A cut grazing a corner meets the shape at a single point (no geoms): use its coordinates.
        ends = [((x-center[0])*nrm[0]+(y-center[1])*nrm[1]) for g in getattr(hit, 'geoms', [hit]) for x, y in g.coords]
        a.append((center[0]+nrm[0]*max(ends), center[1]+nrm[1]*max(ends)))
        b.append((center[0]+nrm[0]*min(ends), center[1]+nrm[1]*min(ends)))
    if len(a) < 2:
        return None
    return a, b


@lru_cache(maxsize=512)
def glyph_columns(path, char):
    """Satin columns for one glyph: [(rail_a, rail_b, closed, width)] in em."""
    shape, advance = glyph_outline(path, char)
    if shape.is_empty:
        return (), advance, shape
    return columns_for(shape), advance, shape


def area_columns(shape):
    """Satin columns for any filled shape (e.g. millimetres): the shape is
    scaled to the tracer's working size and the columns scaled back."""
    if not shape.is_valid:
        # Traced pixel outlines can touch themselves; GEOS refuses those in cuts.
        shape = shape.buffer(0)
    left, top, right, bottom = shape.bounds
    size = max(right-left, bottom-top)
    if shape.is_empty or size <= 0:
        return ()
    factor = size/.75
    unit = affine_transform(shape, [1/factor, 0, 0, 1/factor, -left/factor, -top/factor])
    back = lambda p: (p[0]*factor+left, p[1]*factor+top)
    return tuple((tuple(back(p) for p in a), tuple(back(p) for p in b), closed, width*factor)
                 for a, b, closed, width in columns_for(unit))


def columns_for(shape):
    """Core: skeleton strokes -> cross-section satin columns, in sewing order."""
    mask, to_px, to_em = _raster(shape)
    outline = affine_transform(shape, [RESOLUTION, 0, 0, RESOLUTION, to_px(0, 0)[0], to_px(0, 0)[1]])
    if not outline.is_valid:
        outline = outline.buffer(0)
    distance = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)
    skeleton = skeletonize(mask)
    nodes, edges = _graph(skeleton)
    strokes = _strokes(nodes, edges, distance)
    columns = []
    covered = []
    for s in strokes:
        if path_length(s['points']) < 2:
            continue
        degree = lambda node: sum(1 for t in strokes for e in (t['a'], t['b']) if node is not None and e == node)
        ends = ['terminal' if s['a'] is None or degree(s['a']) <= 1 else 'junction',
                'terminal' if s['b'] is None or degree(s['b']) <= 1 else 'junction']
        width_px = max(1.0, float(np.median([distance[min(max(int(round(y)), 0), distance.shape[0]-1),
                                                       min(max(int(round(x)), 0), distance.shape[1]-1)] for x, y in s['points']])))
        covered.append(LineString(s['points']).buffer(width_px))
        if s['closed']:
            ring = _ring_rails(s['points'], outline, width_px)
            if ring is not None:
                columns.append((ring[0], ring[1], True, width_px))
                continue
        pieces = _split_sharp(s['points'], width_px*2, s['closed'])
        if pieces is None:
            a, b, width = _sections(s['points'], outline, distance, s['closed'], ends)
            if not s['closed']:
                a, b = _clean_column(a, b, outline)
            if len(a) >= 2:
                columns.append((a, b, s['closed'], width))
            continue
        for piece, start_kind, end_kind in pieces:
            kinds = [ends[0] if start_kind == 'start' else 'junction', ends[1] if end_kind == 'end' else 'junction']
            a, b, width = _sections(piece, outline, distance, False, kinds)
            a, b = _clean_column(a, b, outline)
            if len(a) >= 2:
                columns.append((a, b, False, width))
    # Components the skeleton missed (dots, tiny marks) get a long-axis column.
    reached = unary_union(covered) if covered else Polygon()
    for component in polygons(outline):
        if reached.is_empty or component.intersection(reached).area < component.area*.5:
            dot = _dot(component, RESOLUTION)
            if dot:
                widths = [math.dist(p, q)/2 for p, q in zip(*dot)]
                columns.append((dot[0], dot[1], False, float(np.median(widths))))
    result = []
    for a, b, closed, width in columns:
        ra = [to_em(*p) for p in a]; rb = [to_em(*p) for p in b]
        if closed:
            ra, rb = ra+[ra[0]], rb+[rb[0]]
        result.append((tuple(ra), tuple(rb), closed, width/RESOLUTION))
    return tuple(_order(result, shape))


def _order(columns, shape):
    """Sewing order and direction: connectors hidden under not-yet-sewn columns."""
    if len(columns) < 2:
        return columns
    ribbons = []
    for a, b, closed, width in columns:
        polygon = Polygon(a, [b]) if closed else Polygon(list(a)+list(b)[::-1])
        ribbons.append(polygon if polygon.is_valid else polygon.buffer(0))
    zone = shape.buffer(1e-3)
    # Letters have a handful of columns: search exhaustively with exact coverage. Areas
    # traced from pictures can have hundreds; there the exhaustive search with a union
    # per step took minutes, so use prepared shapes, a spatial index and fewer starts.
    large = len(columns) > 12
    if large:
        from shapely import STRtree
        from shapely.prepared import prep
        zone_test = prep(zone)
        grown = [r.buffer(1e-3) for r in ribbons]
        tree = STRtree(grown)
    def cost(position, index, reverse, remaining):
        a, b, closed, width = columns[index]
        start = ((a[-1][0]+b[-1][0])/2, (a[-1][1]+b[-1][1])/2) if reverse else ((a[0][0]+b[0][0])/2, (a[0][1]+b[0][1])/2)
        d = math.dist(position, start)
        if d < 1e-6:
            return 0.0
        link = LineString([position, start])
        if large:
            if not zone_test.contains(link):
                return d*20+1
            left = set(remaining)
            covered = any(int(r) in left and grown[int(r)].contains(link) for r in tree.query(link))
            return d*(.2 if covered else 3)
        if not zone.contains(link):
            return d*20+1
        hidden = unary_union([ribbons[r] for r in remaining]) if remaining else Polygon()
        return d*(.2 if not hidden.is_empty and hidden.buffer(1e-3).contains(link) else 3)
    best = None
    for first in (range(len(columns)) if not large else range(1)):
        for reverse_first in (False, True):
            order = [(first, reverse_first)]
            remaining = [i for i in range(len(columns)) if i != first]
            total = 0.0
            while remaining:
                index, reverse = order[-1]
                a, b, _, _ = columns[index]
                position = ((a[0][0]+b[0][0])/2, (a[0][1]+b[0][1])/2) if reverse else ((a[-1][0]+b[-1][0])/2, (a[-1][1]+b[-1][1])/2)
                options = [(cost(position, i, rev, [r for r in remaining if r != i]), i, rev)
                           for i in remaining for rev in (False, True)]
                step, i, rev = min(options)
                total += step; order.append((i, rev)); remaining.remove(i)
            if best is None or total < best[0]:
                best = (total, order)
    out = []
    for index, reverse in best[1]:
        a, b, closed, width = columns[index]
        out.append((a[::-1], b[::-1], closed, width) if reverse else (a, b, closed, width))
    return out
