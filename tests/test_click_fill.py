"""Click to fill: an empty space closed by the artwork becomes a fill piece, sewn first."""
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from embroiderly.piece_layout import change, inventory
from embroiderly.region_stitches import inventory as region_inventory

SCALE = .2   # mm per pixel


def artwork(gap=0, island=True):
    """A thick black ring (optionally with a gap) and a small black dot inside it."""
    rgba = np.zeros((400, 400, 4), np.uint8)
    ring = cv2.circle(np.zeros((400, 400), np.uint8), (200, 200), 120, 1, 14)
    if gap:
        ring[190:190+gap, 300:340] = 0
    rgba[ring > 0] = [20, 20, 20, 255]
    if island:
        rgba[cv2.circle(np.zeros((400, 400), np.uint8), (200, 200), 20, 1, -1) > 0] = [20, 20, 20, 255]
    return rgba


def layout(rgba, options):
    regions = region_inventory(rgba[:, :, :3], rgba[:, :, 3] > 127, SCALE, options)
    return inventory(regions, options, 400, 400, SCALE)


def fill(rgba, point_px, holes=True, options=None):
    options = options or {}
    report = layout(rgba, options)
    point = [point_px[0]*SCALE-report['origin_mm'][0], point_px[1]*SCALE-report['origin_mm'][1]]
    return change(options, report, dict(ids=[], field='click_fill', value=dict(point=point, colour='#e0b030', holes=holes)), image=rgba)


def filled(options, rgba):
    return [p for p in layout(rgba, options)['pieces'] if p.get('under')]


def test_click_inside_fills_the_space_up_to_and_under_the_lines():
    rgba = artwork()
    options = fill(rgba, (130, 200))
    (piece,) = filled(options, rgba)
    assert piece['colour'] == '#e0b030' and piece['name'].startswith('Fill')
    # Inside the ring (radius 112 px clear) minus the dot (radius 21 px), tucked a little under both.
    clear = (np.pi*112**2-np.pi*21**2)*SCALE**2
    assert clear < piece['area_mm2'] < clear*1.06
    assert len(piece['rings']) == 2   # the dot stays open


def test_without_holes_the_fill_runs_under_the_dot():
    rgba = artwork()
    (piece,) = filled(fill(rgba, (130, 200), holes=False), rgba)
    assert len(piece['rings']) == 1


def test_small_gaps_are_bridged_but_open_spaces_are_refused():
    rgba = artwork(gap=3)   # 0.6 mm gap in the ring
    assert filled(fill(rgba, (130, 200)), rgba)
    with pytest.raises(ValueError, match='open to the outside'):
        fill(artwork(gap=20), (130, 200))
    with pytest.raises(ValueError, match='open to the outside'):
        fill(rgba, (10, 10))
    with pytest.raises(ValueError, match='already stitched'):
        fill(rgba, (200, 200))


def test_filled_space_is_sewn_first_and_passes_the_release_gate(tmp_path):
    from embroiderly.web import create_app
    from embroiderly.release_gate import checked_bytes
    (tmp_path/'work/uploads').mkdir(parents=True)
    Image.fromarray(artwork()).save(tmp_path/'work/uploads/p.png')
    client = create_app(tmp_path).test_client()
    options = {'height_mm': 80, 'floor_mm2': 1, 'smooth': 0, 'mask_holes_mm2': 0, 'count': 2}
    r = client.post('/artwork/p.png', json=dict(options=options)).get_json()
    report = r['report']['piece_layout']
    point = [130*report['scale']-report['origin_mm'][0], 200*report['scale']-report['origin_mm'][1]]
    body = client.post('/artwork/p.png', json=dict(
        options=options, piece_revision=r['piece_revision'], subject_confirmed=True, digitize=True,
        piece_command=dict(ids=[], field='click_fill', value=dict(point=point, colour='#e0b030', holes=True)))).get_json()
    assert body.get('playback'), body.get('error')
    assert body['playback']['colors'][0] == '#e0b030'   # the fill goes first, under the lines
    assert checked_bytes(tmp_path/'work'/'inkstitch-preview'/Path(body['prepared_name']).stem, 'dst')
