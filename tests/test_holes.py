"""Remove / fill holes: an area's stitches run straight across its holes."""
import json

import numpy as np
import pytest
from PIL import Image, ImageDraw

from embroiderly.engine import digitize
from embroiderly.preparation import prepare
from embroiderly.region_stitches import hole_choices, regions
from embroiderly.release_gate import checked_bytes


def build(tmp_path, inner, fill_holes):
    """A 60 mm disc with a square in the middle: another colour, or empty (inner=None)."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path/'art.png'
    image = Image.new('RGBA', (400, 400), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((40, 40, 360, 360), fill=(30, 90, 200, 255))
    draw.rectangle((150, 150, 250, 250), fill=inner or (0, 0, 0, 0))
    image.save(source)
    prepared_image, _, _ = prepare(source, {'height_mm': 60})
    prepared = tmp_path/'prepared.png'
    prepared_image.save(prepared)
    array = np.asarray(prepared_image.convert('RGBA'))
    disc = next(key for key, _, rings in regions(array[..., :3], array[..., 3] > 0) if len(rings) > 1)
    options = {'height_mm': 60, **({'area_holes': {disc: 'fill'}} if fill_holes else {})}
    prepared.with_suffix('.prep.json').write_text(json.dumps({'options': options, 'report': {}}))
    payload = digitize(prepared, tmp_path/'out', 60)
    return payload


def sewn_in_middle(tmp_path):
    import pyembroidery as emb
    pattern = emb.read(str(tmp_path/'out'/'design.dst'))
    # The square spans the middle 15 mm (±7.5 mm around the design centre).
    return sum(1 for x, y, c in pattern.stitches if (c & 0xff) == emb.STITCH and abs(x) < 60 and abs(y) < 60)


def test_an_empty_hole_is_filled_when_asked_and_passes_the_release_gate(tmp_path):
    kept = build(tmp_path/'keep', None, False)
    filled = build(tmp_path/'fill', None, True)
    assert sewn_in_middle(tmp_path/'keep') == 0
    assert sewn_in_middle(tmp_path/'fill') > 50
    assert filled['stitch_count'] > kept['stitch_count']
    assert checked_bytes(tmp_path/'fill'/'out', 'dst')


def test_sewing_over_a_hole_under_another_colour_passes_the_release_gate(tmp_path):
    payload = build(tmp_path, (230, 180, 30, 255), True)
    assert payload['stitch_count'] > 0
    assert checked_bytes(tmp_path/'out', 'dst')


@pytest.mark.parametrize('value', [{'bad': 'fill'}, {'a'*20: 'keep'}, []])
def test_hole_choices_are_checked(value):
    with pytest.raises(ValueError):
        hole_choices({'area_holes': value})
