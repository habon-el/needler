"""Piece editing: mirror, rotate by steps, skew, duplicate with offset, delete copies."""
import pytest

from embroiderly.piece_layout import change, copy_ids, inventory

AREA = dict(id='a'*20, colour='#1e5ac8', style='tatami',
            rings=[[[0, 0], [40, 0], [40, 20], [0, 20]]])   # a 40 × 20 px box; 0.5 mm per px


def layout(options):
    return inventory({'areas': [AREA]}, options, 100, 100, .5)


def apply(options, field, value, ids=('a'*20,)):
    return change(options, layout(options), dict(ids=list(ids), field=field, value=value))


def piece(options, key='a'*20):
    return next(p for p in layout(options)['pieces'] if p['id'] == key)


def xs(p):
    return [x for ring in p['rings_mm'] for x, _ in ring]


def test_mirror_flips_the_outline_in_place_and_the_rotation():
    rotated = apply({}, 'rotation', 30)
    mirrored = apply(rotated, 'mirror', 'x')
    before, after = piece(rotated), piece(mirrored)
    assert after['x_mm'] == pytest.approx(before['x_mm']) and after['width_mm'] == pytest.approx(before['width_mm'])
    assert after['rotation'] == pytest.approx(330)
    # Mirroring twice returns the original outline.
    back = piece(apply(mirrored, 'mirror', 'x'))
    assert sorted(xs(back)) == pytest.approx(sorted(xs(before)))
    with pytest.raises(ValueError):
        apply({}, 'mirror', 'z')


def test_rotate_by_steps_add_up():
    options = apply(apply({}, 'rotate_by', 15), 'rotate_by', 45)
    assert piece(options)['rotation'] == pytest.approx(60)
    options = apply(options, 'rotate_by', -90)
    assert piece(options)['rotation'] == pytest.approx(330)


def test_skew_leans_the_shape_and_is_limited():
    skewed = piece(apply({}, 'skew', 30))
    assert skewed['width_mm'] > piece({})['width_mm']
    assert skewed['height_mm'] == pytest.approx(piece({})['height_mm'])
    with pytest.raises(ValueError):
        apply({}, 'skew', 75)


def test_duplicate_makes_an_independent_piece_with_offset_and_style():
    styled = apply({}, 'style', 'step')
    options = apply(styled, 'duplicate', [25, 0])
    (copy,) = copy_ids(options)
    pieces = layout(options)['pieces']
    assert len(pieces) == 2 and options['region_styles'][copy] == 'step'
    assert piece(options, copy)['x_mm'] == pytest.approx(piece(options)['x_mm']+25)
    assert piece(options, copy)['colour'] == AREA['colour'] and 'copy' in piece(options, copy)['name']
    # Moving the original does not move the copy.
    moved = apply(options, 'x_mm', piece(options)['x_mm']-10)
    assert piece(moved, copy)['x_mm'] == pytest.approx(piece(options, copy)['x_mm'])
    # A second copy gets its own identity.
    assert len(copy_ids(apply(options, 'duplicate', [0, 15]))) == 2


def test_only_copies_can_be_deleted():
    options = apply({}, 'duplicate', [25, 0])
    (copy,) = copy_ids(options)
    with pytest.raises(ValueError, match='Only copied pieces'):
        apply(options, 'delete', True)
    cleared = apply(options, 'delete', True, [copy])
    assert not copy_ids(cleared) and len(layout(cleared)['pieces']) == 1


def test_locked_pieces_refuse_every_new_command():
    locked = apply({}, 'locked', True)
    for field, value in (('mirror', 'x'), ('rotate_by', 15), ('skew', 10), ('duplicate', [5, 5])):
        with pytest.raises(ValueError, match='locked'):
            apply(locked, field, value)


def route_setup(tmp_path):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from test_piece_layout import make_image, sample
    from embroiderly.web import create_app
    client = create_app(tmp_path).test_client()
    make_image(tmp_path/'work/uploads/p.png')
    _, options = sample()
    response = client.post('/artwork/p.png', json={'options': options}).get_json()
    return client, options, response


@pytest.mark.parametrize('field,value', [('mirror', 'x'), ('rotate_by', 45), ('skew', 15), ('duplicate', [30, 0])])
def test_each_command_rebuilds_stitches_that_pass_the_release_gate(tmp_path, field, value):
    from embroiderly.release_gate import checked_bytes
    client, options, r = route_setup(tmp_path)
    key = r['report']['piece_layout']['pieces'][0]['id']
    response = client.post('/artwork/p.png', json=dict(options=options, piece_revision=r['piece_revision'],
                                                        subject_confirmed=True, digitize=True,
                                                        piece_command=dict(ids=[key], field=field, value=value)))
    body = response.get_json()
    assert response.status_code == 200, body
    assert body.get('playback') and not body.get('piece_blocked'), body.get('error')
    pieces = body['report']['piece_layout']['pieces']
    assert len(pieces) == (len(r['report']['piece_layout']['pieces'])+1 if field == 'duplicate' else len(r['report']['piece_layout']['pieces']))
    assert checked_bytes(tmp_path/'work'/'inkstitch-preview'/__import__('pathlib').Path(body['prepared_name']).stem, 'dst')


