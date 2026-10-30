"""Digitize for me never ends with nothing because of one tiny part.

Found 2026-10-30 testing a copy of the flaming basketball: one part about a pixel
wide could not be sewn, painting over it did not clear the error, and all 4 attempts
failed. Cause: the paint brush was centred on the part's half-pixel middle, which
Python rounds to the nearest even pixel, so a speck at an odd x and y was never
covered. With the background left out, cleanup is off, so raising the floor on the
next attempt changed nothing either.
"""
import base64
import io
import time

import numpy as np
from PIL import Image, ImageDraw

from embroiderly.auto_digitize import AutoDigitizer, cleaned_note, unsewable
from embroiderly.colour_knockout import proposal_patch
from embroiderly.preparation import edit_brush
from embroiderly.web import create_app


def speckled(x=151):
    image = Image.new('RGB', (300, 300), 'white')
    draw = ImageDraw.Draw(image)
    draw.ellipse((40, 40, 260, 260), fill='#1d4f91')
    draw.rectangle((100, 120, 200, 180), fill='#e09a1f')
    draw.rectangle((120, 200, 180, 230), fill=(200, 30, 30))
    image.putpixel((x, x), (200, 30, 30))   # one red pixel inside the blue
    return image


def _url(rgba):
    stream = io.BytesIO()
    Image.fromarray(rgba).save(stream, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(stream.getvalue()).decode()


def _wait(client, name):
    for _ in range(400):
        job = client.get('/api/auto-digitize/' + name).get_json()
        if job['state'] != 'running':
            return job
        time.sleep(.5)
    return job


def test_the_paint_covers_a_speck_at_odd_pixels_and_a_lone_dot_is_left_out():
    rgba = np.zeros((20, 20, 4), np.uint8)
    rgba[2:18, 2:12] = (29, 79, 145, 255)
    rgba[11, 7] = (200, 30, 30, 255)    # inside the blue, odd x and y
    rgba[5, 15] = (200, 30, 30, 255)    # alone on bare fabric
    parts = [dict(bounds=[7, 11, 8, 12], colour='#c81e1e'), dict(bounds=[15, 5, 16, 6], colour='#c81e1e')]
    inside, lone = AutoDigitizer(None, '.')._paint_specks(_url(rgba), parts)
    assert inside['kind'] == 'paint' and inside['colour'] == '#1d4f91'
    assert edit_brush(inside, 20, 20)[11, 7] and edit_brush(inside, 20, 20).sum() == 1
    assert lone['kind'] == 'erase' and edit_brush(lone, 20, 20)[5, 15]
    assert AutoDigitizer(None, '.')._paint_specks(None, parts) == []


def test_a_one_pixel_speck_is_painted_and_the_design_sews(tmp_path):
    app = create_app(tmp_path)
    speckled().save(tmp_path / 'work/uploads/speck.png')
    client = app.test_client()
    assert client.post('/api/auto-digitize/speck.png', json={}).status_code == 202
    job = _wait(client, 'speck.png')
    assert job['state'] == 'done', job['steps']
    result = job['result']
    assert result['ok'] and result['attempts'] == 1 and not result['problem']
    assert result['cleaned'] == cleaned_note(1) and 'painted with the colour around it' in result['cleaned']
    assert any('Cleaned 1 tiny part' in s['text'] for s in job['steps'])


def test_when_cleaning_cannot_help_the_message_names_the_part_and_why(tmp_path, monkeypatch):
    monkeypatch.setattr(AutoDigitizer, '_paint_specks', lambda self, prepared, parts, limit=200: [])
    app = create_app(tmp_path)
    speckled().save(tmp_path / 'work/uploads/speck.png')
    auto = AutoDigitizer(app, tmp_path)
    options = dict(artwork_type='logo', count=3, height_mm=100)
    options.update(proposal_patch(speckled(), options))   # the white background left out
    result, _ = auto._attempt(tmp_path / 'work/uploads/speck.png', options)
    error = result['error']
    assert error.startswith('A tiny red part (#') and 'near the middle' in error
    assert 'too small for the needle to sew' in error and 'image bounds' not in error


def test_the_plain_words():
    part = dict(colour='#c81e1e', width_mm=.33, height_mm=.33, bounds=[2, 2, 3, 3])
    assert unsewable([]) is None
    text = unsewable([part, part], _url(np.zeros((30, 30, 4), np.uint8)))
    assert 'A tiny red part (#c81e1e, 0.3 × 0.3 mm, near the top left) and 1 more like it' in text
    assert cleaned_note(3, 1) == ('Cleaned 3 tiny parts under 1 mm that the needle cannot sew: they were painted '
                                  'with the colour around them (1 with nothing sewn around it left out).')
