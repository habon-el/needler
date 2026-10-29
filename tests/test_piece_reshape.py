"""Node reshaping: move, add and delete a piece's outline points; stitches follow the new shape."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_piece_editing import AREA, apply, layout, piece, route_setup  # noqa: E402
from embroiderly.piece_layout import change, copy_ids  # noqa: E402


def flat(ring):
    return [v for q in ring for v in q]


def corners(options):
    return [list(map(float, q)) for q in piece(options)['rings_mm'][0]]


def test_moving_a_point_changes_the_shape_and_keeps_the_piece():
    styled = apply({}, 'style', 'step')
    ring = corners(styled)
    ring[2] = [ring[2][0]+10, ring[2][1]+5]          # pull one corner out
    moved = apply(styled, 'reshape', [ring])
    p = piece(moved)
    assert p['id'] == AREA['id'] and p['nodes'] == 4 and moved['region_styles'][AREA['id']] == 'step'
    assert flat(p['rings_mm'][0]) == pytest.approx(flat(ring))
    assert p['area_mm2'] > piece(styled)['area_mm2']
    # The new outline moves, turns and copies like any piece.
    shifted = apply(moved, 'x_mm', p['x_mm']+20)
    assert piece(shifted)['rings_mm'][0][2][0] == pytest.approx(ring[2][0]+20)
    copied = apply(moved, 'duplicate', [0, 30])
    (copy,) = copy_ids(copied)
    assert piece(copied, copy)['area_mm2'] == pytest.approx(p['area_mm2'])


def test_adding_and_deleting_points():
    ring = corners({})
    middle = [(ring[0][0]+ring[1][0])/2, ring[0][1]-6]   # a new point on the top edge, pulled up
    added = apply({}, 'reshape', [ring[:1]+[middle]+ring[1:]])
    assert piece(added)['nodes'] == 5 and piece(added)['area_mm2'] > piece({})['area_mm2']
    triangle = apply(added, 'reshape', [corners(added)[:-1]])
    assert piece(triangle)['nodes'] == 4
    with pytest.raises(ValueError, match='three points'):
        apply({}, 'reshape', [ring[:2]])


def test_a_bad_outline_is_refused():
    ring = corners({})
    with pytest.raises(ValueError, match='crosses itself'):
        apply({}, 'reshape', [[ring[0], ring[2], ring[1], ring[3]]])
    with pytest.raises(ValueError, match='too small'):
        apply({}, 'reshape', [[[0, 0], [0.5, 0], [0.5, 0.5]]])
    with pytest.raises(ValueError, match='locked'):
        apply(apply({}, 'locked', True), 'reshape', [ring])
    with pytest.raises(ValueError):
        apply({}, 'reshape', [ring, ring])          # the same rings, no new ones


def test_a_turned_piece_keeps_its_turn():
    turned = apply({}, 'rotation', 30)
    ring = corners(turned)
    ring[0] = [ring[0][0]-3, ring[0][1]-3]
    p = piece(apply(turned, 'reshape', [ring]))
    assert p['rotation'] == pytest.approx(30) and flat(p['rings_mm'][0]) == pytest.approx(flat(ring), abs=.02)


def test_drawn_lines_can_be_reshaped():
    options = change({}, layout({}), dict(ids=[], field='draw', value=dict(shape='line', points=[[0, 0], [20, 0]], colour='#202020')))
    line = next(p for p in layout(options)['pieces'] if p.get('line'))
    bent = change(options, layout(options), dict(ids=[line['id']], field='reshape', value=[[[0, 0], [10, 8], [20, 0]]]))
    assert next(p for p in layout(bent)['pieces'] if p.get('line'))['nodes'] == 3


def test_reshaped_pieces_rebuild_stitches_that_pass_the_release_gate(tmp_path):
    from embroiderly.release_gate import checked_bytes
    client, options, r = route_setup(tmp_path)
    p = r['report']['piece_layout']['pieces'][0]
    ring = p['rings_mm'][0]
    # A new point halfway along the first edge, pulled 1 mm out from the piece's centre.
    (x0, y0), (x1, y1) = ring[0], ring[1]
    mx, my = (x0+x1)/2, (y0+y1)/2
    dx, dy = mx-p['x_mm'], my-p['y_mm']
    length = (dx*dx+dy*dy) ** .5 or 1
    new = [ring[0], [mx+dx/length, my+dy/length], *ring[1:]]
    response = client.post('/artwork/p.png', json=dict(options=options, piece_revision=r['piece_revision'], subject_confirmed=True,
                                                        piece_command=dict(ids=[p['id']], field='reshape', value=[new, *p['rings_mm'][1:]])))
    body = response.get_json()
    assert response.status_code == 200, body
    assert body.get('playback'), body.get('error')
    after = next(q for q in body['report']['piece_layout']['pieces'] if q['id'] == p['id'])
    assert after['nodes'] == p['nodes']+1
    assert checked_bytes(tmp_path/'work'/'inkstitch-preview'/Path(body['prepared_name']).stem, 'dst')
