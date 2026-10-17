import numpy as np
import pytest
from PIL import Image
from embroiderly.preparation import selection, clean_selection


def test_protection_preserves_tiny_islands_and_holes():
    image = Image.new('RGBA', (40, 40), 'white')
    mask = np.zeros((40, 40), bool)
    mask[5:35, 5:35] = True
    mask[20, 20] = False
    mask[1, 1] = True
    result, report = clean_selection(mask.copy(), image, dict(
        protect_selection=True, floor_mm2=25, mask_holes_mm2=25,
        mask_smooth=2), pixel_area_override=1)
    assert np.array_equal(mask, result)
    assert report['mask_pixels_changed'] == 0


@pytest.mark.parametrize('mode', ['lasso', 'assisted', 'full'])
def test_manual_corrections_override_cleanup_for_every_selection(mode):
    image = Image.new('RGBA', (40, 40), 'white')
    mask = np.ones((40, 40), bool)
    mask[3:9, 3:9] = False
    result, _ = clean_selection(mask, image, dict(selection=mode,
        protect_selection=True, hints=[
            dict(kind='keep', points=[[5, 5]], radius=1),
            dict(kind='remove', points=[[20, 20]], radius=1)]))
    assert result[5, 5]
    assert not result[20, 20]


def test_outline_preserves_all_interior_colours():
    rgb = np.random.default_rng(42).integers(0, 256, (40, 40, 3), dtype=np.uint8)
    image = Image.fromarray(rgb).convert('RGBA')
    options = dict(selection='lasso', outline=[[2, 2], [37, 2], [37, 37], [2, 37]], protect_selection=True)
    mask, _ = clean_selection(selection(image, options), image, options)
    isolated = image.copy()
    isolated.putalpha(Image.fromarray(mask.astype('uint8') * 255))
    assert mask[3:37, 3:37].all()
    assert np.array_equal(np.asarray(isolated)[mask, :3], rgb[mask])
