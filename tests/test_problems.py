import base64
import json

import numpy as np
from PIL import Image, ImageDraw

from embroiderly.auto_digitize import AutoDigitizer
from embroiderly.web import create_app


def _design(tmp_path):
    app = create_app(tmp_path)
    image = Image.new('RGB', (300, 200), 'white')
    ImageDraw.Draw(image).rectangle((40, 40, 260, 160), fill='#1d4f91')
    image.save(tmp_path / 'work/uploads/block.png')
    result, _ = AutoDigitizer(app, tmp_path)._attempt(tmp_path / 'work/uploads/block.png',
                                                     dict(artwork_type='logo', count=2, height_mm=40), .8)
    return app.test_client(), result['prepared']


def _remove_area(tmp_path, prepared, box):
    """Mark part of the sewn area as removed, as an erased spot would be."""
    folder = tmp_path / 'work/inkstitch-preview' / prepared.rsplit('.', 1)[0]
    record = json.loads((folder / 'release-context.json').read_text())
    h, w = record['shape']
    mask = np.unpackbits(np.frombuffer(base64.b64decode(record['mask']), np.uint8))[:h * w].reshape(h, w).astype(bool)
    x0, y0, x1, y1 = box
    mask[y0:y1, x0:x1] = False
    record['mask'] = base64.b64encode(np.packbits(mask).tobytes()).decode()
    (folder / 'release-context.json').write_text(json.dumps(record))


def test_clean_design_has_no_problems(tmp_path):
    client, prepared = _design(tmp_path)
    assert client.get('/api/problems/' + prepared).get_json()['problems'] == []


def test_problem_is_found_grouped_located_and_fixable(tmp_path):
    client, prepared = _design(tmp_path)
    _remove_area(tmp_path, prepared, (140, 90, 146, 96))
    problems = client.get('/api/problems/' + prepared).get_json()['problems']
    assert problems and problems[0]['title'] == 'Stitches cross bare fabric'
    first = problems[0]
    x0, y0, x1, y1 = first['bounds']
    assert x0 <= 146 and x1 >= 140 and y0 <= 96 and y1 >= 90          # points at the spot
    edit = first['fix']['edits'][0]
    assert edit['kind'] == 'paint' and edit['colour'] == '#1d4f91'    # filled with the colour around it
    assert len(problems) < 10                                          # nearby findings are one problem
    assert client.get('/api/problems/nothing.png').status_code == 404
