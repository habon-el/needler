"""New fills and outline borders, through the engine and the release gate."""
import json

import numpy as np
import pytest
from PIL import Image, ImageDraw

from embroiderly.engine import digitize
from embroiderly.preparation import prepare
from embroiderly.region_stitches import regions
from embroiderly.release_gate import checked_bytes


def design(tmp_path, options):
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path/'art.png'
    image = Image.new('RGBA', (400, 400), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((40, 40, 360, 360), fill=(30, 90, 200, 255))
    draw.rectangle((150, 150, 250, 250), fill=(230, 180, 30, 255))
    image.save(source)
    height = 60
    prepared_image, _, report = prepare(source, {'height_mm': height})
    assert not report['generation_blockers']
    prepared = tmp_path/'prepared.png'; prepared_image.save(prepared)
    if 'region_styles' in options:
        array = np.asarray(Image.open(prepared).convert('RGBA'))
        ids = [key for key, _, _ in regions(array[..., :3], array[..., 3] > 0)]
        options = dict(options, region_styles={key: options['region_styles'] for key in ids})
    prepared.with_suffix('.prep.json').write_text(json.dumps({'options': {'height_mm': height, **options}, 'report': {}}))
    payload = digitize(prepared, tmp_path/'out', height)
    return payload, (tmp_path/'out'/'design.svg').read_text(encoding='utf-8')


@pytest.mark.parametrize('kind', ['step', 'gradient', 'radial'])
def test_specialty_fills_generate_and_pass_the_release_gate(tmp_path, kind):
    payload, svg = design(tmp_path, {'region_styles': kind})
    assert f'{kind}_fill' in svg
    assert payload['stitch_count'] > 300
    assert checked_bytes(tmp_path/'out', 'dst')


@pytest.mark.parametrize('kind', ['backstitch', 'stemstitch', 'blanket', 'zigzag'])
def test_outline_borders_generate_and_pass_the_release_gate(tmp_path, kind):
    payload, svg = design(tmp_path, {'border_style': kind, 'border_width': 2, 'border_colour': '#202020'})
    assert f'outline_style="{kind}"' in svg
    assert checked_bytes(tmp_path/'out', 'dst')


def test_density_choice_scales_stitches_and_passes_the_release_gate(tmp_path):
    counts = {}
    for level in ('lighter', 'normal', 'denser'):
        payload, _ = design(tmp_path/level, {'density': level})
        counts[level] = payload['stitch_count']
        assert checked_bytes(tmp_path/level/'out', 'dst')
    assert counts['lighter'] < counts['normal'] < counts['denser']
    with pytest.raises(ValueError):
        design(tmp_path/'bad', {'density': 'thick'})
