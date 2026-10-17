"""Auto select must not replace an existing alpha cutout with colour guesses."""
import hashlib
import json

import numpy as np
import pytest
from PIL import Image, ImageDraw

from embroiderly.preparation import cached_selection, selection
from embroiderly.web import create_app


def lettering():
    # Transparent pixels deliberately have the same RGB as the lettering.
    image = Image.new('RGBA', (100, 60))
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 10, 12, 45), fill='black')
    draw.rectangle((30, 10, 34, 45), fill='black')
    draw.ellipse((55, 10, 85, 45), outline='black', width=3)
    draw.rectangle((92, 42, 94, 45), fill='black')
    return image


@pytest.mark.parametrize('rect', [[0, 0, 100, 60], [1, 1, 99, 59], [0, 0, 50, 60]])
def test_alpha_letters_and_holes_preserved(rect):
    image = lettering()
    expected = np.asarray(image.getchannel('A')) > 127
    roi = np.zeros(expected.shape, bool)
    x, y, right, bottom = rect
    roi[y:bottom, x:right] = True
    actual = selection(image, {'selection': 'grabcut', 'rect': rect})
    assert np.array_equal(actual, expected & roi)


def test_alpha_selection_respects_remove_hints():
    image = lettering()
    selected = selection(image, {'selection': 'grabcut', 'rect': [0, 0, 100, 60],
        'hints': [{'kind': 'remove', 'points': [[32, 25]], 'radius': 3}]})
    assert not selected[25, 32]
    assert selected[20, 11]
    assert not selected[25, 70]  # The letter counter is still open.


@pytest.mark.parametrize('rect', [[20, 20, 20, 20], [20, 20, 50, 20]])
def test_zero_area_rectangle_has_actionable_message(rect):
    with pytest.raises(ValueError, match='Click and drag'):
        selection(lettering(), {'selection': 'grabcut', 'rect': rect})


def test_opaque_full_image_still_needs_background_evidence():
    with pytest.raises(ValueError, match='Use full image'):
        selection(Image.new('RGB', (100, 60), 'black'),
                  {'selection': 'grabcut', 'rect': [0, 0, 100, 60]})


def test_old_colour_selection_cache_not_reused(tmp_path):
    image = lettering()
    path = tmp_path / 'lettering.png'
    image.save(path)
    options = {'selection': 'grabcut', 'rect': [1, 1, 99, 59]}
    cache = tmp_path / 'masks'
    cache.mkdir()
    old_key = hashlib.sha256(path.read_bytes() + json.dumps(options, sort_keys=True).encode()
                             + b'selection-v1').hexdigest()
    Image.new('L', image.size).save(cache / (old_key + '.png'))
    cold = cached_selection(path, image, options, cache)
    warm = cached_selection(path, image, options, cache)
    assert np.array_equal(cold, np.asarray(image.getchannel('A')) > 127)
    assert np.array_equal(cold, warm)


def test_preview_preserves_alpha_without_saving_original(tmp_path):
    client = create_app(tmp_path).test_client()
    image = lettering()
    path = tmp_path / 'work/uploads/letters.png'
    image.save(path)
    before = path.read_bytes()
    options = {'selection': 'grabcut', 'rect': [0, 0, 100, 60],
               'smooth': 0, 'floor_mm2': 0, 'mask_holes_mm2': 0}
    response = client.post('/artwork/letters.png', json={'options': options})
    assert response.status_code == 200, response.json
    import base64
    import io
    isolated = Image.open(io.BytesIO(base64.b64decode(response.json['isolated'].split(',')[1])))
    assert np.array_equal(np.asarray(isolated.getchannel('A')), np.asarray(image.getchannel('A')))
    assert path.read_bytes() == before
    assert not (tmp_path / 'work/decisions/letters.png.preparation.json').exists()
