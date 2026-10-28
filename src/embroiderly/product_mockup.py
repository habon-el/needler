"""Product mockup: the exported stitches at real size on a simple product shape.

Shapes are drawn in code (millimetres, front view, adult sizes). The design is
rendered from the written machine file only, then placed at its true size, so
the picture shows how big the embroidery looks on the product.
"""
import math
import numpy as np
from PIL import Image, ImageDraw
from .thread_surface import FABRICS, buffers, read_stream, rgb, segments, shade

BACKGROUND = (238, 240, 242)

# Each product: label, box size (mm), shapes (polygon, tone), lines (points, tone),
# placements: key -> (label, centre x, centre y, usual largest width, usual largest height).
_TEE = [(310, 22), (180, 60), (40, 230), (120, 330), (215, 270), (215, 735), (625, 735), (625, 270),
        (720, 330), (800, 230), (660, 60), (530, 22), (490, 80), (420, 100), (350, 80)]
_HOODIE = [(300, 40), (170, 75), (60, 300), (90, 640), (170, 640), (215, 330), (215, 735), (625, 735),
           (625, 330), (670, 640), (750, 640), (780, 300), (670, 75), (540, 40), (490, 100), (420, 125), (350, 100)]
PRODUCTS = {
    'tshirt': dict(label='T-shirt', size=(840, 760),
                   shapes=[(_TEE, 1.0), ([(350, 80), (420, 100), (490, 80), (480, 95), (420, 115), (360, 95)], .82)],
                   lines=[([(215, 270), (215, 735)], .9), ([(625, 270), (625, 735)], .9)],
                   placements={'left_chest': ('Left chest', 530, 230, 100, 100),
                               'centre_chest': ('Centre chest', 420, 290, 280, 280)}),
    'polo': dict(label='Polo shirt', size=(840, 760),
                 shapes=[(_TEE, 1.0), ([(330, 22), (420, 70), (510, 22), (530, 40), (450, 120), (420, 95), (390, 120), (310, 40)], .9),
                         ([(405, 95), (435, 95), (435, 220), (405, 220)], .94)],
                 lines=[([(215, 270), (215, 735)], .9), ([(625, 270), (625, 735)], .9)],
                 placements={'left_chest': ('Left chest', 530, 230, 100, 100),
                             'right_chest': ('Right chest', 310, 230, 100, 100)}),
    'hoodie': dict(label='Hoodie', size=(840, 760),
                   shapes=[(_HOODIE, 1.0), ([(300, 40), (420, 0), (540, 40), (490, 100), (420, 125), (350, 100)], .8),
                           ([(300, 520), (540, 520), (590, 690), (250, 690)], .94)],
                   lines=[([(215, 330), (215, 735)], .9), ([(625, 330), (625, 735)], .9)],
                   placements={'left_chest': ('Left chest', 530, 250, 100, 100),
                               'centre_chest': ('Centre chest', 420, 310, 280, 200)}),
    'cap': dict(label='Cap', size=(320, 220),
                shapes=[([(20, 150)] + [(160 - 140 * math.cos(a), 150 - 135 * math.sin(a)) for a in np.linspace(0, math.pi, 24)] + [(300, 150)], 1.0),
                        ([(10, 150), (310, 150), (290, 205), (30, 205)], .85)],
                lines=[([(160, 15), (160, 150)], .9)],
                placements={'front': ('Front', 160, 90, 110, 55)}),
    'tote': dict(label='Tote bag', size=(420, 640),
                 shapes=[([(10, 200), (410, 200), (410, 630), (10, 630)], 1.0)],
                 lines=[([(110, 200), (110, 60), (150, 20), (270, 20), (310, 60), (310, 200)], .85),
                        ([(10, 230), (410, 230)], .9)],
                 placements={'centre': ('Centre', 210, 410, 280, 280)}),
    'towel': dict(label='Towel', size=(520, 920),
                  shapes=[([(10, 10), (510, 10), (510, 910), (10, 910)], 1.0), ([(10, 820), (510, 820), (510, 860), (10, 860)], .9)],
                  lines=[],
                  placements={'border': ('Above the border', 260, 740, 300, 100),
                              'corner': ('Bottom corner', 400, 740, 100, 100)}),
}