def test_knife_cuts_a_piece_into_two_parts_in_place():
    styled = apply({}, 'style', 'step')
    whole = piece(styled)
    # A vertical cut through the middle of the 20 × 10 mm box.
    line = [[whole['x_mm'], whole['y_mm']-20], [whole['x_mm'], whole['y_mm']+20]]
    cut = apply(styled, 'knife', line)
    parts = layout(cut)['pieces']
    assert len(parts) == 2 and all(p['id'] != 'a'*20 for p in parts)
    assert sum(p['area_mm2'] for p in parts) == pytest.approx(whole['area_mm2'], rel=.02)
    assert all(cut['region_styles'][p['id']] == 'step' for p in parts)
    assert sorted(round(p['width_mm'], 1) for p in parts) == [10.0, 10.0]
    # A part can be cut again, moved on its own, duplicated and deleted.
    first = parts[0]
    again = change(cut, layout(cut), dict(ids=[first['id']], field='knife',
                                          value=[[first['x_mm']-20, first['y_mm']], [first['x_mm']+20, first['y_mm']]]))
    assert len(layout(again)['pieces']) == 3
    copied = change(cut, layout(cut), dict(ids=[first['id']], field='duplicate', value=[30, 0]))
    assert len(layout(copied)['pieces']) == 3


def test_knife_must_cross_the_piece():
    whole = piece({})
    with pytest.raises(ValueError, match='cross the piece'):
        apply({}, 'knife', [[whole['x_mm']+50, -100], [whole['x_mm']+50, 100]])
    with pytest.raises(ValueError, match='locked'):
        apply(apply({}, 'locked', True), 'knife', [[whole['x_mm'], -100], [whole['x_mm'], 100]])


def test_cut_pieces_rebuild_stitches_that_pass_the_release_gate(tmp_path):
    from pathlib import Path
    from embroiderly.release_gate import checked_bytes
    client, options, r = route_setup(tmp_path)
    p = r['report']['piece_layout']['pieces'][0]
    line = [[p['x_mm'], p['y_mm']-p['height_mm']], [p['x_mm'], p['y_mm']+p['height_mm']]]
    response = client.post('/artwork/p.png', json=dict(options=options, piece_revision=r['piece_revision'],
                                                        subject_confirmed=True, digitize=True,
                                                        piece_command=dict(ids=[p['id']], field='knife', value=line)))
    body = response.get_json()
    assert response.status_code == 200, body
    assert len(body['report']['piece_layout']['pieces']) == len(r['report']['piece_layout']['pieces'])+1
    assert body.get('playback'), body.get('error')
    assert checked_bytes(tmp_path/'work'/'inkstitch-preview'/Path(body['prepared_name']).stem, 'dst')


def test_applique_pieces_still_pass_after_piece_edits(tmp_path):
    """The satin cover of an appliqué piece lies half outside it; edited pieces must allow that band."""
    from pathlib import Path
    from embroiderly.release_gate import checked_bytes
    client, options, r = route_setup(tmp_path)
    p = max(r['report']['piece_layout']['pieces'], key=lambda q: q['area_mm2'])
    for field, value in (('style', 'applique'), ('rotate_by', 15)):
        response = client.post('/artwork/p.png', json=dict(options=options, piece_revision=r['piece_revision'],
                                                            subject_confirmed=True, digitize=True,
                                                            piece_command=dict(ids=[p['id']], field=field, value=value)))
        r = response.get_json()
        assert response.status_code == 200, r
        options = r['options']
    assert r.get('playback'), r.get('error')
    assert checked_bytes(tmp_path/'work'/'inkstitch-preview'/Path(r['prepared_name']).stem, 'dst')


def test_duplicates_do_not_add_colour_changes(tmp_path):
    client, options, r = route_setup(tmp_path)
    pieces = r['report']['piece_layout']['pieces']
    first = pieces[0]
    response = client.post('/artwork/p.png', json=dict(options=options, piece_revision=r['piece_revision'],
                                                        subject_confirmed=True, digitize=True,
                                                        piece_command=dict(ids=[first['id']], field='duplicate', value=[0, 30])))
    body = response.get_json()
    assert response.status_code == 200, body
    colours = {p['colour'] for p in body['report']['piece_layout']['pieces']}
    assert len(body['playback']['colors']) == len(colours)
