"""Selected details must not silently vanish between artwork and fill paths."""
import json
import numpy as np
from PIL import Image, ImageDraw
import pytest

from embroiderly.preparation import prepare
from embroiderly.engine import digitize


def artwork(path):
    image = Image.new('RGBA', (100, 100), '#ddaa88')
    ImageDraw.Draw(image).rectangle((48, 48, 49, 49), fill='black')
    image.save(path)
    return image


def test_kept_half_mm_piece_warns_before_stitching(tmp_path):
    path = tmp_path / 'eye.png'
    original = artwork(path)
    result, _, report = prepare(path, dict(count=2, floor_mm2=0, smooth=0, height_mm=25))
    assert np.array_equal(np.asarray(original), np.asarray(result))
    item, = report['generation_blockers']
    assert item['bounds'] == [48, 48, 50, 50]
    assert (item['width_mm'], item['height_mm'], item['area_mm2']) == (.5, .5, .25)
    assert item['colour'] == '#000000'


def test_generation_refuses_omission_before_touching_last_files(tmp_path, monkeypatch):
    path = tmp_path / 'eye.png'
    artwork(path)
    path.with_suffix('.prep.json').write_text(json.dumps({'options': {'floor_mm2': 0}}))
    directory = tmp_path / 'machine-files'
    directory.mkdir()
    (directory / 'design.dst').write_bytes(b'previous checked design')
    def no_engine(*args, **kwargs):
        raise AssertionError('An incomplete design reached the generator')
    monkeypatch.setattr('embroiderly.engine.generate_plan', no_engine)
    with pytest.raises(ValueError, match='would leave out'):
        digitize(path, directory, 25)
    assert (directory / 'design.dst').read_bytes() == b'previous checked design'
