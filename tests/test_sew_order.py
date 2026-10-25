"""Sewing order: fewest colour changes, or best look (back to front, a thread may repeat)."""
import numpy as np
import cv2
import pytest
from PIL import Image

from embroiderly.engine import layer_passes

BLUE, RED = (120, 160, 230), (200, 30, 60)


def picture():
    rgba = np.zeros((400, 400, 4), np.uint8)
    rgba[40:360, 230:380] = [*BLUE, 255]                 # big tail: the larger blue area
    head = cv2.circle(np.zeros((400, 400), np.uint8), (120, 150), 90, 1, -1)
    rgba[head > 0] = [*RED, 255]
    cheek = cv2.circle(np.zeros((400, 400), np.uint8), (100, 160), 30, 1, -1)
    rgba[cheek > 0] = [*BLUE, 255]                      # cheek sits inside the head
    return rgba


def test_layer_passes_sew_the_cheek_after_the_head():
    rgba = picture()
    masks = [(np.array(c), {'thread': '#%02x%02x%02x' % c}, np.all(rgba[:, :, :3] == c, axis=2).astype(np.uint8))
             for c in (BLUE, RED)]
    order = [tuple(int(v) for v in colour) for colour, _, _ in layer_passes(masks)]
    assert order == [BLUE, RED, BLUE]


@pytest.mark.parametrize('order,threads', [('colours', 2), ('layers', 3)])
def test_both_orders_pass_the_release_gate(tmp_path, order, threads):
    from embroiderly.web import create_app
    from embroiderly.release_gate import checked_bytes
    (tmp_path/'work/uploads').mkdir(parents=True)
    Image.fromarray(picture()).save(tmp_path/'work/uploads/p.png')
    client = create_app(tmp_path).test_client()
    options = {'height_mm': 80, 'floor_mm2': 1, 'smooth': 0, 'mask_holes_mm2': 0, 'count': 2, 'sew_order': order}
    body = client.post('/artwork/p.png', json=dict(options=options, subject_confirmed=True, digitize=True)).get_json()
    assert body.get('playback'), body.get('error')
    assert len(body['playback']['colors']) == threads
    assert checked_bytes(tmp_path/'work'/'inkstitch-preview'/__import__('pathlib').Path(body['prepared_name']).stem, 'dst')


def test_unknown_order_is_refused(tmp_path):
    from embroiderly.engine import layer_passes  # noqa: F401
    from embroiderly.web import create_app
    (tmp_path/'work/uploads').mkdir(parents=True)
    Image.fromarray(picture()).save(tmp_path/'work/uploads/p.png')
    client = create_app(tmp_path).test_client()
    options = {'height_mm': 80, 'count': 2, 'sew_order': 'random'}
    body = client.post('/artwork/p.png', json=dict(options=options, subject_confirmed=True, digitize=True)).get_json()
    assert 'sewing order' in (body.get('error') or '')
