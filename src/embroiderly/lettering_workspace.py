"""Workspace adapter for native letters: display vectors, replay checked files.

No raster artwork/preparation call is allowed here. An immutable recipe ID is
the source of truth; edited words/size produce a new ID. The original design is
never overwritten. SVG below is display-only and is not fed back to generation.
"""
import base64
from tempfile import TemporaryDirectory
import json
from pathlib import Path
import re

import pyembroidery as emb
from flask import jsonify, render_template
from .lettering_geometry import outline
from .lettering_native import load
from .machine_files import read_pattern
from .release_gate import checked_bytes


def workspace_data(folder, key):
    result = load(folder, key)
    # Even a preview must not advertise an unchecked/corrupted pair as current.
    if result['checks_passed']:
        checked = checked_bytes(folder, 'dst')
    shape, _, _ = outline((folder/'source.svg').read_text())
    left, top, right, bottom = shape.bounds
    cx, cy = (left+right)/2, (top+bottom)/2
    r = result['reports']['dst']
    width = max(right-left, r['width_mm'])+4
    height = max(bottom-top, r['height_mm'])+4
    colour = result['recipe']['colour']
    polygons = list(shape.geoms) if shape.geom_type == 'MultiPolygon' else [shape]
    rings = [ring for p in polygons for ring in (p.exterior, *p.interiors)]
    d = ' '.join('M '+' L '.join(f'{x-cx:.5f},{y-cy:.5f}' for x,y in ring.coords)+' Z' for ring in rings)
    # Explicit intrinsic aspect ratio is important for the shared canvas/ruler.
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width*10}" height="{height*10}" '
           f'viewBox="{-width/2} {-height/2} {width} {height}">'
           f'<path fill="{colour}" fill-rule="evenodd" d="{d}"/></svg>')
    image = 'data:image/svg+xml;base64,'+base64.b64encode(svg.encode()).decode()
    with TemporaryDirectory(prefix='text-playback-') as temporary:
        snapshot = Path(temporary)/'design.dst'
        snapshot.write_bytes(checked if result['checks_passed'] else (folder/'design.dst').read_bytes())
        pattern = read_pattern(snapshot)
    types = {emb.STITCH:'stitch', emb.JUMP:'jump', emb.TRIM:'trim', emb.COLOR_CHANGE:'color_change', emb.END:'end'}
    steps = [dict(x=x/10,y=y/10,t=types.get(flag & emb.COMMAND_MASK,'unknown'),color=colour)
             for x,y,flag in pattern.stitches]
    playback = dict(steps=steps, colors=[colour], stitch_count=r['stitches'], trim_count=r['trims'],
                    origin_mm=[width/2,height/2], height_mm=height,
                    engine='Ink/Stitch embroidery font', generation_mode='native lettering',
                    objects=result['source_columns'])
    return dict(result=result, image=image, playback=playback,
                canvas_height_mm=height, canvas_width_mm=width)


def register(app, root):
    store = Path(root)/'work/lettering-native'

    def get(key):
        if not re.fullmatch(r'[a-f0-9]{64}', key):
            raise ValueError('This lettering link is invalid.')
        return workspace_data(store/key, key)

    @app.get('/lettering/native/<key>/workspace-data')
    def data(key):
        try:
            return jsonify(get(key))
        except (ValueError, OSError, KeyError) as error:
            message = str(error) if isinstance(error, ValueError) else 'Saved lettering is unavailable. Open Text and rebuild your words.'
            return jsonify(error=message), 422

    @app.get('/text/new')
    def new_workspace():
        # Display the existing native-text editor, without generating a design.
        from .colour_knockout import defaults
        return render_template('artwork.html', name='new-text', options={},
            original='', previous=None, simulation='', knockout_seed=defaults(),
            native_text=dict(id=None, recipe=dict(text='', font='small_font',
                height_mm=5, align='center', available_width_mm=50, colour='#202020')))

    @app.get('/text/<key>')
    def workspace(key):
        from .colour_knockout import defaults
        # Load the recipe even when generator changes require a fresh build.
        # Never route a stale native design back through picture processing.
        if not re.fullmatch(r'[a-f0-9]{64}', key):
            return 'This lettering link is invalid. Return to your design.', 404
        try:
            settings = json.loads((store/key/'result.json').read_text())['recipe']
        except (OSError, ValueError, KeyError):
            return 'Saved lettering is unavailable. Return to your design and open Text.', 404
        return render_template('artwork.html', name='text-'+key,
            options={}, original='', previous=None, simulation='', knockout_seed=defaults(),
            native_text=dict(id=key, recipe=settings))
