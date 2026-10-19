"""Small designs (down to 3 mm): narrow areas become satin and pass the gate."""
import json
import pytest
from PIL import Image, ImageDraw
from embroiderly.engine import digitize, thickness_mm
from embroiderly.preparation import prepare
from embroiderly.release_gate import checked_bytes

STAR = [(200, 20), (245, 150), (380, 150), (270, 230), (310, 370), (200, 285), (90, 370), (130, 230), (20, 150), (155, 150)]


def star(path):
    image = Image.new('RGBA', (400, 400), (0, 0, 0, 0))
    ImageDraw.Draw(image).polygon(STAR, fill=(220, 30, 40, 255))
    image.save(path)


@pytest.mark.parametrize('height', [3, 5, 10])
def test_small_star_is_satin_and_passes_release_gate(tmp_path, height):
    source = tmp_path/'star.png'; star(source)
    image, _, report = prepare(source, {'height_mm': height})
    assert not report['generation_blockers']
    prepared = tmp_path/'prepared.png'; image.save(prepared)
    prepared.with_suffix('.prep.json').write_text(json.dumps({'options': {'height_mm': height}, 'report': {}}))
    payload = digitize(prepared, tmp_path/'out', height)
    svg = (tmp_path/'out'/'design.svg').read_text()
    assert 'auto_satin' in svg
    assert payload['stitch_count'] >= 40
    assert checked_bytes(tmp_path/'out', 'dst')


def test_wide_areas_keep_tatami():
    import numpy as np
    square = [np.array([[0, 0], [399, 0], [399, 399], [0, 399]]).reshape(-1, 1, 2)]
    assert thickness_mm(square, 60/400) > 4.5


def test_minimum_design_height_is_three_mm(tmp_path):
    source = tmp_path/'star.png'; star(source)
    prepare(source, {'height_mm': 3})
    with pytest.raises(ValueError):
        prepare(source, {'height_mm': 2})
