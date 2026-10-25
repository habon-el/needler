"""Repeat pieces: mirror copy, circle layout (upright or turned like a wreath) and array."""
import math
from pathlib import Path

import pytest

from embroiderly.piece_layout import MAX_COPIES, change, copy_ids, inventory

AREA = dict(id='a'*20, colour='#1e5ac8', style='tatami',
            rings=[[[0, 0], [40, 0], [40, 20], [0, 20]]])   # a 40 × 20 px box; 0.5 mm per px → 20 × 10 mm
TRIANGLE = dict(id='b'*20, colour='#c81e1e', style='tatami',
                rings=[[[0, 0], [40, 0], [0, 20]]])          # the right angle on the left


def layout(options, areas=(AREA,)):
    return inventory({'areas': list(areas)}, options, 100, 100, .5)


def apply(options, field, value, ids=('a'*20,), areas=(AREA,)):
    return change(options, layout(options, areas), dict(ids=list(ids), field=field, value=value))


def pieces(options, areas=(AREA,)):
    return layout(options, areas)['pieces']


def copies(options, areas=(AREA,)):
    keys = copy_ids(options)
    return [p for p in pieces(options, areas) if p['id'] in keys]


def test_mirror_copy_reflects_across_the_right_edge_and_keeps_the_style():
    styled = apply({}, 'style', 'step', areas=(TRIANGLE,), ids=('b'*20,))
    original = pieces(styled, (TRIANGLE,))[0]
    options = apply(styled, 'mirror_copy', 'x', areas=(TRIANGLE,), ids=('b'*20,))
    (copy,) = copies(options, (TRIANGLE,))
    right = original['x_mm']+original['width_mm']/2
    # Touching on the right: the copy starts where the original ends and is as wide.
    assert copy['x_mm']-copy['width_mm']/2 == pytest.approx(right)
    assert copy['width_mm'] == pytest.approx(original['width_mm']) and copy['y_mm'] == pytest.approx(original['y_mm'])
    # The right angle, on the original's left, is on the copy's right: it is reflected, not moved.
    corner = max(copy['rings_mm'][0], key=lambda q: q[1])
    assert corner[0] == pytest.approx(copy['x_mm']+copy['width_mm']/2)
    assert options['region_styles'][copy['id']] == 'step' and copy['name'].endswith('mirror')
    # Top-bottom: below, touching the bottom edge.
    (below,) = copies(apply({}, 'mirror_copy', 'y'))
    assert below['y_mm'] == pytest.approx(pieces({})[0]['y_mm']+10)
    with pytest.raises(ValueError, match='Mirror copy'):
        apply({}, 'mirror_copy', 'z')


def test_circle_places_copies_evenly_around_and_turns_them_like_a_wreath():
    original = pieces({})[0]
    for turn in (True, False):
        options = apply({}, 'circle', dict(count=6, radius_mm=30, turn=turn))
        made = copies(options)
        assert len(made) == 5 and len(pieces(options)) == 6
        centre = (original['x_mm'], original['y_mm']+30)
        for p in made:
            assert math.hypot(p['x_mm']-centre[0], p['y_mm']-centre[1]) == pytest.approx(30)
        angles = sorted(round(p['rotation']) for p in made)
        assert angles == ([60, 120, 180, 240, 300] if turn else [0]*5)
        # The copy at the bottom is upside down in a wreath (the box is the same size), upright otherwise.
        bottom = max(made, key=lambda p: p['y_mm'])
        assert bottom['y_mm'] == pytest.approx(original['y_mm']+60)
        assert bottom['width_mm'] == pytest.approx(original['width_mm'])
    # A turned copy at 90° stands on its side.
    side = copies(apply({}, 'circle', dict(count=4, radius_mm=20, turn=True)))
    assert sorted(round(p['width_mm']) for p in side) == [10, 10, 20]


def test_array_makes_rows_and_columns_with_the_gap():
    original = pieces({})[0]
    options = apply({}, 'array', dict(rows=2, columns=3, gap_mm=5))
    made = copies(options)
    assert len(made) == 5
    xs = sorted({round(p['x_mm'], 3) for p in pieces(options)})
    ys = sorted({round(p['y_mm'], 3) for p in pieces(options)})
    assert xs == pytest.approx([original['x_mm']+i*25 for i in range(3)])
    assert ys == pytest.approx([original['y_mm'], original['y_mm']+15])
    # Each copy is its own piece: moving one leaves the others.
    first = made[0]
    moved = change(options, layout(options), dict(ids=[first['id']], field='x_mm', value=first['x_mm']+40))
    assert sorted(round(p['x_mm'], 3) for p in pieces(moved) if p['id'] != first['id']) == \
        sorted(round(p['x_mm'], 3) for p in pieces(options) if p['id'] != first['id'])


