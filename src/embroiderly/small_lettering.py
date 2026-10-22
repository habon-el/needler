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


def size_limits(font, puff=False):
    """Editable tenth-mm range inside the font's supported scale range. Puff
    letters go larger: their strokes must be as wide as the foam is thick."""
    return (math.ceil(font['size'] * font['min_scale'] * 10) / 10,
            math.floor(font['size'] * font['puff_max_scale' if puff else 'max_scale'] * 10) / 10)


def puff_foam(body):
    foam=body.get('puff_foam_mm',3)
    if foam not in (2,3,2.0,3.0):raise ValueError('Choose 2 mm or 3 mm puff foam.')
    return float(foam)


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
    minimum, maximum = size_limits(font, body.get('puff') is True)
    if not math.isfinite(height) or not minimum <= height <= maximum:
        raise ValueError(f'Choose a font size from {minimum:g} to {maximum:g} mm for this font. Your words are unchanged.')
    scale=round(height/font['size']*100)
    # Rounded: 1.1*100 is 110.00000000000001 in floating point, which refused the smallest size.
    if not round(font['min_scale']*100)<=scale<=round(font['puff_max_scale' if body.get('puff') is True else 'max_scale']*100):
        raise ValueError('That size is outside this embroidery font’s supported range.')
    align=body.get('align','left')
    if align not in ('left','center','right'):raise ValueError('Choose left, centre or right alignment.')
    return text,font,scale,align


def generate(body, *, native=False):
    text,font,scale,align=validate(body)
    vector=embroidery_fonts.layout(text,font['key'],scale,align,puff=body.get('puff') is True,
                                   foam_mm=puff_foam(body))
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
