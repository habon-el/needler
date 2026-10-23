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


def _bounds(text, font, puff, foam):
    """Measurements of the words, the satin edge, and the capital heights the
    font allows for them (for puff: every stroke wide enough for the foam)."""
    from .stitch_engine import PUFF_MAX_MM, puff_min_mm
    m=embroidery_fonts.text_metrics(text,font['key'])
    if m is None:raise ValueError('Enter some letters to stitch.')
    # The satin's outer edge sits this far outside the letter (embroidery_fonts.layout).
    pull=((.35 if foam<2.5 else .45)-.05) if puff else font['pull_mm']
    low=font['size']*font['min_scale'];high=font['size']*font['puff_max_scale' if puff else 'max_scale']
    if puff:low=max(low,puff_min_mm(foam)/m['thin']);high=min(high,PUFF_MAX_MM/m['wide'])
    return m,pull,low,high


# Above the satin range letters are sewn as tatami fill (embroidery_fonts.layout),
# up to this capital height; the fill stays inside the letter (no satin edge).
FILL_MAX_CAP_MM=300.0


def height_range(text, font, puff=False, foam=3.0):
    """Stitched heights (mm) these words can have in this font; None when puff cannot work."""
    m,pull,low,high=_bounds(text,font,puff,foam)
    if low>high:return None
    top=m['height']*high+2*pull if puff else max(m['height']*high+2*pull,m['height']*FILL_MAX_CAP_MM)
    return math.ceil((m['height']*low+2*pull)*10)/10,math.floor(top*10)/10


def scale_for(text, font, height, puff=False, foam=3.0):
    """The height entered is the height of the stitched words (top of the tallest
    letter to the bottom of the lowest, all lines), not the font's capital
    height: find the font scale that gives it, inside the font's range and,
    for 3D puff, where every stroke is wide enough for the foam."""
    m,pull,low,high=_bounds(text,font,puff,foam)
    if low>high:
        raise ValueError(f'These words in {font["name"]} cannot be 3D puff on {foam:g} mm foam at any height: '
                         f'the thinnest strokes are too thin next to the widest. Try a bold block font such as '
                         f'Russo One or Bungee{", or 2 mm foam" if foam>2 else ""}.')
    cap=(height-2*pull)/m['height']
    if not puff and cap>high+1e-9 and height/m['height']<=FILL_MAX_CAP_MM+1e-9:
        # Too wide for satin: tatami fill letters, no satin edge.
        return height/m['height']/font['size']*100
    if puff:
        # Wide puff strokes get less edge so no stitch passes 6.9 mm (stitch_satin._puff_satin).
        for _ in range(3):
            edge=max(0.0,min(pull,(6.9-.05-m['wide']*cap)/2));cap=(height-2*edge)/m['height']
    if not low-1e-9<=cap<=high+1e-9:
        lo,hi=height_range(text,font,puff,foam)
        raise ValueError(f'Choose a height from {lo:g} to {hi:g} mm for these words in {font["name"]}'
                         +(f' with 3D puff on {foam:g} mm foam' if puff else '')+'. Your words are unchanged.')
    return cap/font['size']*100


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
    if not math.isfinite(height) or height<=0:
        raise ValueError('Enter the height of your stitched words in mm.')
    scale=scale_for(text,font,height,body.get('puff') is True,puff_foam(body) if body.get('puff') is True else 3.0)
    align=body.get('align','left')
    if align not in ('left','center','right'):raise ValueError('Choose left, centre or right alignment.')
    return text,font,scale,align


def generate(body, *, native=False):
    text,font,scale,align=validate(body)
    puff=body.get('puff') is True
    vector=embroidery_fonts.layout(text,font['key'],scale,align,puff=puff,foam_mm=puff_foam(body),
                                   fill=not puff and scale>font['max_scale']*100+1e-6)
    coverage={}
    if native:
        from .lettering_geometry import source_frame
        from .lettering_source import route_font
        vector,cuts=route_font(vector)
        vector,mask,origin,columns,grid=source_frame(vector,with_grid=True)
        coverage=dict(mask=mask,origin=origin,columns=columns,added_cuts=cuts,grid=grid)
    from .lettering_rebuild import rebuild
    rebuilt_svg, rebuilt_plan, report = rebuild(vector)
    report.update(coverage)
    return dict(svg=rebuilt_svg,plan=rebuilt_plan,rebuild_report=report,
                text=text,font=font['name'],nominal_height_mm=font['size']*scale/100,
                requested_height_mm=float(body.get('height_mm',5)),release_approved=False)
