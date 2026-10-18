"""Minimal, dependency-free SVG geometry reader for our own generated documents.

Supports path data (M L H V C S Q T A Z, absolute and relative), basic shapes,
nested group transforms and document units. Curves are flattened to polylines
with an explicit tolerance in user units. No scripts, CSS or external references
are interpreted: this is geometry only.
"""
import math
import re
import xml.etree.ElementTree as ET

SVG = '{http://www.w3.org/2000/svg}'
XLINK = '{http://www.w3.org/1999/xlink}'
PX_MM = 25.4/96
UNITS = {'': PX_MM, 'px': PX_MM, 'mm': 1.0, 'cm': 10.0, 'in': 25.4, 'pt': 25.4/72, 'pc': 25.4/6}
IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
NAMED = {'black': '#000000', 'white': '#ffffff', 'red': '#ff0000', 'green': '#008000', 'blue': '#0000ff',
         'yellow': '#ffff00', 'gray': '#808080', 'grey': '#808080', 'orange': '#ffa500', 'purple': '#800080'}
_TOKEN = re.compile(r'[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?')
_NUMBER = re.compile(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?')


def local(tag):
    return tag.split('}')[-1] if isinstance(tag, str) else ''


def multiply(a, b):
    """Compose affine transforms: apply b first, then a."""
    return (a[0]*b[0]+a[2]*b[1], a[1]*b[0]+a[3]*b[1],
            a[0]*b[2]+a[2]*b[3], a[1]*b[2]+a[3]*b[3],
            a[0]*b[4]+a[2]*b[5]+a[4], a[1]*b[4]+a[3]*b[5]+a[5])


def apply(m, point):
    x, y = point
    return (m[0]*x+m[2]*y+m[4], m[1]*x+m[3]*y+m[5])


def parse_transform(text):
    result = IDENTITY
    for name, args in re.findall(r'(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)', text or ''):
        v = [float(n) for n in _NUMBER.findall(args)]
        if name == 'matrix' and len(v) == 6:
            m = tuple(v)
        elif name == 'translate' and v:
            m = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif name == 'scale' and v:
            m = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == 'rotate' and v:
            a = math.radians(v[0]); c, s = math.cos(a), math.sin(a)
            m = (c, s, -s, c, 0, 0)
            if len(v) == 3:
                m = multiply(multiply((1, 0, 0, 1, v[1], v[2]), m), (1, 0, 0, 1, -v[1], -v[2]))
        elif name == 'skewX' and v:
            m = (1, 0, math.tan(math.radians(v[0])), 1, 0, 0)
        elif name == 'skewY' and v:
            m = (1, math.tan(math.radians(v[0])), 0, 1, 0, 0)
        else:
            raise ValueError('Unsupported SVG transform.')
        result = multiply(result, m)
    return result


def length_mm(value):
    match = re.fullmatch(r'\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*([a-z%]*)\s*', value or '')
    if not match or match[2] not in UNITS:
        return None
    return float(match[1])*UNITS[match[2]]


def document_scale(root):
    """Millimetres per user unit, following width/viewBox like a renderer."""
    box = [float(v) for v in _NUMBER.findall(root.get('viewBox', ''))]
    width = length_mm(root.get('width')) if root.get('width') else None
    if len(box) == 4 and box[2] > 0:
        if width is not None:
            return width/box[2]
        return PX_MM
    return PX_MM


def _cubic(p0, p1, p2, p3, tolerance):
    # Control-polygon length bounds the subdivision count; deterministic output.
    size = math.dist(p0, p1)+math.dist(p1, p2)+math.dist(p2, p3)
    n = max(1, min(256, int(math.ceil(math.sqrt(size/max(tolerance, 1e-9))))))
    out = []
    for i in range(1, n+1):
        t = i/n; u = 1-t
        out.append((u**3*p0[0]+3*u*u*t*p1[0]+3*u*t*t*p2[0]+t**3*p3[0],
                    u**3*p0[1]+3*u*u*t*p1[1]+3*u*t*t*p2[1]+t**3*p3[1]))
    return out


def _quadratic(p0, p1, p2, tolerance):
    return _cubic(p0, (p0[0]+2/3*(p1[0]-p0[0]), p0[1]+2/3*(p1[1]-p0[1])),
                  (p2[0]+2/3*(p1[0]-p2[0]), p2[1]+2/3*(p1[1]-p2[1])), p2, tolerance)


def _arc(p0, rx, ry, phi, large, sweep, p1, tolerance):
    if p0 == p1:
        return []
    rx, ry = abs(rx), abs(ry)
    if rx < 1e-12 or ry < 1e-12:
        return [p1]
    phi = math.radians(phi); c, s = math.cos(phi), math.sin(phi)
    dx, dy = (p0[0]-p1[0])/2, (p0[1]-p1[1])/2
    x1, y1 = c*dx+s*dy, -s*dx+c*dy
    scale = x1*x1/(rx*rx)+y1*y1/(ry*ry)
    if scale > 1:
        rx *= math.sqrt(scale); ry *= math.sqrt(scale)
    num = rx*rx*ry*ry-rx*rx*y1*y1-ry*ry*x1*x1
    factor = math.sqrt(max(0, num/(rx*rx*y1*y1+ry*ry*x1*x1)))
    if large == sweep:
        factor = -factor
    cx1, cy1 = factor*rx*y1/ry, -factor*ry*x1/rx
    cx = c*cx1-s*cy1+(p0[0]+p1[0])/2
    cy = s*cx1+c*cy1+(p0[1]+p1[1])/2
    def angle(ux, uy, vx, vy):
        a = math.atan2(ux*vy-uy*vx, ux*vx+uy*vy)
        return a
    start = angle(1, 0, (x1-cx1)/rx, (y1-cy1)/ry)
    delta = angle((x1-cx1)/rx, (y1-cy1)/ry, (-x1-cx1)/rx, (-y1-cy1)/ry)
    if not sweep and delta > 0:
        delta -= 2*math.pi
    elif sweep and delta < 0:
        delta += 2*math.pi
    radius = max(rx, ry)
    step = 2*math.acos(max(-1, min(1, 1-tolerance/max(radius, 1e-9))))
    n = max(1, min(512, int(math.ceil(abs(delta)/max(step, 1e-3)))))
    out = []
    for i in range(1, n+1):
        t = start+delta*i/n
        x, y = rx*math.cos(t), ry*math.sin(t)
        out.append((c*x-s*y+cx, s*x+c*y+cy))
    out[-1] = p1
    return out


def parse_path(d, tolerance=0.05):
    """Return [(points, closed)] subpaths in user units."""
    tokens = _TOKEN.findall(d or '')
    paths, points = [], []
    current = start = (0.0, 0.0)
    command = None; previous_control = None; previous_command = None
    i = 0

    def number():
        nonlocal i
        if i >= len(tokens) or tokens[i].isalpha():
            raise ValueError('Malformed SVG path data.')
        i += 1
        return float(tokens[i-1])

    def finish(closed):
        nonlocal points
        if len(points) >= 2 or (points and closed):
            paths.append((points, closed))
        points = []

    while i < len(tokens):
        if tokens[i].isalpha():
            command = tokens[i]; i += 1
        elif command is None:
            raise ValueError('Malformed SVG path data.')
        relative = command.islower(); kind = command.upper()
        base = current if relative else (0.0, 0.0)
        if kind == 'Z':
            if points:
                if math.dist(points[-1], start) > 1e-12:
                    points.append(start)
                finish(True)
            current = start; previous_control = None; previous_command = 'Z'
            continue
        if kind == 'M':
            finish(False)
            current = (base[0]+number(), base[1]+number()); start = current
            points = [current]
            command = 'l' if relative else 'L'
            previous_control = None; previous_command = 'M'
            continue
        if not points:
            points = [current]
        if kind == 'L':
            current = (base[0]+number(), base[1]+number()); points.append(current); previous_control = None
        elif kind == 'H':
            current = ((current[0] if relative else 0)+number(), current[1]); points.append(current); previous_control = None
        elif kind == 'V':
            current = (current[0], (current[1] if relative else 0)+number()); points.append(current); previous_control = None
        elif kind in 'CS':
            if kind == 'C':
                c1 = (base[0]+number(), base[1]+number())
            else:
                c1 = (2*current[0]-previous_control[0], 2*current[1]-previous_control[1]) \
                    if previous_control and previous_command in 'CS' else current
            c2 = (base[0]+number(), base[1]+number()); end = (base[0]+number(), base[1]+number())
            points.extend(_cubic(current, c1, c2, end, tolerance))
            previous_control = c2; current = end
        elif kind in 'QT':
            if kind == 'Q':
                c1 = (base[0]+number(), base[1]+number())
            else:
                c1 = (2*current[0]-previous_control[0], 2*current[1]-previous_control[1]) \
                    if previous_control and previous_command in 'QT' else current
            end = (base[0]+number(), base[1]+number())
            points.extend(_quadratic(current, c1, end, tolerance))
            previous_control = c1; current = end
        elif kind == 'A':
            rx, ry, phi = number(), number(), number()
            large, sweep = number() != 0, number() != 0
            end = (base[0]+number(), base[1]+number())
            points.extend(_arc(current, rx, ry, phi, large, sweep, end, tolerance))
            current = end; previous_control = None
        else:
            raise ValueError('Unsupported SVG path command.')
        previous_command = kind
    finish(False)
    return paths


def shape_paths(node, tolerance=0.05):
    """Subpaths for a single element in its own user space."""
    kind = local(node.tag)
    f = lambda name, default=0.0: float(node.get(name, default) or default)
    if kind == 'path':
        return parse_path(node.get('d', ''), tolerance)
    if kind in ('circle', 'ellipse'):
        cx, cy = f('cx'), f('cy')
        rx = f('r') if kind == 'circle' else f('rx'); ry = f('r') if kind == 'circle' else f('ry')
        if rx <= 0 or ry <= 0:
            return []
        n = max(8, min(256, int(math.ceil(2*math.pi/max(2*math.acos(max(-1, 1-tolerance/max(rx, ry))), 1e-3)))))
        pts = [(cx+rx*math.cos(2*math.pi*i/n), cy+ry*math.sin(2*math.pi*i/n)) for i in range(n)]
        return [(pts+[pts[0]], True)]
    if kind == 'rect':
        x, y, w, h = f('x'), f('y'), f('width'), f('height')
        if w <= 0 or h <= 0:
            return []
        return [([(x, y), (x+w, y), (x+w, y+h), (x, y+h), (x, y)], True)]
    if kind == 'line':
        return [([(f('x1'), f('y1')), (f('x2'), f('y2'))], False)]
    if kind in ('polyline', 'polygon'):
        v = [float(n) for n in _NUMBER.findall(node.get('points', ''))]
        pts = list(zip(v[0::2], v[1::2]))
        if len(pts) < 2:
            return []
        closed = kind == 'polygon'
        return [(pts+[pts[0]] if closed else pts, closed)]
    return []


def style(node):
    values = {}
    for name in ('fill', 'stroke', 'stroke-width', 'fill-rule', 'display', 'visibility'):
        if node.get(name) is not None:
            values[name] = node.get(name).strip()
    for part in (node.get('style') or '').split(';'):
        if ':' in part:
            key, value = part.split(':', 1)
            values[key.strip()] = value.strip()
    return values


def colour(value):
    """Normalise a paint value to #rrggbb, or None for no paint."""
    if value is None:
        return None
    value = value.strip().lower()
    if value in ('none', 'transparent', ''):
        return None
    value = NAMED.get(value, value)
    if re.fullmatch(r'#[0-9a-f]{3}', value):
        return '#'+''.join(c*2 for c in value[1:])
    if re.fullmatch(r'#[0-9a-f]{6}', value):
        return value
    match = re.fullmatch(r'rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', value)
    if match:
        return '#%02x%02x%02x' % tuple(min(255, int(v)) for v in match.groups())
    if value.startswith('url('):
        return '#000000'
    return None


DRAWABLE = ('path', 'circle', 'ellipse', 'rect', 'line', 'polyline', 'polygon')
SKIPPED = ('defs', 'symbol', 'metadata', 'title', 'desc', 'style', 'script', 'clipPath', 'mask', 'pattern')


def elements(root, tolerance=0.05):
    """Yield (node, transformed subpaths, inherited style) in document order."""
    def walk(node, matrix, inherited):
        kind = local(node.tag)
        if kind in SKIPPED:
            return
        merged = {**inherited, **style(node)}
        if merged.get('display') == 'none':
            return
        m = multiply(matrix, parse_transform(node.get('transform')))
        if kind in DRAWABLE:
            # Scale the flattening tolerance so it stays constant after transforms.
            det = abs(m[0]*m[3]-m[1]*m[2]) or 1.0
            local_tolerance = tolerance/math.sqrt(det)
            paths = [([apply(m, p) for p in pts], closed) for pts, closed in shape_paths(node, local_tolerance)]
            yield node, paths, merged, m
            return
        for child in node:
            yield from walk(child, m, merged)
    for child in root:
        yield from walk(child, IDENTITY, {})


def origin(root):
    """Explicit origin command (<use href="#inkstitch_origin">) in user units."""
    for node in root.iter():
        if local(node.tag) != 'use':
            continue
        href = node.get(XLINK+'href') or node.get('href') or ''
        if href.lstrip('#') in ('inkstitch_origin', 'needler_origin'):
            m = parse_transform(node.get('transform'))
            return apply(m, (float(node.get('x', 0) or 0), float(node.get('y', 0) or 0)))
    return None


def load(source):
    if isinstance(source, bytes):
        return ET.fromstring(source)
    if isinstance(source, str) and source.lstrip().startswith('<'):
        return ET.fromstring(source)
    return ET.parse(source).getroot()
