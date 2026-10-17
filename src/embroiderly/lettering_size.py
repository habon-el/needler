"""Source-font measurements for typed artwork, not a sewability certificate.

Use the saved vector recipe to measure a reference capital H at the current
canvas scale. Never infer a letter's height by dividing a multi-line block.
Selection, cropping or per-piece transforms can invalidate this estimate.
"""
import json
import math
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen


def source_metrics(recipe):
    from .lettering import catalogue, outline
    normalized, _, size = outline(recipe)
    font_path = catalogue()[normalized['font']]['path']
    with TTFont(font_path) as font:
        glyphs = font.getGlyphSet()
        cmap = font.getBestCmap()
        if ord('H') not in cmap:
            raise ValueError('No reference capital H in this font.')
        cap = BoundsPen(glyphs)
        glyphs[cmap[ord('H')]].draw(cap)
        # Match outline()'s row origins, including blank lines and descenders.
        from fontTools.pens.transformPen import TransformPen
        bounds = BoundsPen(glyphs)
        for row, line in enumerate(normalized['text'].split('\n')):
            for char in line:
                glyphs[cmap[ord(char)]].draw(TransformPen(bounds, (1,0,0,-1,0,row*font['head'].unitsPerEm*1.4)))
        block_units = bounds.bounds[3]-bounds.bounds[1]
        cap_units = cap.bounds[3]-cap.bounds[1]
    return dict(capital_per_canvas_mm=cap_units/(block_units*1.08),
                line_count=len(normalized['text'].split('\n')),
                basis='Source font capital H, before stitch generation')


def saved_metrics(decisions, name):
    """Missing/old/unavailable fonts must not break non-lettering artwork."""
    path = Path(decisions)/(Path(name).name+'.lettering.json')
    if not path.is_file():
        return None
    try:
        return source_metrics(json.loads(path.read_text()))
    except (ValueError, TypeError, KeyError, OSError):
        return dict(unavailable=True, basis='Source font measurement unavailable')


def width_fit(width_mm, available_mm):
    """Measure fit; never scale, reflow, delete or crop the customer's words."""
    target = float(available_mm)
    if not math.isfinite(target) or not 5 <= target <= 400:
        raise ValueError('Available width must be 5–400 mm.')
    return dict(available_width_mm=target, actual_width_mm=width_mm,
                fits=width_mm <= target + 1e-8,
                overflow_mm=round(max(0, width_mm-target), 2),
                resized=False)
