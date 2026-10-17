"""Small flat-art colours must not depend on where a sample stride lands."""
import numpy as np
import pytest
from PIL import Image, ImageDraw

from embroiderly.preparation import prepare


@pytest.mark.parametrize('left', [200, 201, 204, 207])
def test_small_colour_survives_without_cleanup_or_colour_lock(tmp_path, left):
    path = tmp_path / 'small-eye.png'
    image = Image.new('RGBA', (400, 400), '#ddaa88')
    ImageDraw.Draw(image).rectangle((left, 201, left + 2, 203), fill='black')
    image.save(path)
    output, palette, report = prepare(path, dict(count=2, floor_mm2=0, smooth=0, height_mm=100))
    assert np.array_equal(np.asarray(image), np.asarray(output))
    assert {p['hex'] for p in palette} == {'#000000', '#ddaa88'}
    assert not report['automatic_changes']


def test_small_colour_reaches_cleanup_review_at_its_real_size(tmp_path):
    path = tmp_path / 'small-eye.png'
    image = Image.new('RGBA', (400, 400), '#ddaa88')
    ImageDraw.Draw(image).rectangle((201, 201, 203, 203), fill='black')
    image.save(path)
    options = dict(count=2, floor_mm2=1, smooth=0, height_mm=100)
    _, _, report = prepare(path, options)
    item, = report['cleanup_review']
    assert (item['width_mm'], item['height_mm'], item['area_mm2']) == (.75, .75, .5625)
    assert item['bounds'] == [201, 201, 204, 204]
    output, _, _ = prepare(path, {**options, 'cleanup_decisions': {item['id']: 'keep'}})
    assert output.getpixel((202, 202)) == (0, 0, 0, 255)


def test_colour_reduction_cannot_claim_nothing_changed(tmp_path):
    path = tmp_path / 'three-tones.png'
    image = Image.new('RGBA', (120, 120), '#ddaa88')
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 10, 40, 40), fill='black')
    draw.rectangle((70, 70, 100, 100), fill='white')
    image.save(path)
    output, _, report = prepare(path, dict(count=2, floor_mm2=0, smooth=0, height_mm=100))
    assert not np.array_equal(np.asarray(image), np.asarray(output))
    assert report['automatic_changes']
    assert any(c['stage'] == 'quantization' for c in report['detail_loss']['pipeline_changes'])
