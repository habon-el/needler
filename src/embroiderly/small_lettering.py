"""Direct installed embroidery-font generation, independent of picture cleanup.

This produces vector source and a generator plan, NOT release-approved files.
Font size is the installed font's nominal height, not an inferred cap height.
"""
import io
import json
import math
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unicodedata
import zipfile

FONT_ROOT=Path('/opt/inkstitch/fonts')
ENGINE=Path('/opt/inkstitch/bin/inkstitch')
FONTS=('small_font','glacial_tiny')


def fonts():
    result={}
    for key in FONTS:
        folder=FONT_ROOT/key
        if not (folder/'font.json').is_file() or not (folder/'LICENSE').is_file():continue
        data=json.loads((folder/'font.json').read_text())
        result[key]=data
    return result


def size_limits(font):
    """Editable tenth-mm range inside the installed font author's scale limits."""
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
    # Batch normally splits lines into separate designs; use a separator which
    # cannot occur in accepted text so all requested lines remain one design.
    separator='__NEEDLORA_SEPARATE_DESIGN__'
    if separator in text:raise ValueError('Reserved lettering separator in text.')
    with TemporaryDirectory(prefix='small-lettering-') as temporary:
        source=Path(temporary)/'blank.svg'
        source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="200mm" height="100mm" viewBox="0 0 755.9055 377.9528"><metadata xmlns:i="http://inkstitch.org/namespace"><i:inkstitch_svg_version>3</i:inkstitch_svg_version></metadata></svg>')
        run=subprocess.run([str(ENGINE),'--extension=batch_lettering','--text='+text,
                            '--separator='+separator,'--font='+font['name'],'--scale='+str(scale),
                            '--trim=glyph','--text-align='+align,'--file-formats='+('svg' if native else 'svg,json'),str(source)],
                           capture_output=True,timeout=120,check=True,env={**os.environ,'PYTHONHASHSEED':'0'})
        with zipfile.ZipFile(io.BytesIO(run.stdout)) as archive:
            svg=[n for n in archive.namelist() if n.endswith('.svg')]
            plans=[n for n in archive.namelist() if n.endswith('.json')]
            if len(svg)!=1 or (not native and len(plans)!=1):raise ValueError('The font generator did not preserve one complete design.')
            vector=archive.read(svg[0]).decode()
            coverage={}
            if native:
                from .lettering_geometry import source_frame
                from .lettering_source import route_font
                vector,cuts=route_font(vector)
                vector,mask,origin,columns=source_frame(vector)
                coverage=dict(mask=mask,origin=origin,columns=columns,added_cuts=cuts)
            from .lettering_rebuild import rebuild
            rebuilt_svg, rebuilt_plan, report = rebuild(vector, ENGINE)
            report.update(coverage)
            return dict(svg=rebuilt_svg,plan=rebuilt_plan,rebuild_report=report,
                        text=text,font=font['name'],nominal_height_mm=font['size']*scale/100,
                        requested_height_mm=float(body.get('height_mm',5)),release_approved=False)
