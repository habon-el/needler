"""Weld pieces of one thread into one; smooth a piece's outline."""
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image
from shapely.geometry import Polygon

from embroiderly.piece_layout import change, inventory

BLUE, RED = '#1e5ac8', '#c81e3c'


def box(key, x0, y0, x1, y1, colour=BLUE):
    return dict(id=key*20, colour=colour, style='tatami', rings=[[[x0, y0], [x1, y0], [x1, y1], [x0, y1]]])


def disc():
    # A 30 px disc traced from pixels: its outline is all stair-steps.
    mask = np.zeros((80, 80), np.uint8)
    cv2.circle(mask, (40, 40), 30, 1, -1)
    contour = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0][0]
    return dict(id='d'*20, colour=BLUE, style='tatami', rings=[contour[:, 0, :].tolist()])


def layout(areas, options):
    return inventory({'areas': areas}, options, 100, 100, .5)   # 0.5 mm per px


def apply(areas, options, field, value, ids):
    return change(options, layout(areas, options), dict(ids=list(ids), field=field, value=value))


def area(p):
    return Polygon(p['rings_mm'][0], p['rings_mm'][1:]).area


def test_weld_joins_overlapping_pieces_and_keeps_the_first_style():
    areas = [box('a', 0, 0, 40, 20), box('b', 30, 10, 60, 40)]
    styled = apply(areas, {}, 'style', 'step', ['b'*20])
    welded = apply(areas, styled, 'weld', None, ['b'*20, 'a'*20])   # b picked first
    (piece,) = layout(areas, welded)['pieces']
    assert piece['style'] == 'step' and piece['colour'] == BLUE
    # 10 × 5 mm and 7.5 × 7.5 mm (0.5 mm per px), overlapping by 2.5 × 2.5 mm.
    assert area(piece) == pytest.approx(200+225-25, rel=.01)
    assert len(piece['rings_mm']) == 1
    assert welded['piece_edits']['a'*20]['cut'] and welded['piece_edits']['b'*20]['cut']


def test_pieces_that_only_touch_weld_into_one():
    areas = [box('a', 0, 0, 20, 20), box('b', 20, 0, 40, 20)]
    welded = apply(areas, {}, 'weld', None, ['a'*20, 'b'*20])
    (piece,) = layout(areas, welded)['pieces']
    assert area(piece) == pytest.approx(200, rel=.01) and len(piece['rings_mm'][0]) <= 6


def test_weld_refuses_other_threads_gaps_and_a_single_piece():
    areas = [box('a', 0, 0, 20, 20), box('b', 20, 0, 40, 20, RED), box('c', 30, 30, 40, 40)]
    with pytest.raises(ValueError, match='different threads'):
        apply(areas, {}, 'weld', None, ['a'*20, 'b'*20])
    with pytest.raises(ValueError, match='do not touch'):
        apply(areas, {}, 'weld', None, ['a'*20, 'c'*20])
    with pytest.raises(ValueError, match='two or more'):
        apply(areas, {}, 'weld', None, ['a'*20])
    locked = apply(areas, {}, 'locked', True, ['c'*20])
    with pytest.raises(ValueError, match='locked'):
        apply(areas, locked, 'weld', None, ['a'*20, 'c'*20])


def test_weld_a_moved_copy_with_its_original():
    areas = [box('a', 0, 0, 20, 20)]
    copied = apply(areas, {}, 'duplicate', [5, 0], ['a'*20])
    copy = next(k for k in copied['piece_edits'] if k != 'a'*20)
    welded = apply(areas, copied, 'weld', None, [copy, 'a'*20])
    (piece,) = layout(areas, welded)['pieces']
    assert piece['width_mm'] == pytest.approx(15) and area(piece) == pytest.approx(150, rel=.01)
    assert copy not in welded['piece_edits']   # the copy is replaced by the welded part


def test_smooth_removes_steps_and_keeps_the_size():
    areas = [disc()]
    before = layout(areas, {})['pieces'][0]
    light = layout(areas, apply(areas, {}, 'smooth', 'light', ['d'*20]))['pieces'][0]
    more = layout(areas, apply(areas, {}, 'smooth', 'more', ['d'*20]))['pieces'][0]
    assert area(light) == pytest.approx(area(before), rel=.005) and area(more) == pytest.approx(area(before), rel=.005)
    assert light['width_mm'] == pytest.approx(before['width_mm'], abs=.5)

    def square_turns(p):
        # Pixel steps turn by 45° or 90° at every step; a smooth circle bends gently.
        ring = np.asarray(p['rings_mm'][0])
        a, b = ring-np.roll(ring, 1, axis=0), np.roll(ring, -1, axis=0)-ring
        turn = np.degrees(np.abs(np.arctan2(a[:, 0]*b[:, 1]-a[:, 1]*b[:, 0], (a*b).sum(axis=1))))
        return int((turn > 30).sum())
    assert square_turns(before) > 20 and square_turns(light) == 0 and square_turns(more) == 0


