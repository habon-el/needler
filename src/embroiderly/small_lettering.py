"""Direct embroidery-font generation, independent of picture cleanup.

This produces vector source and a generator plan, NOT release-approved files.
Font size is the embroidery font's nominal height (capital H), not an inferred
cap height of arbitrary artwork. Fonts are Needler's own satin conversions of
bundled open-licence TrueType fonts; no external program is involved.
"""
import math
import unicodedata

from . import embroidery_fonts

FONTS = tuple(embroidery_fonts.FONTS)


def fonts():
    return embroidery_fonts.catalogue()


def size_limits(font):
    """Editable tenth-mm range inside the font's supported scale range."""
    return (math.ceil(font['size'] * font['min_scale'] * 10) / 10,
            math.floor(font['size'] * font['max_scale'] * 10) / 10)


def validate(body):
    if not isinstance(body,dict):raise ValueError('Expected lettering settings.')
    text=body.get('text')
    if not isinstance(text,str) or not text.strip() or len(text)>200:
        raise ValueError('Enter 1–200 characters.')
    if len(text.splitlines())>5:raise ValueError('Use at most five lines.')
    text=unicodedata.normalize('NFC',text).replace('\r\n','\n')
    font=fonts().get(body.get('font'))
    if font is None:raise ValueError('Select an installed small embroidery font.')
    missing=sorted(set(text)-set(font['glyphs'])-{' ','\n'})
    if missing:raise ValueError('This embroidery font does not contain: '+' '.join(missing))
    height=float(body.get('height_mm',5))
    minimum, maximum = size_limits(font)
    if not math.isfinite(height) or not minimum <= height <= maximum:
        raise ValueError(f'Choose a font size from {minimum:g} to {maximum:g} mm for this font. Your words are unchanged.')
    scale=round(height/font['size']*100)
    if not font['min_scale']*100<=scale<=font['max_scale']*100:
        raise ValueError('That size is outside this embroidery font’s supported range.')
    align=body.get('align','left')
    if align not in ('left','center','right'):raise ValueError('Choose left, centre or right alignment.')
    return text,font,scale,align


def generate(body, *, native=False):
    text,font,scale,align=validate(body)
    vector=embroidery_fonts.layout(text,font['key'],scale,align)
    coverage={}
    if native:
        from .lettering_geometry import source_frame
        from .lettering_source import route_font
        vector,cuts=route_font(vector)
        vector,mask,origin,columns=source_frame(vector)
        coverage=dict(mask=mask,origin=origin,columns=columns,added_cuts=cuts)
    from .lettering_rebuild import rebuild
    rebuilt_svg, rebuilt_plan, report = rebuild(vector)
    report.update(coverage)
    return dict(svg=rebuilt_svg,plan=rebuilt_plan,rebuild_report=report,
                text=text,font=font['name'],nominal_height_mm=font['size']*scale/100,
                requested_height_mm=float(body.get('height_mm',5)),release_approved=False)
