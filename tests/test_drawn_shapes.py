"""Drawn shapes: rectangle, ellipse, polygon and freehand outlines become new pieces."""
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_piece_editing import AREA, layout, piece, route_setup  # noqa: E402
from embroiderly.piece_layout import change, copy_ids  # noqa: E402


def draw(options, shape, points, colour='#c81e1e'):
    return change(options, layout(options), dict(ids=[], field='draw', value=dict(shape=shape, points=points, colour=colour)))


def drawn(options):
    return [p for p in layout(options)['pieces'] if p['id'] != AREA['id']]


@pytest.mark.parametrize('shape,points,area', [
    ('rectangle', [[30, 10], [10, 20]], 200),
    ('ellipse', [[10, 10], [30, 20]], math.pi*10*5),
    ('polygon', [[10, 10], [30, 10], [20, 30]], 200),
    ('freehand', [[10+10*math.cos(t/10), 10+10*math.sin(t/10)] for t in range(63)], math.pi*100),
])
def test_each_shape_becomes_a_piece_where_it_was_drawn(shape, points, area):
    before = piece({})
    options = draw({}, shape, points)
    (new,) = drawn(options)
    assert new['colour'] == '#c81e1e' and new['copy'] and new['name'].startswith(shape.capitalize())
    assert new['area_mm2'] == pytest.approx(area, rel=.03)
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    assert new['x_mm'] == pytest.approx((min(xs)+max(xs))/2, abs=.1)
    assert new['y_mm'] == pytest.approx((min(ys)+max(ys))/2, abs=.1)
    # The picture's pieces stay exactly where they were.
    assert piece(options)['rings_mm'] == before['rings_mm']


def test_drawn_shapes_can_be_edited_copied_cut_and_deleted():
    options = draw({}, 'rectangle', [[10, 10], [30, 20]])
    (new,) = drawn(options)
    moved = change(options, layout(options), dict(ids=[new['id']], field='x_mm', value=40))
    assert drawn(moved)[0]['x_mm'] == pytest.approx(40)
    copied = change(options, layout(options), dict(ids=[new['id']], field='duplicate', value=[0, 15]))
    assert len(drawn(copied)) == 2
    cut = change(options, layout(options), dict(ids=[new['id']], field='knife', value=[[20, 0], [20, 40]]))
    assert len(drawn(cut)) == 2
    # Deleting a drawn shape takes its copies with it; picture pieces are never deleted.
    gone = change(copied, layout(copied), dict(ids=[new['id']], field='delete', value=True))
    assert not drawn(gone) and not copy_ids(gone)


def test_invalid_drawings_are_refused():
    with pytest.raises(ValueError, match='too small'):
        draw({}, 'rectangle', [[10, 10], [10.5, 10.5]])
    with pytest.raises(ValueError, match='three points'):
        draw({}, 'polygon', [[10, 10], [20, 10]])
    with pytest.raises(ValueError, match='rectangle, ellipse'):
        draw({}, 'star', [[10, 10], [20, 20]])
    with pytest.raises(ValueError, match='thread colour'):
        draw({}, 'rectangle', [[10, 10], [20, 20]], colour='red')


def test_drawn_shape_stitches_pass_the_release_gate(tmp_path):
    from embroiderly.release_gate import checked_bytes
    client, options, r = route_setup(tmp_path)
    p = r['report']['piece_layout']['pieces'][0]
    corner = [p['x_mm']+p['width_mm']/2+5, p['y_mm']]
    value = dict(shape='ellipse', points=[corner, [corner[0]+15, corner[1]+10]], colour='#c81e1e')
    response = client.post('/artwork/p.png', json=dict(options=options, piece_revision=r['piece_revision'],
                                                        subject_confirmed=True, digitize=True,
                                                        piece_command=dict(ids=[], field='draw', value=value)))
    body = response.get_json()
    assert response.status_code == 200, body
    pieces = body['report']['piece_layout']['pieces']
    assert len(pieces) == len(r['report']['piece_layout']['pieces'])+1
    assert body.get('playback'), body.get('error')
    assert '#c81e1e' in {p['colour'] for p in pieces}
    assert checked_bytes(tmp_path/'work'/'inkstitch-preview'/Path(body['prepared_name']).stem, 'dst')
