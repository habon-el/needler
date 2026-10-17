"""Independent coverage from font-authored satin rails, never from output stitches.

Only installed-font SVGs enter here. Unknown geometry fails closed. Font pull
compensation is part of the intended sewing envelope, not a relaxed length gate.
Inkscape's local parser handles curves/transforms; no font code is copied.
"""
import io
import math
import sys
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import Polygon
from shapely.ops import unary_union
from .lettering_rails import column_shape

SVG = '{http://www.w3.org/2000/svg}'
INK = '{http://inkstitch.org/namespace}'
MM = 25.4 / 96
GRID = .04


def outline(svg, *, with_paths=False):
    try:
        import inkex
    except ImportError:
        installed = Path('/usr/share/inkscape/extensions')
        if not (installed/'inkex/__init__.py').is_file():
            raise ValueError('The installed vector parser is unavailable. No lettering was changed.')
        sys.path.append(str(installed))
        import inkex
    from inkex.bezier import cspsubdiv
    root = inkex.load_svg(io.BytesIO(svg.encode())).getroot()
    shapes, envelopes, paths = [], [], {}
    for node in root.iter():
        if not isinstance(node, inkex.PathElement):
            continue
        if str(node.get(INK+'satin_column', '')).lower() != 'true':
            # Font-authored underpaths must lie inside independently defined
            # columns; they may not create their own permission to cross gaps.
            continue
        csp = node.path.transform(node.composed_transform()).to_superpath()
        cspsubdiv(csp, .01/MM)
        parts = [[(float(n[1][0])*MM, float(n[1][1])*MM) for n in part] for part in csp]
        shape = column_shape(parts)
        compensation = [float(v) for v in node.get(INK+'pull_compensation_mm', '0').split()]
        if not compensation or any(not math.isfinite(v) or not 0 <= v <= .5 for v in compensation):
            raise ValueError('This font has unsupported pull compensation.')
        shapes.append(shape)
        envelopes.append(shape.buffer(max(compensation)))
        paths[node.get('id')] = envelopes[-1]
    if not shapes:
        raise ValueError('This font has no verifiable satin columns.')
    if with_paths:
        return paths
    return unary_union(shapes), unary_union(envelopes), len(shapes)


def source_frame(svg):
    """Pin source and engine to one explicit design centre before generation."""
    shape, envelope, columns = outline(svg)
    x, y, right, bottom = shape.bounds
    center = [(x+right)/2, (y+bottom)/2]
    root = ET.fromstring(svg)
    defs = ET.SubElement(root, SVG+'defs')
    ET.SubElement(defs, SVG+'symbol', id='inkstitch_origin')
    ET.SubElement(root, SVG+'use', {'{http://www.w3.org/1999/xlink}href': '#inkstitch_origin',
                                 'x': str(center[0]/MM), 'y': str(center[1]/MM)})
    # Output coordinates are relative to that origin. This grid is independent
    # of the eventual written stitch coordinates and is never derived from them.
    from shapely.affinity import translate
    shape = translate(shape, xoff=-center[0], yoff=-center[1])
    envelope = translate(envelope, xoff=-center[0], yoff=-center[1])
    # Each endpoint snaps at most 0.05 mm per axis on the file grid. Include
    # that bounded quantisation envelope, not arbitrary gaps/letter counters.
    # The same 0.3 mm stitch-length and cut checks still run after writing.
    envelope = envelope.buffer(math.sqrt(2)*.05)
    x, y, right, bottom = envelope.bounds
    origin = [1-x, 1-y]
    width, height = math.ceil((right-x+2)/GRID), math.ceil((bottom-y+2)/GRID)
    if width*height > 16_000_000:
        raise ValueError('This text is too large for the lettering verifier. Use fewer words or lines.')
    plane = Image.new('L', (width, height))
    draw = ImageDraw.Draw(plane)
    polygons = list(envelope.geoms) if envelope.geom_type == 'MultiPolygon' else [envelope]
    def coords(ring):
        return [((px+origin[0])/GRID, (py+origin[1])/GRID) for px, py in ring.coords]
    for polygon in polygons:
        draw.polygon(coords(polygon.exterior), fill=255)
        for hole in polygon.interiors:
            draw.polygon(coords(hole), fill=0)
    return ET.tostring(root, encoding='unicode'), np.asarray(plane)>127, origin, columns
