"""Rasterise our own simple SVG documents (filled paths) without external tools.

Nonzero and even-odd fill rules are honoured by accumulating signed coverage per
contour. Edges are antialiased by supersampling. Only geometry and solid paint
are read, never scripts, images, fonts or remote references.
"""
import math
import numpy as np
from PIL import Image, ImageDraw
from . import svg_geometry as sg


def _box(root):
    box = [float(v) for v in sg._NUMBER.findall(root.get('viewBox', ''))]
    if len(box) == 4 and box[2] > 0 and box[3] > 0:
        return box
    width = sg.length_mm(root.get('width') or '') or 0
    height = sg.length_mm(root.get('height') or '') or 0
    if width <= 0 or height <= 0:
        raise ValueError('The vector artwork has no size.')
    return [0.0, 0.0, width/sg.PX_MM, height/sg.PX_MM]


def size_for(root, width=None, height=None):
    x, y, w, h = _box(root)
    if width:
        return int(width), max(1, int(round(width*h/w)))
    return max(1, int(round(height*w/h))), int(height)


def render(source, width=None, height=None, supersample=4, background=(0, 0, 0, 0)):
    """RGBA image of the page area."""
    root = sg.load(source)
    x0, y0, w, h = _box(root)
    out_w, out_h = size_for(root, width, height)
    big_w, big_h = out_w*supersample, out_h*supersample
    sx, sy = big_w/w, big_h/h
    canvas = Image.new('RGBA', (big_w, big_h), background)
    tolerance = .25/max(sx, sy)
    for node, paths, style, matrix in sg.elements(root, tolerance=tolerance):
        if not paths:
            continue
        paint = sg.colour(style.get('fill', '#000000')) if sg.local(node.tag) not in ('line', 'polyline') else None
        if paint is not None:
            _fill(canvas, paths, style, paint, (x0, y0), (sx, sy))
        # SVG paints the outline on top of the fill.
        stroke = sg.colour(style.get('stroke'))
        if stroke:
            _stroke(canvas, paths, style, matrix, stroke, (x0, y0), (sx, sy))
    if supersample > 1:
        canvas = canvas.resize((out_w, out_h), Image.Resampling.BOX)
    return canvas


def _fill(canvas, paths, style, paint, offset, scale):
    (x0, y0), (sx, sy) = offset, scale
    big_w, big_h = canvas.size
    rule = style.get('fill-rule', 'nonzero')
    winding = np.zeros((big_h, big_w), np.int32)
    for points, _ in paths:
        if len(points) < 3:
            continue
        pixels = [((px-x0)*sx, (py-y0)*sy) for px, py in points]
        signed = sum(a[0]*b[1]-b[0]*a[1] for a, b in zip(pixels, pixels[1:]+pixels[:1]))
        if abs(signed) < 1e-9:
            continue
        layer = Image.new('L', (big_w, big_h), 0)
        ImageDraw.Draw(layer).polygon(pixels, fill=1)
        mask = np.asarray(layer, np.int32)
        if rule == 'evenodd':
            winding ^= mask
        else:
            winding += mask if signed > 0 else -mask
    covered = (winding != 0) if rule != 'evenodd' else (winding & 1).astype(bool)
    try:
        opacity = float(style.get('fill-opacity', style.get('opacity', 1)) or 1)
    except ValueError:
        opacity = 1.0
    alpha = Image.fromarray((covered*int(255*max(0, min(1, opacity)))).astype(np.uint8), 'L')
    rgb = tuple(int(paint[i:i+2], 16) for i in (1, 3, 5))
    canvas.paste(Image.new('RGBA', (big_w, big_h), rgb+(255,)), (0, 0), alpha)


def _stroke(canvas, paths, style, matrix, paint, offset, scale):
    try:
        width = float(sg._NUMBER.findall(style.get('stroke-width', '1'))[0])
    except (IndexError, ValueError):
        width = 1.0
    # Stroke width follows the element's transform like the outline does.
    width *= math.sqrt(abs(matrix[0]*matrix[3]-matrix[1]*matrix[2])) or 1.0
    pixels = max(1, int(round(width*(scale[0]+scale[1])/2)))
    layer = Image.new('L', canvas.size, 0)
    draw = ImageDraw.Draw(layer)
    for points, closed in paths:
        if len(points) < 2:
            continue
        line = [((px-offset[0])*scale[0], (py-offset[1])*scale[1]) for px, py in points]
        draw.line(line, fill=255, width=pixels, joint='curve')
        r = pixels/2
        for x, y in (line[0], line[-1]):
            draw.ellipse((x-r, y-r, x+r, y+r), fill=255)
    rgb = tuple(int(paint[i:i+2], 16) for i in (1, 3, 5))
    canvas.paste(Image.new('RGBA', canvas.size, rgb+(255,)), (0, 0), layer)


def svg_upload(data, longest=768):
    # 768 px matches preparation's working size, so the image is never resampled.
    """Validate an uploaded SVG and render it for artwork preparation."""
    import xml.etree.ElementTree as ET
    head = data[:4096].lower()
    if b'<!doctype' in head or b'<!entity' in data.lower():
        raise ValueError('SVG files with document type or entity declarations are not supported. Export a plain SVG.')
    try:
        root = sg.load(data)
    except ET.ParseError:
        raise ValueError('This SVG file could not be read. Export it again as a plain SVG.') from None
    if sg.local(root.tag) != 'svg':
        raise ValueError('This file is not an SVG drawing.')
    try:
        x, y, w, h = _box(root)
    except ValueError:
        raise ValueError('The SVG has no width, height or viewBox. Set a page size and export again.') from None
    width, height = (longest, None) if w >= h else (None, longest)
    # Exact flat colours (no edge blending): a vector logo has no in-between
    # shades, and blended edge pixels would become tiny unsewable regions.
    image = render(data, width=width, height=height, supersample=1)
    if image.getchannel('A').getextrema()[1] == 0:
        raise ValueError('Nothing visible was found in this SVG. Text must be converted to outlines (paths) before upload.')
    return image, data


def render_png(source, path, width=None, height=None):
    render(source, width, height).save(path)
    return path