def test_smooth_keeps_sharp_corners():
    # A square whose right side has a tiny zig-zag: it goes, and the corners stay where they are.
    steps = [[40, 0]]+[[40+.5*(i % 2), i*2+2] for i in range(19)]+[[40, 40]]
    areas = [dict(id='e'*20, colour=BLUE, style='tatami', rings=[[[0, 0], *steps, [0, 40]]])]
    smoothed = layout(areas, apply(areas, {}, 'smooth', 'light', ['e'*20]))['pieces'][0]
    ring = np.asarray(smoothed['rings_mm'][0])
    corner = np.asarray(layout(areas, {})['pieces'][0]['rings_mm'][0])[0]   # the top-left corner
    assert np.linalg.norm(ring-corner, axis=1).min() < .15


def test_smooth_refuses_a_smooth_shape_and_unknown_strength():
    areas = [box('a', 0, 0, 40, 20)]
    with pytest.raises(ValueError, match='already smooth'):
        apply(areas, {}, 'smooth', 'light', ['a'*20])
    with pytest.raises(ValueError, match='Light or More'):
        apply([disc()], {}, 'smooth', 'lots', ['d'*20])


def setup(tmp_path, draw):
    from embroiderly.web import create_app
    rgba = np.zeros((400, 400, 4), np.uint8)
    draw(rgba)
    (tmp_path/'work/uploads').mkdir(parents=True)
    Image.fromarray(rgba).save(tmp_path/'work/uploads/p.png')
    client = create_app(tmp_path).test_client()
    options = {'height_mm': 80, 'floor_mm2': 1, 'smooth': 0, 'mask_holes_mm2': 0, 'count': 2}
    body = client.post('/artwork/p.png', json=dict(options=options)).get_json()
    assert body['report']['piece_layout']['pieces'], body.get('error')
    return client, options, body


def command(client, options, body, ids, field, value):
    done = client.post('/artwork/p.png', json=dict(
        options=options, piece_revision=body['piece_revision'], subject_confirmed=True,
        piece_command=dict(ids=ids, field=field, value=value))).get_json()
    assert done.get('options'), done.get('error')
    return done


def checked(tmp_path, client, done):
    from embroiderly.release_gate import checked_bytes
    stitched = client.post('/artwork/p.png', json=dict(options=done['options'], piece_revision=done['piece_revision'],
                                                        subject_confirmed=True, digitize=True)).get_json()
    assert stitched.get('playback'), stitched.get('error')
    assert len(stitched['playback']['colors']) == 1
    assert checked_bytes(tmp_path/'work'/'inkstitch-preview'/Path(stitched['prepared_name']).stem, 'dst')


def test_weld_route_passes_the_release_gate(tmp_path):
    def draw(rgba):
        rgba[100:220, 100:220] = [200, 30, 60, 255]
    client, options, body = setup(tmp_path, draw)
    first = body['report']['piece_layout']['pieces'][0]['id']
    copied = command(client, options, body, [first], 'duplicate', [10, 10])
    ids = [p['id'] for p in copied['report']['piece_layout']['pieces']]
    welded = command(client, copied['options'], copied, ids, 'weld', None)
    (piece,) = welded['report']['piece_layout']['pieces']
    assert piece['width_mm'] == pytest.approx(first_width(body)+10, abs=.3)
    checked(tmp_path, client, welded)


def first_width(body):
    return body['report']['piece_layout']['pieces'][0]['width_mm']


def test_smooth_route_passes_the_release_gate(tmp_path):
    def draw(rgba):
        rgba[..., :] = 0
        mask = np.zeros(rgba.shape[:2], np.uint8)
        cv2.circle(mask, (200, 200), 90, 1, -1)
        rgba[mask > 0] = [200, 30, 60, 255]
    client, options, body = setup(tmp_path, draw)
    before = body['report']['piece_layout']['pieces'][0]
    done = command(client, options, body, [before['id']], 'smooth', 'more')
    (after,) = done['report']['piece_layout']['pieces']
    assert after['area_mm2'] == pytest.approx(before['area_mm2'], rel=.01) and after['nodes'] < before['nodes']
    checked(tmp_path, client, done)
