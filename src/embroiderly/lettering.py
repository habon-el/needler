"""Local lettering recipes and vector masters; never overwrite customer designs.

Only enumerated installed fonts are accepted. Preview SVG contains generated
paths, not user markup or remote font references. This is outline lettering,
not a catalogue of pre-digitized or sew-out-validated embroidery fonts.
"""
import base64
from functools import lru_cache
import hashlib
import io
import json
import math
from pathlib import Path
import re
import threading
import unicodedata
from uuid import uuid4

from flask import jsonify, request, abort, Response
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.transformPen import TransformPen

BUNDLED = Path(__file__).with_name('fonts')
# Bundled open-licence fonts work on every operating system. Linux system font
# packages are added when present; each source must ship its licence text.
FONT_SOURCES = [
    (BUNDLED/'dejavu', 'fonts-dejavu-core', BUNDLED/'dejavu'/'LICENSE'),
    (BUNDLED/'lato', 'fonts-lato', BUNDLED/'lato'/'LICENSE'),
] + [(BUNDLED/name, 'google-fonts-'+name, BUNDLED/name/'LICENSE') for name in (
    # SIL Open Font License fonts from github.com/google/fonts (ofl/).
    'graduate', 'bebasneue', 'anton', 'staatliches', 'pacifico', 'lobster', 'kaushanscript',
    'alfaslabone', 'righteous', 'russoone', 'archivoblack', 'bowlbyone', 'bungee', 'passionone',
)] + [(Path(directory), package, Path('/usr/share/doc')/package/'copyright') for directory, package in (
    ('/usr/share/fonts/truetype/lato', 'fonts-lato'),
    ('/usr/share/fonts/truetype/dejavu', 'fonts-dejavu-core'),
    ('/usr/share/fonts/truetype/liberation', 'fonts-liberation'),
    ('/usr/share/fonts/truetype/quicksand', 'fonts-quicksand'),
    ('/usr/share/fonts/truetype/freefont', 'fonts-freefont-ttf'),
    ('/usr/share/fonts/opentype/urw-base35', 'fonts-urw-base35'),
    ('/usr/share/texmf/fonts/opentype/public/tex-gyre', 'fonts-texgyre'),
)]
RENDER_LOCK = threading.Lock()


def license_file(package):
    return next((path for _, name, path in FONT_SOURCES if name == package and path.is_file()), None)


@lru_cache(maxsize=1)
def catalogue():
    result = {}
    seen = set()
    for directory, package, license_path in FONT_SOURCES:
        if not license_path.is_file():
            continue
        for path in sorted(Path(directory).glob('*')):
            if path.suffix.lower() not in ('.ttf', '.otf'):
                continue
            try:
                with TTFont(path) as font:
                    family = font['name'].getDebugName(16) or font['name'].getDebugName(1)
                    style = font['name'].getDebugName(17) or font['name'].getDebugName(2)
                    if not family or not style or (family, style) in seen:
                        continue
                    # Bundled fonts get location-independent IDs so saved recipes
                    # keep working on any computer.
                    identity = 'bundled/'+path.relative_to(BUNDLED).as_posix() if directory.parent == BUNDLED else str(path)
                    key = hashlib.sha256(identity.encode()).hexdigest()[:20]
                    seen.add((family, style))
                    result[key] = dict(id=key, family=family, style=style,
                                       path=str(path), package=package)
            except (OSError, KeyError):
                continue
    return result


def outline(body):
    if not isinstance(body, dict):
        raise ValueError('Expected text settings.')
    text = body.get('text')
    if not isinstance(text, str) or not text.strip() or len(text) > 200:
        raise ValueError('Enter 1–200 characters.')
    text = unicodedata.normalize('NFC', text).replace('\r\n', '\n')
    if len(text.split('\n')) > 5:
        raise ValueError('Use at most five lines.')
    # Do not pretend to shape scripts requiring bidi/contextual glyph selection.
    if any(c != '\n' and (unicodedata.category(c).startswith('C') or
           unicodedata.combining(c) or unicodedata.bidirectional(c) in ('R','AL','AN')) for c in text):
        raise ValueError('This version supports left-to-right lettering without combining marks; contextual scripts need a shaping engine.')
    if any(unicodedata.category(c).startswith('L') and not unicodedata.name(c, '').startswith(('LATIN','GREEK','CYRILLIC')) for c in text):
        raise ValueError('This version supports Latin, Greek and Cyrillic letters; other scripts need a shaping engine.')
    font_id = body.get('font')
    if not isinstance(font_id, str) or font_id not in catalogue():
        raise ValueError('Choose an available font.')
    colour = body.get('colour', '#202020')
    if not isinstance(colour, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', colour):
        raise ValueError('Choose a valid thread colour.')
    height = float(body.get('height_mm', 25))
    spacing = float(body.get('spacing', 0))
    align = body.get('align', 'left')
    if not math.isfinite(height) or not 10 <= height <= 350:
        raise ValueError('Text height must be 10–350 mm.')
    if not math.isfinite(spacing) or not 0 <= spacing <= .5:
        raise ValueError('Letter spacing must be 0–0.5 em.')
    if align not in ('left', 'center', 'right'):
        raise ValueError('Choose left, centre or right alignment.')
    with TTFont(catalogue()[font_id]['path']) as font:
        cmap = font.getBestCmap()
        missing = sorted(set(c for c in text if c != '\n' and ord(c) not in cmap))
        if missing:
            raise ValueError('This font is missing: ' + ' '.join(missing))
        glyphs = font.getGlyphSet(); em = font['head'].unitsPerEm
        lines = text.split('\n')
        widths = [sum(glyphs[cmap[ord(c)]].width for c in line) + max(0,len(line)-1)*spacing*em for line in lines]
        paths = []; bounds = BoundsPen(glyphs)
        for row, line in enumerate(lines):
            x = (max(widths)-widths[row]) * {'left':0,'center':.5,'right':1}[align]
            for c in line:
                glyph = glyphs[cmap[ord(c)]]
                transform = (1,0,0,-1,x,row*em*1.4)
                pen = SVGPathPen(glyphs)
                glyph.draw(TransformPen(pen,transform));glyph.draw(TransformPen(bounds,transform))
                if pen.getCommands():
                    paths.append('<path d="'+pen.getCommands()+'"/>')
                x += glyph.width + spacing*em
    if bounds.bounds is None:
        raise ValueError('Enter visible letters, not only spaces.')
    x0,y0,x1,y1 = bounds.bounds; w,h = x1-x0,y1-y0
    if h <= 0 or w <= 0 or w/h > 25:
        raise ValueError('Text is too wide. Use shorter lines.')
    pad = h*.04
    width_mm = w/h*height
    if width_mm > 400:
        raise ValueError('Text exceeds 400 mm wide. Reduce height or add a line break.')
    recipe = dict(text=text,font=font_id,colour=colour.lower(),height_mm=height,spacing=spacing,align=align)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_mm+height*.08}mm" height="{height*1.08}mm" '
           f'viewBox="{x0-pad} {y0-pad} {w+2*pad} {h+2*pad}"><g fill="{colour}" fill-rule="nonzero">'+''.join(paths)+'</g></svg>')
    return recipe, svg, dict(width_mm=round(width_mm,2),height_mm=height,canvas_height_mm=height*1.08)


