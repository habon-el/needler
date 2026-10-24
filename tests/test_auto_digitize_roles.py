"""Auto-digitizing: background omitted, hairlines sewn as runs, optional outlines."""
import json

import numpy as np
import pytest
from PIL import Image, ImageDraw

from embroiderly.engine import digitize
from embroiderly.fill_coverage import missing_boundaries
from embroiderly.preparation import prepare
from embroiderly.release_gate import checked_bytes


def artwork(path):
    image = Image.new('RGBA', (400, 400), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((60, 60, 340, 200), fill=(30, 90, 200, 255))
    draw.line((60, 260, 340, 260), fill=(200, 40, 40, 255), width=1)    # a pixel wide: no area to fill
    draw.line((60, 320, 340, 320), fill=(40, 140, 60, 255), width=2)    # about half a millimetre
    image.save(path)


def generate(tmp_path, options, height=100):
    source = tmp_path/'art.png'
    artwork(source)
    image, _, report = prepare(source, {'height_mm': height, 'floor_mm2': .1})
    prepared = tmp_path/'prepared.png'
    image.save(prepared)
    prepared.with_suffix('.prep.json').write_text(json.dumps({'options': {'height_mm': height, **options}, 'report': {}}))
    payload = digitize(prepared, tmp_path/'out', height)
    return report, payload, (tmp_path/'out'/'design.svg').read_text(encoding='utf-8')


def test_hairlines_are_sewn_as_runs_and_pass_the_release_gate(tmp_path):
    # At 60 mm the 1-pixel line has no area and the 2-pixel one is 0.3 mm: both are runs.
    report, _, svg = generate(tmp_path, {}, height=60)
    assert not report['generation_blockers']
    assert svg.count('id="hair') == 2
    assert checked_bytes(tmp_path/'out', 'dst')


def test_lines_wide_enough_for_satin_stay_satin(tmp_path):
    _, _, svg = generate(tmp_path, {}, height=100)          # the 2-pixel line is 0.5 mm here
    assert svg.count('id="hair') == 1 and 'auto_satin' in svg


def test_short_specks_are_still_reported_missing():
    rgb = np.zeros((50, 50, 3), np.uint8)
    alpha = np.zeros((50, 50), bool)
    alpha[10, 10] = True                       # one pixel: 0.25 mm, too short to sew as a line
    alpha[30, 5:45] = True                     # 40 pixels long: 10 mm, sewn as a line
    found = missing_boundaries(rgb, alpha, .25)
    assert len(found) == 1 and found[0]['bounds'][:2] == [10, 10]


def test_outlines_trace_colour_boundaries_last_in_their_own_thread(tmp_path):
    _, _, svg = generate(tmp_path, {'outlines': True, 'outline_colour': '#101010'})
    assert 'stroke:#101010' in svg
    assert svg.rfind('stroke:#101010') > svg.rfind('id="area')
    assert checked_bytes(tmp_path/'out', 'dst')


def test_outline_colour_is_checked(tmp_path):
    with pytest.raises(ValueError):
        generate(tmp_path, {'outlines': True, 'outline_colour': 'black'})


def run_auto(tmp_path, body):
    import time
    import sys
    sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
    from test_auto_digitize import badge
    from embroiderly.web import create_app
    app = create_app(tmp_path)
    badge().save(tmp_path/'work/uploads/badge.png')
    client = app.test_client()
    assert client.post('/api/auto-digitize/badge.png', json=body).status_code == 202
    for _ in range(600):
        job = client.get('/api/auto-digitize/badge.png').get_json()
        if job['state'] != 'running':
            return job
        time.sleep(.5)
    return job


def test_digitize_for_me_leaves_out_a_plain_background(tmp_path):
    job = run_auto(tmp_path, {'request': ''})
    result = job['result']
    assert job['state'] == 'done', job
    # The badge is round: sewn width and height match (the white canvas is 4:3).
    assert abs(result['width_mm']-result['height_mm']) < 3
    assert any('Leaving out the plain background' in s['text'] for s in job['steps'])


def test_keep_the_background_still_sews_it(tmp_path):
    result = run_auto(tmp_path, {'request': 'keep the background'})['result']
    assert result['width_mm'] > 1.2*result['height_mm']


def test_outline_and_detail_choices_reach_the_engine(tmp_path):
    job = run_auto(tmp_path, {'request': '', 'outlines': True, 'detail': 5})
    assert job['state'] == 'done', job
    saved = json.loads((tmp_path/'work/decisions/badge.png.preparation.json').read_text())
    assert saved['outlines'] is True and saved['floor_mm2'] == .25
    svgs = list((tmp_path/'work/inkstitch-preview').glob('*/design.svg'))
    assert any('stroke:#202020' in p.read_text(encoding='utf-8') for p in svgs)


def test_request_words_turn_outlines_on():
    from embroiderly.auto_digitize import parse_request
    assert parse_request('logo with an outline, 6 cm wide')['outlines'] is True
    assert 'outlines' not in parse_request('logo 6 cm wide')
