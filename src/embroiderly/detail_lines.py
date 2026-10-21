"""Mixed mode: thin lines the colour fills cannot hold, sewn over the fills.

Colour preparation turns the picture into flat areas; lines one or two pixels
wide (a skull's face, highlights, pen hatching) are merged away because the
fill converter cannot sew them. Here they are found again in the original
picture with a morphological top-hat (light lines) and black-hat (dark lines),
given the nearest thread of the design's palette, and traced into running
stitches with the line-art router. A line is only kept where its thread
differs from the fill already sewn under it, so it adds visible detail.
"""
import cv2
import numpy as np
from PIL import Image

LEVELS = ('off', 'light', 'all')
CONTRAST = 40        # grey levels a line must stand out from its surroundings
KERNEL_PX = 7        # lines narrower than about half of this are found


def _nearest(colours, palette):
    """Index of the nearest palette colour for each colour (perceptual-ish RGB weights)."""
    w = np.array([.3, .59, .11]) ** .5
    d = (((colours[:, None, :].astype(float) - palette[None, :, :].astype(float)) * w) ** 2).sum(2)
    return d.argmin(1)


def line_layers(source_rgb, prepared_rgb, alpha, level='light'):
    """[(thread hex, mask)] of thin lines that differ from the fill under them."""
    if level not in LEVELS[1:]:
        return []
    lum = cv2.cvtColor(source_rgb, cv2.COLOR_RGB2GRAY)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (KERNEL_PX, KERNEL_PX))
    light = cv2.morphologyEx(lum, cv2.MORPH_TOPHAT, kernel) > CONTRAST
    dark = cv2.morphologyEx(lum, cv2.MORPH_BLACKHAT, kernel) > CONTRAST if level == 'all' else np.zeros_like(light)
    dark &= ~light
    found = (light | dark) & alpha
    if not found.any():
        return []
    # A line one pixel wide is blended with what is around it: take its tone from the
    # lightest (light lines) or darkest (dark lines) pixel next to it.
    small = np.ones((3, 3), np.uint8)
    tone = np.where(light[..., None], cv2.dilate(source_rgb, small), cv2.erode(source_rgb, small))
    palette = np.unique(prepared_rgb[alpha].reshape(-1, 3), axis=0)
    ys, xs = np.nonzero(found)
    thread = _nearest(tone[ys, xs], palette)
    under = _nearest(prepared_rgb[ys, xs], palette)
    keep = thread != under
    layers = []
    for index in np.unique(thread[keep]):
        mask = np.zeros(alpha.shape, bool)
        pick = keep & (thread == index)
        mask[ys[pick], xs[pick]] = True
        if mask.sum() >= 12:
            layers.append(('#%02x%02x%02x' % tuple(int(v) for v in palette[index]), mask))
    return layers


def source_pixels(prepared_path, metadata, shape):
    """The original upload as RGB at the prepared size, or None if it does not line up."""
    name = (metadata or {}).get('source')
    if not name:
        return None
    path = prepared_path.parent / name
    if not path.is_file():
        return None
    with Image.open(path) as image:
        rgb = np.asarray(image.convert('RGB'))
    return rgb if rgb.shape[:2] == shape else None
