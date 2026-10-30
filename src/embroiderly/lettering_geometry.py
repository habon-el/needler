"""Independent coverage from font-authored satin rails, never from output stitches.

Only embroidery-font SVGs enter here. Unknown geometry fails closed. Font pull
compensation is part of the intended sewing envelope, not a relaxed length gate.
Our own SVG reader handles curves and transforms.
"""
import math
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
MAX_GRID = .1   # coarsest verifier raster, for the largest lettering


def outline(svg, *, with_paths=False, raw=False):
    """raw: with_paths gives each column's own area, without its pull compensation."""
    from . import svg_geometry
    try:
        root = svg_geometry.load(svg)
    except ET.ParseError:
        raise ValueError('The lettering vectors could not be read. No lettering was changed.') from None
    shapes, envelopes, paths = [], [], {}
    for node, subpaths, _, _ in svg_geometry.elements(root, tolerance=.01/MM):
        if svg_geometry.local(node.tag) != 'path':
            continue
        if str(node.get(INK+'letter_fill', '')).lower() == 'true':
            # Big letters sewn as a tatami fill (embroidery_fonts.layout): the
            # letter's own outline, holes kept; the fill stays inside it.
            from .stitch_fills import fill_shape
            parts = [[(float(x)*MM, float(y)*MM) for x, y in points] for points, _ in subpaths]
            shape = fill_shape([(part, True) for part in parts], 'evenodd')
            if shape.is_empty:
                continue
            shapes.append(shape)
            envelopes.append(shape.buffer(.05))
            paths[node.get('id')] = envelopes[-1]
            continue
        if str(node.get(INK+'satin_column', '')).lower() != 'true':
            # Font-authored underpaths must lie inside independently defined
            # columns; they may not create their own permission to cross gaps.
            continue
        parts = [[(float(x)*MM, float(y)*MM) for x, y in points] for points, _ in subpaths]
        if node.get(INK+'satin_pairs') == 'indexed' and len(parts) == 2 and len(parts[0]) == len(parts[1]) >= 2:
            # Matched cross-sections: each stitch joins section i to section i
            # or i+1, so the sewn area is the chain of neighbouring-section hulls.
            from shapely.geometry import MultiPoint
            a, b = parts
            shape = unary_union([MultiPoint([a[i], a[i+1], b[i+1], b[i]]).convex_hull for i in range(len(a)-1)])
        else:
            shape = column_shape(parts)
        compensation = [float(v) for v in node.get(INK+'pull_compensation_mm', '0').split()]
        if not compensation or any(not math.isfinite(v) or not 0 <= v <= .5 for v in compensation):
            raise ValueError('This font has unsupported pull compensation.')
        shapes.append(shape)
        envelopes.append(shape.buffer(max(compensation)))
        paths[node.get('id')] = shape if raw else envelopes[-1]
    if not shapes:
        raise ValueError('This font has no verifiable satin columns.')
    if with_paths:
        return paths
    return unary_union(shapes), unary_union(envelopes), len(shapes)


def source_frame(svg, with_grid=False):
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
    # Plus one raster cell: filling the polygon on the GRID raster can move its
    # edge inward by up to a cell, which must not eat the quantisation allowance.
    # Big lettering (jacket backs) gets a coarser raster, never coarser than
    # 0.1 mm, so the verifier stays within 16 million cells up to ~400 x 400 mm.
    x, y, right, bottom = envelope.bounds
    grid = GRID
    while grid < MAX_GRID-1e-9 and (right-x+2+2*(.08+MAX_GRID))*(bottom-y+2+2*(.08+MAX_GRID))/grid**2 > 16_000_000:
        grid = round(grid+.01, 2)
    envelope = envelope.buffer(math.sqrt(2)*.05+grid)
    x, y, right, bottom = envelope.bounds
    origin = [1-x, 1-y]
    width, height = math.ceil((right-x+2)/grid), math.ceil((bottom-y+2)/grid)
    if width*height > 16_000_000:
        raise ValueError('This text is larger than about 400 × 400 mm, more than any embroidery hoop. '
                         'Use a smaller height, fewer words or more lines.')
    plane = Image.new('L', (width, height))
    draw = ImageDraw.Draw(plane)
    polygons = list(envelope.geoms) if envelope.geom_type == 'MultiPolygon' else [envelope]
    def coords(ring):
        return [((px+origin[0])/grid, (py+origin[1])/grid) for px, py in ring.coords]
    for polygon in polygons:
        draw.polygon(coords(polygon.exterior), fill=255)
        for hole in polygon.interiors:
            draw.polygon(coords(hole), fill=0)
    result = (ET.tostring(root, encoding='unicode'), np.asarray(plane)>127, origin, columns)
    return result+(grid,) if with_grid else result
