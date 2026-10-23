"""Size limits follow font metadata; cleanup can be reviewed without 372 requests."""
import numpy as np
import pytest
from PIL import Image, ImageDraw

from embroiderly.small_lettering import validate, size_limits
from embroiderly.web import create_app


@pytest.mark.parametrize('height', [6, 8, 12, 15])
def test_height_is_the_stitched_height_of_the_words(height):
    from embroiderly.embroidery_fonts import text_metrics
    words, font, scale, _ = validate(dict(text='tiny i .', font='small_font', height_mm=height))
    assert words == 'tiny i .'
    assert font['min_scale'] * 100 <= scale <= font['max_scale'] * 100
    # Capital height times the block's height in capitals, plus the satin edge.
    stitched = text_metrics(words, 'small_font')['height'] * font['size'] * scale / 100 + 2 * font['pull_mm']
    assert abs(stitched - height) < .01


def test_range_is_derived_not_a_new_hard_coded_font_rule():
    assert size_limits(dict(size=10, min_scale=.25, max_scale=2)) == (2.5, 20)
    for height in [0, float('inf'), float('nan')]:
        with pytest.raises(ValueError, match='Enter the height'):
            validate(dict(text='tiny', font='small_font', height_mm=height))
    for height in [2, 3, 1000]:  # 1000 mm: past the 300 mm capital limit
        with pytest.raises(ValueError, match='Choose a height from'):
            validate(dict(text='tiny', font='small_font', height_mm=height))


def test_many_cleanup_choices_return_preview_and_keep_all_preserves_pixels(tmp_path):
    client = create_app(tmp_path).test_client()
    path = tmp_path/'work/uploads/details.png'
    image = Image.new('RGBA', (240, 250), 'white')
    draw = ImageDraw.Draw(image)
    for y in range(12):
        for x in range(31):
            draw.rectangle((5+x*7, 5+y*19, 6+x*7, 6+y*19), fill='black')
    image.save(path)
    options = dict(count=2, height_mm=50, floor_mm2=1, smooth=0)
    blocked = client.post('/artwork/details.png', json=dict(options=options, digitize=True, subject_confirmed=True))
    assert blocked.status_code == 400
    assert blocked.json.get('code') == 'cleanup_review_required'
    assert blocked.json['image'].startswith('data:image/png;base64,')
    records = blocked.json['report']['cleanup_review']
    assert len(records) == 372 and all(r['decision'] == 'pending' for r in records)
    # One explicit selection represents every pending record, not a server bypass.
    options['cleanup_decisions'] = {r['id']: 'keep' for r in records}
    saved = client.post('/artwork/details.png', json=dict(options=options, save=True))
    assert saved.status_code == 200, saved.json
    assert all(r['decision'] == 'keep' for r in saved.json['report']['cleanup_review'])
    from embroiderly.preparation import prepare
    kept, _, _ = prepare(path, options)
    assert np.array_equal(np.array(kept), np.array(image))
    # Changing the physical size needs a new preview, never silently reuses decisions.
    changed = client.post('/artwork/details.png', json=dict(options={**options, 'height_mm': 40}, save=True))
    assert changed.status_code == 400 and changed.json['code'] == 'cleanup_review_required'


def test_editor_uses_server_font_limits(tmp_path):
    page = create_app(tmp_path).test_client().get('/text/new')
    assert page.status_code == 200
    assert b'data-min="3.6" data-max="15.2"' in page.data
    assert b'id="nativeSmaller"' in page.data
