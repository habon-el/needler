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
    m=embroidery_fonts.text_metrics(text,font['key'],font.get('layout',{}).get('line_spacing',1.0))
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


def layout_options(body):
    """Letter spacing, line spacing, baseline and letter order (lettering
    layout), checked. Defaults reproduce the plain left-to-right straight line."""
    def number(name,default,low,high,label):
        value=body.get(name,default)
        try:value=float(value)
        except (TypeError,ValueError):value=math.nan
        if not math.isfinite(value) or not low<=value<=high:raise ValueError(label)
        return value
    options=dict(letter_spacing_mm=number('letter_spacing_mm',0,-2,10,'Enter letter spacing from -2 to 10 mm.'),
                 line_spacing=number('line_spacing_percent',100,70,250,'Enter line spacing from 70 to 250%.')/100,
                 baseline=body.get('baseline','straight'),sequence=body.get('sequence','left'))
    if options['baseline'] not in embroidery_fonts.BASELINES:raise ValueError('Choose a straight or arc baseline.')
    if options['sequence'] not in embroidery_fonts.SEQUENCES:raise ValueError('Choose left to right or centre out.')
    if options['baseline']!='straight':
        # Curve: how far round the circle the words reach; the radius then follows the words' length.
        if body.get('arc_degrees') is not None:
            options['arc_degrees']=number('arc_degrees',90,10,300,'Choose a curve from 10 to 300 degrees.')
        else:
            options['radius_mm']=number('arc_radius_mm',60,5,1000,'Enter an arc radius from 5 to 1000 mm.')
    return options


def fabric_pull_extra(body):
    """Extra satin pull (mm per side) for the chosen fabric: half of how much more the
    fabric pulls than twill, at most 0.15 mm, so small letters keep open counters."""
    if not body.get('fabric_preset') or body.get('puff') is True:
        return 0.0
    from .generation_policy import preset_for
    pull=float(preset_for({'fabric_preset':body['fabric_preset']}).get('satin_pull_mm',.1))
    return max(0.0,min(.15,(pull-.1)/2))


def puff_foam(body):
    foam=body.get('puff_foam_mm',3)
    if foam not in (2,3,2.0,3.0):raise ValueError('Choose 2 mm or 3 mm puff foam.')
    return float(foam)


# Bold fonts tried first when the chosen font cannot be 3D puff.
PUFF_FIRST=('russo_one','bungee','archivo_black','anton','bowlby_one','alfa_slab_one')


def laid_out_width(body):
    """Width (mm) of the words as the letters are placed, before any stitches are made
    (a few hundredths of a second): the letter outlines plus the satin edge each side."""
    import re
    text,font,scale,align=validate(body)
    puff=body.get('puff') is True
    svg=embroidery_fonts.layout(text,font['key'],scale,align,puff=puff,foam_mm=puff_foam(body),
                                fill=not puff and scale>font['max_scale']*100+1e-6,pull_mm=font['pull_mm'],**font['layout'])
    xs=[float(x) for d in re.findall(r' d="([^"]+)"',svg) for x,_ in re.findall(r'(-?[\d.]+)[ ,](-?[\d.]+)',d)]
    return (max(xs)-min(xs))*embroidery_fonts.PX_MM


def advice(body):
    """Every problem with these text settings at once, each with a fix the screen can
    apply in one click (instead of one refusal per press of Make stitches). Nothing is
    built; the width is an estimate from the font's letter widths."""
    if not isinstance(body,dict):raise ValueError('Expected lettering settings.')
    text=body.get('text')
    if not isinstance(text,str) or not text.strip():
        return dict(problems=[],height_range=None,puff_fonts=[])
    text=unicodedata.normalize('NFC',text).replace('\r\n','\n')[:200]
    catalogue=fonts();font=catalogue.get(body.get('font'))
    if font is None:raise ValueError('Select an installed small embroidery font.')
    puff=body.get('puff') is True;foam=puff_foam(body) if puff else 3.0
    try:layout=layout_options(body)
    except ValueError as error:return dict(problems=[dict(message=str(error))],height_range=None,puff_fonts=[])
    font=dict(font,layout=layout)
    problems=[]
    fix=lambda label,**values:dict(label=label,set=values)
    lines=text.split('\n')
    missing=sorted(set(text)-set(font['glyphs'])-{' ','\n'})
    if missing:
        problems.append(dict(message=f'{font["name"]} has no '+' '.join(missing)+'. Remove those letters or choose another font.'))
        return dict(problems=problems,height_range=None,puff_fonts=[])
    if len(lines)>1 and layout['baseline']!='straight':
        problems.append(dict(message='A curved line takes one line of words. Remove the line break or use a straight line.',
                             fix=fix('Use a straight line',baseline='straight')))
    def workable(key):
        other=catalogue[key]
        if set(text)-set(other['glyphs'])-{' ','\n'}:return False
        try:return height_range(text,dict(other,layout=layout),True,foam) is not None
        except ValueError:return False
    puff_fonts=[key for key in catalogue if workable(key)] if puff else []
    span=height_range(text,font,puff,foam)
    if puff and span is None:
        better=sorted(puff_fonts,key=lambda k:PUFF_FIRST.index(k) if k in PUFF_FIRST else len(PUFF_FIRST))
        problem=dict(message=f'{font["name"]} cannot be 3D puff: its thin strokes are too thin for {foam:g} mm foam.')
        if better:problem['fix']=fix(f'Use {catalogue[better[0]]["name"]}',font=better[0])
        elif foam>2:problem['fix']=fix('Use 2 mm foam',puff_foam_mm=2)
        problems.append(problem)
    height=float(body.get('height_mm') or 0)
    if span and not span[0]<=height<=span[1]:
        best=min(max(height,span[0]),span[1]);best=math.floor(best*10)/10 if best>span[0] else math.ceil(best*10)/10
        problems.append(dict(message=f'Height must be {span[0]:g}–{span[1]:g} mm for these words in {font["name"]}'
                             +(f' with 3D puff on {foam:g} mm foam' if puff else '')+'.',
                             fix=fix(f'Set height to {best:g} mm',height_mm=best)))
        height=best
    available=float(body.get('available_width_mm') or 0)
    if span and height>0 and available>0:
        try:widest=laid_out_width(dict(body,height_mm=height))+.5   # the stitched edge lands within ~0.5 mm
        except ValueError:widest=0
        if widest>available:
            need=min(400,math.ceil(widest+2));smaller=math.floor(height*available/widest*10)/10
            problem=dict(message=f'About {widest:.0f} mm wide: more than your max width of {available:g} mm.',
                         fix=fix(f'Set max width to {need} mm',available_width_mm=need))
            if smaller>=span[0]:problem['also']=fix(f'Make it smaller ({smaller:g} mm tall)',height_mm=smaller)
            problems.append(problem)
    return dict(problems=problems,height_range=list(span) if span else None,puff_fonts=puff_fonts)


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
    # Fabric preset: the satin edge sits a little further out on fabrics that pull in more.
    font=dict(font,pull_mm=round(font['pull_mm']+fabric_pull_extra(body),3),layout=layout_options(body))
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
                                   fill=not puff and scale>font['max_scale']*100+1e-6,pull_mm=font['pull_mm'],
                                   **font['layout'])
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
