"""Digitize for me with a colourful photo of one object on a plain background (a rose on white):
sewn in colour with its shading, colour families never merged, detail wishes understood."""
import json
import time

import numpy as np
from PIL import Image

from embroiderly.auto_digitize import adjust, classify, hue_families, parse_request


def rose():
    """A shaded red flower, two green leaves and a thin stem on white, like a product photo."""
    h, w = 600, 380
    yy, xx = np.mgrid[:h, :w]
    rgb = np.full((h, w, 3), 255, np.float32)
    flower = (xx-190)**2/80**2+(yy-90)**2/60**2 < 1
    shade = (np.sin(xx/9.0)*np.cos(yy/7.0)+1)/2             # petal folds: dark and light reds
    rgb[flower] = np.stack([130+110*shade, 10+20*shade, 15+20*shade], -1)[flower]
    stem = (abs(xx-190) < 5) & (yy > 140) & (yy < 590)
    leaves = ((xx-120)**2/60**2+(yy-260)**2/22**2 < 1) | ((xx-260)**2/60**2+(yy-330)**2/22**2 < 1)
    green = stem | leaves
    rgb[green] = np.stack([70+40*shade, 110+40*shade, 40+20*shade], -1)[green]
    # Camera noise and soft light: the subject is not flat colour, the white stays plain.
    noise = np.random.default_rng(0).normal(0, 32, rgb.shape)
    rgb[flower | green] += noise[flower | green]+(yy[flower | green, None]-300)*.08
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))


def test_a_photo_of_one_object_on_white_is_sewn_in_colour():
    kind, facts = classify(rose())
    assert kind == 'logo' and facts['object_photo'] and facts['hues'] == 2
    assert facts['thread_colours'] >= 6   # enough threads for the shading


def test_flat_artwork_on_white_is_still_a_logo():
    art = np.full((300, 300, 3), 255, np.uint8)
    art[50:250, 50:150] = (200, 30, 40)
    art[50:250, 160:250] = (40, 140, 60)
    kind, facts = classify(Image.fromarray(art))
    assert kind == 'logo' and not facts.get('object_photo')


def test_colour_families():
    red = np.array([[200, 30, 40], [150, 10, 20]]*20, np.float32)
    green = np.array([[40, 140, 60], [70, 110, 40]]*20, np.float32)
    assert hue_families(red) == 1 and hue_families(np.vstack([red, green])) == 2


def test_detail_words_are_understood():
    assert parse_request('make it and include all the details')['detail'] == 'more'
    assert parse_request('a detailed rose, 8 colours') == {'colours': 8, 'detail': 'more'}
    assert parse_request('keep it simple')['detail'] == 'less'
    assert 'detail' not in parse_request('10 cm tall')


def test_retries_never_merge_colour_families():
    cuts = [dict(kind='cuts', text='90 thread cuts')]
    # Red and green: never fewer than 3 threads, however many cuts.
    nxt, _, why = adjust({'count': 4, 'floor_mm2': 1}, 'logo', cuts, 1, least=3)
    assert nxt['count'] == 3
    nxt, _, why = adjust({'count': 3, 'floor_mm2': 1}, 'logo', cuts, 2, least=3)
    assert nxt['count'] == 3 and 'colours to make' not in why


def test_a_detail_wish_keeps_detail_on_retries():
    cuts = [dict(kind='cuts', text='90 thread cuts')]
    assert adjust({'count': 7, 'floor_mm2': .5}, 'logo', cuts, 1, detail='more') is None   # cuts are its price
    blocked = [dict(kind='gate', text='Export blocked')]
    nxt, _, why = adjust({'count': 7, 'floor_mm2': .5}, 'logo', blocked, 1, least=3, detail='more')
    assert nxt['count'] == 7 and nxt['floor_mm2'] <= 2.5 and 'colours stay' in why
    nxt, _, why = adjust({'count': 7, 'floor_mm2': 2.5}, 'logo', blocked, 3, least=3, detail='more')
    assert nxt['count'] == 6 and 'stay separate' in why
    assert adjust({'count': 3, 'floor_mm2': 2.5}, 'logo', blocked, 4, least=3, detail='more') is None


def test_digitize_for_me_sews_the_rose_in_red_and_green_and_passes_the_release_gate(tmp_path):
    from embroiderly.web import create_app
    from embroiderly.release_gate import checked_bytes
    (tmp_path/'work/uploads').mkdir(parents=True)
    rose().save(tmp_path/'work/uploads/rose.png')
    client = create_app(tmp_path).test_client()
    assert client.post('/api/auto-digitize/rose.png', json=dict(request='make it and include all the details')).status_code == 202
    for _ in range(300):
        job = client.get('/api/auto-digitize/rose.png').get_json()
        if job.get('state') not in ('running', 'queued'):
            break
        time.sleep(1)
    steps = ' '.join(s['text'] for s in job['steps'])
    assert 'one object on a plain background' in steps and 'Cutting the object out' in steps and 'asked for detail' in steps
    assert job['result']['ok'], job['result']
    preview = max((tmp_path/'work/inkstitch-preview').iterdir(), key=lambda p: p.stat().st_mtime)
    colours = json.loads((preview/'playback.json').read_text())['colors']
    rgb = [tuple(int(c[i:i+2], 16) for i in (1, 3, 5)) for c in colours]
    assert any(r > g+60 for r, g, b in rgb) and any(g > r+20 for r, g, b in rgb)   # reds and greens, not brown
    assert checked_bytes(preview, 'dst')