def register_lettering(app, root):
    root = Path(root)
    from .lettering_trial import register
    register(app)
    from .lettering_native import register as register_native
    register_native(app, root)
    from .lettering_workspace import register as register_workspace
    register_workspace(app, root)
    @app.get('/lettering/fonts')
    def lettering_fonts():
        fonts = [{k:v for k,v in item.items() if k!='path'} for item in catalogue().values()]
        return jsonify(fonts=sorted(fonts,key=lambda f:(f['family'],f['style'])), families=len({f['family'] for f in fonts}))

    @app.get('/lettering/license/<package>')
    def lettering_license(package):
        path=license_file(package)
        if path is None: abort(404)
        return Response(path.read_text(encoding='utf-8',errors='replace'),mimetype='text/plain')

    @app.get('/lettering/recipe/<name>')
    def lettering_recipe(name):
        if not re.fullmatch(r'lettering-[0-9a-f]{32}\.png',name): return jsonify(recipe=None)
        path=root/'work/decisions'/(name+'.lettering.json')
        return jsonify(recipe=json.loads(path.read_text()) if path.is_file() else None)

    @app.post('/lettering/preview')
    def lettering_preview():
        try:
            recipe,svg,size=outline(request.get_json(silent=True))
            from .lettering_size import source_metrics
            try:
                metrics=source_metrics(recipe)
                size['reference_capital_mm']=round(metrics['capital_per_canvas_mm']*size['canvas_height_mm'],2)
                size['line_count']=metrics['line_count']
            except (ValueError,TypeError,KeyError,OSError):
                size['reference_capital_mm']=None
            return jsonify(recipe=recipe,size=size,image='data:image/svg+xml;base64,'+base64.b64encode(svg.encode()).decode(),
                           warning='Outline font — needs stitch checking. No shaping/kerning or foam-puff validation. Fine details may exceed the current artwork resolution.')
        except (ValueError,TypeError,OverflowError) as error:
            return jsonify(error=str(error)),400

    @app.post('/lettering/create')
    def lettering_create():
        try:
            recipe,svg,size=outline(request.get_json(silent=True))
            if not RENDER_LOCK.acquire(blocking=False): return jsonify(error='Another lettering design is rendering. Retry shortly.'),409
            try:
                from .vector_raster import render
                wide=size['width_mm']>=size['height_mm']
                image=render(svg,width=768 if wide else None,height=None if wide else 768)
                buffer=io.BytesIO();image.save(buffer,'PNG');png=buffer.getvalue()
            finally:
                RENDER_LOCK.release()
            name='lettering-'+uuid4().hex+'.png'
            decisions=root/'work/decisions';uploads=root/'work/uploads'
            (decisions/(name+'.lettering.json')).write_text(json.dumps(recipe,sort_keys=True))
            (decisions/(name+'.svg')).write_text(svg)
            (decisions/(name+'.preparation.json')).write_text(json.dumps(dict(height_mm=size['canvas_height_mm'],
                selection='full',count=2,floor_mm2=0,smooth=0,simplify=0,mask_holes_mm2=0,mask_smooth=0,edge=0)))
            (uploads/name).write_bytes(png)
            return jsonify(name=name,url='/artwork/'+name)
        except (ValueError,TypeError,OverflowError) as error:
            return jsonify(error=str(error)),400
        except OSError:
            return jsonify(error='Lettering could not be rendered. Your existing design is unchanged; retry.'),503
