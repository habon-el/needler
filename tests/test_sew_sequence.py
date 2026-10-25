"""Sewing order by hand: move a part earlier or later, or sew picked parts in a chosen order."""
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from test_sew_order import BLUE, RED, picture  # noqa: E402
from embroiderly.sew_sequence import arrange, choices  # noqa: E402

A, B, C, D = ('a'*20, 'b'*20, 'c'*20, 'd'*20)


def test_chosen_parts_follow_the_chosen_order():
    assert [[A, B, C][i] for i in arrange([A, B, C], [C, A, B])] == [C, A, B]


def test_unnamed_parts_keep_their_place_after_the_part_before_them():
    # D (new) and the unnamed speck stay right after the part sewn before them automatically.
    order = arrange([A, D, B, None, C], [B, A, C])
    assert [[A, D, B, None, C][i] for i in order] == [B, None, A, D, C]


@pytest.mark.parametrize('bad', ['abc', [A, A], ['XYZ'], [1], [A]*2001])
def test_bad_orders_are_refused(bad):
    with pytest.raises(ValueError):
        choices({'sew_sequence': bad})


def test_split_parts_keep_their_ids():
    # Each part cut out of its thread's mask traces to the same id the Pieces panel shows.
    from embroiderly.engine import hand_passes
    from embroiderly.region_stitches import regions
    rgba = picture()
    rgb, alpha = rgba[:, :, :3], rgba[:, :, 3] > 0
    passes = [(np.array(c), {'thread': '#%02x%02x%02x' % c}, (np.all(rgb == c, axis=2) & alpha).astype(np.uint8))
              for c in (BLUE, RED)]
    ids = [key for key, _, _ in regions(rgb, alpha)]
    reverse = list(reversed(ids))
    out = hand_passes(passes, reverse)
    assert len(out) == 3 and sum(int(m.sum()) for _, _, m in out) == sum(int(m.sum()) for _, _, m in passes)
    from embroiderly.region_stitches import region_id
    import cv2
    traced = []
    for _, _, mask in out:
        contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        outer = [i for i in range(len(contours)) if hierarchy[0, i, 3] == -1]
        rings = [contours[outer[0]]]+[contours[i] for i in range(len(contours)) if hierarchy[0, i, 3] == outer[0]]
        traced.append(region_id(rings))
    assert traced == reverse


def setup(tmp_path):
    from embroiderly.web import create_app
    (tmp_path/'work/uploads').mkdir(parents=True)
    Image.fromarray(picture()).save(tmp_path/'work/uploads/p.png')
    client = create_app(tmp_path).test_client()
    options = {'height_mm': 80, 'floor_mm2': 1, 'smooth': 0, 'mask_holes_mm2': 0, 'count': 2}
    body = client.post('/artwork/p.png', json=dict(options=options, subject_confirmed=True, digitize=True)).get_json()
    assert body.get('playback'), body.get('error')
    return client, options, body


def command(client, options, body, ids, value):
    return client.post('/artwork/p.png', json=dict(
        options=options, piece_revision=body['piece_revision'], subject_confirmed=True, digitize=True,
        piece_command=dict(ids=ids, field='sew_order', value=value))).get_json()


def test_hand_order_is_sewn_and_passes_the_release_gate(tmp_path):
    from embroiderly.release_gate import checked_bytes
    client, options, body = setup(tmp_path)
    automatic = body['playback']['sew_parts']
    assert len(automatic) == 3 and len(body['playback']['colors']) == 2
    # Move the last part (the cheek) to the front: the cheek, then the tail and the head.
    wanted = [automatic[-1]]+automatic[:-1]
    moved = command(client, options, body, [automatic[-1]], wanted)
    assert moved.get('playback'), moved.get('error')
    assert moved['options']['sew_sequence'] == wanted and moved['playback']['sew_parts'] == wanted
    assert checked_bytes(tmp_path/'work'/'inkstitch-preview'/Path(moved['prepared_name']).stem, 'dst')
    # Automatic order again.
    back = command(client, moved['options'], moved, [automatic[0]], None)
    assert 'sew_sequence' not in back['options'] and back['playback']['sew_parts'] == automatic


def test_hand_order_on_edited_pieces_passes_the_release_gate(tmp_path):
    from embroiderly.release_gate import checked_bytes
    client, options, body = setup(tmp_path)
    pieces = body['report']['piece_layout']['pieces']
    head = next(p for p in pieces if p['colour'] == '#%02x%02x%02x' % RED)
    moved = client.post('/artwork/p.png', json=dict(
        options=options, piece_revision=body['piece_revision'], subject_confirmed=True, digitize=True,
        piece_command=dict(ids=[head['id']], field='rotate_by', value=10))).get_json()
    assert moved.get('playback'), moved.get('error')
    automatic = moved['playback']['sew_parts']
    wanted = list(reversed(automatic))
    done = command(client, moved['options'], moved, [head['id']], wanted)
    assert done.get('playback'), done.get('error')
    assert done['playback']['sew_parts'] == wanted
    assert checked_bytes(tmp_path/'work'/'inkstitch-preview'/Path(done['prepared_name']).stem, 'dst')


def test_unknown_parts_are_refused(tmp_path):
    client, options, body = setup(tmp_path)
    parts = body['playback']['sew_parts']
    refused = command(client, options, body, [parts[0]], parts+['e'*20])
    assert 'parts changed' in (refused.get('error') or '')


def test_the_lock_guard_allows_a_new_sewing_order():
    # The order moves no piece, so saving it never trips a lock.
    from embroiderly.piece_layout import guard
    previous = {'piece_edits': {A: {'locked': True}}, 'count': 2}
    guard(previous, {**previous, 'sew_sequence': [B, A]})
    with pytest.raises(ValueError):
        guard(previous, {**previous, 'count': 3})