def products():
    """Product names and placements for the studio menu."""
    return [dict(id=key, label=item['label'],
                 placements=[dict(id=p, label=v[0]) for p, v in item['placements'].items()])
            for key, item in PRODUCTS.items()]


def _tone(colour, factor):
    return tuple(int(round(min(255, max(0, c * 255 * factor)))) for c in rgb(colour))


def _draw_product(item, colour, width, height, ppm, origin):
    """Flat product drawing with a darker edge; supersampled for smooth edges."""
    ss = 3
    image = Image.new('RGB', (width * ss, height * ss), BACKGROUND)
    draw = ImageDraw.Draw(image)
    edge = _tone(colour, .72) if rgb(colour).mean() > .25 else _tone('#ffffff', .35)
    point = lambda p: ((origin[0] + p[0] * ppm) * ss, (origin[1] + p[1] * ppm) * ss)
    for polygon, tone in item['shapes']:
        draw.polygon([point(p) for p in polygon], fill=_tone(colour, tone), outline=edge, width=ss * 2)
    for line, tone in item['lines']:
        draw.line([point(p) for p in line], fill=_tone(colour, tone), width=ss * 2)
    return image.resize((width, height), Image.Resampling.LANCZOS)


def render_product(path, product, placement, colour, width=960, height=720, strand=.375,
                   texture='twill', angle=225, neutral=False, palette=None):
    """Return (image, note). The note says when the design is larger than usual for that spot."""
    if product not in PRODUCTS:
        raise ValueError('Choose a product from the list.')
    item = PRODUCTS[product]
    if placement not in item['placements']:
        raise ValueError('Choose a placement for this product.')
    if not (64 <= width <= 1200 and 64 <= height <= 900):
        raise ValueError('Mockup dimensions exceed the bounded render size.')
    if not math.isfinite(strand) or not .1 <= strand <= .8 or not math.isfinite(angle) or not 0 <= angle <= 360 or texture not in FABRICS:
        raise ValueError('Invalid thread appearance settings.')
    rgb(colour)
    plan = read_stream(path, palette)
    points = np.array([p for _, a, b, _ in segments(plan) for p in (a, b)])
    if not len(points):
        raise ValueError('This export has no sewn segments.')
    low, high = points.min(0) - 1, points.max(0) + 1
    size = high - low
    box = np.array(item['size'], float)
    ppm = float(min(width / box[0], height / box[1]) * .94)
    origin = (np.array([width, height]) - box * ppm) / 2
    picture = _draw_product(item, colour, width, height, ppm, origin)
    # Render the stitches sharply on their own, then shrink them to real size on the product.
    detail = float(np.clip(math.sqrt(4_000_000 / (size[0] * size[1])), 2, 8))
    bw, bh = int(math.ceil(size[0] * detail)), int(math.ceil(size[1] * detail))
    offset = (-low * detail).tolist()
    heights, direction, colours, _ = buffers(plan, bw, bh, detail, offset, strand)
    thread = np.rint(shade(heights, direction, colours, detail, offset, colour, texture, angle, neutral) * 255).astype(np.uint8)
    layer = Image.fromarray(np.dstack([thread, np.where(heights > 0, 255, 0).astype(np.uint8)]), 'RGBA')
    target = (max(1, round(size[0] * ppm)), max(1, round(size[1] * ppm)))
    layer = layer.resize(target, Image.Resampling.LANCZOS)
    label, cx, cy, max_w, max_h = item['placements'][placement]
    at = origin + np.array([cx, cy]) * ppm - np.array(target) / 2
    picture.paste(layer, (int(round(at[0])), int(round(at[1]))), layer)
    design_w, design_h = size - 2
    note = None
    if design_w > max_w + .5 or design_h > max_h + .5:
        note = f'{design_w:.0f} × {design_h:.0f} mm is larger than the usual {max_w} × {max_h} mm here.'
    return picture, note