def test_a_multi_selection_repeats_as_one_group():
    areas = (AREA, {**TRIANGLE, 'rings': [[[60, 0], [100, 0], [60, 20]]]})
    options = apply({}, 'array', dict(rows=1, columns=2, gap_mm=0), ids=('a'*20, 'b'*20), areas=areas)
    made = copies(options, areas)
    # One step is the whole group's width (0..100 px = 50 mm), not each piece's own.
    assert len(made) == 2
    by_source = {options['piece_edits'][p['id']]['source']: p for p in made}
    for p in pieces({}, areas):
        assert by_source[p['id']]['x_mm'] == pytest.approx(p['x_mm']+50)


def test_copies_of_a_copy_point_to_the_original():
    options = apply({}, 'duplicate', [25, 0])
    (copy,) = copy_ids(options)
    again = apply(options, 'mirror_copy', 'x', ids=(copy,))
    assert {item['source'] for item in again['piece_edits'].values()} == {'a'*20}


@pytest.mark.parametrize('field,value,message', [
    ('circle', dict(count=1, radius_mm=30, turn=True), '2 to 36'),
    ('circle', dict(count=37, radius_mm=30, turn=True), '2 to 36'),
    ('circle', dict(count=6.5, radius_mm=30, turn=True), '2 to 36'),
    ('circle', dict(count=6, radius_mm=0, turn=True), 'radius'),
    ('circle', dict(count=6, radius_mm=float('nan'), turn=True), 'radius'),
    ('circle', dict(count=6, radius_mm=30), 'how many'),
    ('circle', dict(count=6, radius_mm=30, turn='yes'), 'how many'),
    ('array', dict(rows=1, columns=1, gap_mm=2), 'more than one'),
    ('array', dict(rows=21, columns=1, gap_mm=2), 'rows'),
    ('array', dict(rows=2, columns=0, gap_mm=2), 'columns'),
    ('array', dict(rows=2, columns=2, gap_mm=-1), 'gap'),
    ('array', [2, 2], 'rows, columns'),
])
def test_bad_values_are_refused(field, value, message):
    with pytest.raises(ValueError, match=message):
        apply({}, field, value)


def test_copy_limit_and_locks_are_respected():
    with pytest.raises(ValueError, match=f'at most {MAX_COPIES}'):
        apply({}, 'array', dict(rows=11, columns=10, gap_mm=0))
    full = apply({}, 'array', dict(rows=10, columns=10, gap_mm=0))
    assert len(copy_ids(full)) == 99
    with pytest.raises(ValueError, match=r'\(1 more\)'):
        apply(full, 'circle', dict(count=3, radius_mm=10, turn=False))
    locked = apply({}, 'locked', True)
    for field, value in (('mirror_copy', 'x'), ('circle', dict(count=3, radius_mm=10, turn=True)),
                         ('array', dict(rows=1, columns=2, gap_mm=1))):
        with pytest.raises(ValueError, match='locked'):
            apply(locked, field, value)


def route_setup(tmp_path):
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from test_piece_layout import make_image, sample
    from embroiderly.web import create_app
    client = create_app(tmp_path).test_client()
    make_image(tmp_path/'work/uploads/p.png')
    _, options = sample()
    # The sample is one 40 mm part: a larger hoop leaves room for its copies.
    options['piece_hoop_mm'] = [200, 200]
    response = client.post('/artwork/p.png', json={'options': options}).get_json()
    return client, options, response


@pytest.mark.parametrize('field,value,added', [
    ('mirror_copy', 'y', 1),
    ('circle', dict(count=4, radius_mm=30, turn=True), 3),
    ('array', dict(rows=2, columns=2, gap_mm=1), 3),
])
def test_repeats_rebuild_stitches_that_pass_the_release_gate(tmp_path, field, value, added):
    from embroiderly.release_gate import checked_bytes
    client, options, r = route_setup(tmp_path)
    before = r['report']['piece_layout']['pieces']
    p = min(before, key=lambda q: q['area_mm2'])
    # No digitize flag: the command itself asks for the stitches to be rebuilt.
    response = client.post('/artwork/p.png', json=dict(options=options, piece_revision=r['piece_revision'],
                                                        subject_confirmed=True,
                                                        piece_command=dict(ids=[p['id']], field=field, value=value)))
    body = response.get_json()
    assert response.status_code == 200, body
    assert len(body['report']['piece_layout']['pieces']) == len(before)+added
    assert body.get('playback') and not body.get('piece_blocked'), body.get('error')
    # Copies share their original's thread: no new colour blocks.
    assert len(body['playback']['colors']) == len({q['colour'] for q in body['report']['piece_layout']['pieces']})
    assert checked_bytes(tmp_path/'work'/'inkstitch-preview'/Path(body['prepared_name']).stem, 'dst')
