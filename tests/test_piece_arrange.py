"""Line up several pieces: align, space evenly, same size."""
from pathlib import Path

import pytest

from embroiderly.piece_layout import change, inventory

A, B, C = 'a'*20, 'b'*20, 'c'*20
AREAS = [dict(id=A, colour='#1e5ac8', style='tatami', rings=[[[0, 0], [40, 0], [40, 20], [0, 20]]]),       # 20 × 10 mm
         dict(id=B, colour='#c81e1e', style='tatami', rings=[[[60, 40], [80, 40], [80, 80], [60, 80]]]),   # 10 × 20 mm
         dict(id=C, colour='#1ec85a', style='tatami', rings=[[[150, 0], [160, 0], [160, 10], [150, 10]]])]  # 5 × 5 mm


def layout(options):
    return inventory({'areas': AREAS}, options, 200, 100, .5)


def apply(options, field, value, ids=(A, B, C)):
    return change(options, layout(options), dict(ids=list(ids), field=field, value=value))


def boxes(options):
    return {p['id']: (p['x_mm']-p['width_mm']/2, p['y_mm']-p['height_mm']/2,
                      p['x_mm']+p['width_mm']/2, p['y_mm']+p['height_mm']/2) for p in layout(options)['pieces']}


@pytest.mark.parametrize('value,side', [('left', 0), ('top', 1), ('right', 2), ('bottom', 3)])
def test_align_lines_up_the_edges_on_the_selection_edge(value, side):
    before, after = boxes({}), boxes(apply({}, 'align', value))
    target = (min if side < 2 else max)(b[side] for b in before.values())
    assert [b[side] for b in after.values()] == pytest.approx([target]*3)
    # Only the one direction moves; sizes stay.
    other = 1-side % 2
    for key in before:
        assert after[key][other] == pytest.approx(before[key][other])
        assert after[key][2]-after[key][0] == pytest.approx(before[key][2]-before[key][0])


def test_align_centre_and_middle_use_the_selection_centre():
    before = boxes({})
    after = boxes(apply(apply({}, 'align', 'centre'), 'align', 'middle'))
    cx = (min(b[0] for b in before.values())+max(b[2] for b in before.values()))/2
    cy = (min(b[1] for b in before.values())+max(b[3] for b in before.values()))/2
    for b in after.values():
        assert ((b[0]+b[2])/2, (b[1]+b[3])/2) == pytest.approx((cx, cy))


def test_space_evenly_keeps_the_outer_pieces_and_evens_the_gaps():
    before = boxes({})
    after = boxes(apply({}, 'distribute', 'across'))
    assert after[A] == pytest.approx(before[A]) and after[C] == pytest.approx(before[C])
    gaps = [after[B][0]-after[A][2], after[C][0]-after[B][2]]
    assert gaps[0] == pytest.approx(gaps[1]) and gaps[0] > 0
    assert after[B][1] == pytest.approx(before[B][1])
    # Down: sorted by vertical centre (C, A, B), the outer two stay put.
    down = boxes(apply({}, 'distribute', 'down'))
    assert down[C] == pytest.approx(before[C]) and down[B] == pytest.approx(before[B])
    assert down[A][1]-down[C][3] == pytest.approx(down[B][1]-down[A][3])


def test_same_size_follows_the_first_piece_picked():
    first = boxes({})[B]
    w, h = first[2]-first[0], first[3]-first[1]
    width = boxes(apply({}, 'match_size', 'width', (B, A, C)))
    for key in (A, C):
        assert width[key][2]-width[key][0] == pytest.approx(w)
    # Proportions are kept: A was 2:1, C square.
    assert width[A][3]-width[A][1] == pytest.approx(w/2) and width[C][3]-width[C][1] == pytest.approx(w)
    height = boxes(apply({}, 'match_size', 'height', (B, A, C)))
    assert height[A][3]-height[A][1] == pytest.approx(h) and height[A][2]-height[A][0] == pytest.approx(2*h)
    both = boxes(apply({}, 'match_size', 'both', (B, A, C)))
    for key in (A, C):
        assert (both[key][2]-both[key][0], both[key][3]-both[key][1]) == pytest.approx((w, h))
    # Each piece keeps its own centre, and the first is unchanged.
    assert both[B] == pytest.approx(first)
    before = boxes({})[C]
    assert (both[C][0]+both[C][2], both[C][1]+both[C][3]) == pytest.approx((before[0]+before[2], before[1]+before[3]))


def test_needs_enough_pieces_valid_choices_and_no_locks():
    with pytest.raises(ValueError, match='at least two'):
        apply({}, 'align', 'left', (A,))
    with pytest.raises(ValueError, match='at least three'):
        apply({}, 'distribute', 'across', (A, B))
    with pytest.raises(ValueError, match='Choose'):
        apply({}, 'align', 'sideways')
    locked = apply({}, 'locked', True, (B,))
    for field, value in (('align', 'left'), ('distribute', 'down'), ('match_size', 'both')):
        with pytest.raises(ValueError, match='locked'):
            apply(locked, field, value)
    # Unselected locked pieces do not block the others.
    assert boxes(apply(locked, 'align', 'bottom', (A, C)))[C][3] == pytest.approx(boxes({})[A][3])


@pytest.mark.parametrize('field,value,order', [('align', 'top', (0, 1, 2)), ('distribute', 'across', (0, 1, 2)),
                                               ('match_size', 'both', (1, 0, 2))])
def test_lined_up_pieces_rebuild_stitches_that_pass_the_release_gate(tmp_path, field, value, order):
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from test_piece_layout import make_image, sample
    from embroiderly.release_gate import checked_bytes
    from embroiderly.web import create_app
    client = create_app(tmp_path).test_client()
    make_image(tmp_path/'work/uploads/p.png')
    _, options = sample()
    r = client.post('/artwork/p.png', json={'options': options}).get_json()
    original = r['report']['piece_layout']['pieces'][0]['id']
    # Two smaller copies of the 40 mm square, up right and down left, apart from it.
    options = {**options, 'piece_edits': {'1'*20: {'source': original, 'matrix': [.4, 0, 0, .4, 35, -30]},
                                          '2'*20: {'source': original, 'matrix': [.4, 0, 0, .4, -30, 30]}}}
    ids = [[original, '1'*20, '2'*20][i] for i in order]
    response = client.post('/artwork/p.png', json=dict(options=options, piece_revision=r['piece_revision'],
                                                        subject_confirmed=True,
                                                        piece_command=dict(ids=ids, field=field, value=value)))
    body = response.get_json()
    assert response.status_code == 200, body
    assert body.get('playback') and not body.get('piece_blocked'), body.get('error')
    pieces = body['report']['piece_layout']['pieces']
    assert len(pieces) == 3
    if field == 'align':
        assert len({round(p['y_mm']-p['height_mm']/2, 3) for p in pieces}) == 1
    elif field == 'match_size':
        assert all(p['width_mm'] == pytest.approx(16, abs=.05) for p in pieces)
    assert checked_bytes(tmp_path/'work'/'inkstitch-preview'/Path(body['prepared_name']).stem, 'dst')
