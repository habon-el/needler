"""Hoop picker: hoops by machine brand, the user's own hoops, a turned hoop, and the chosen hoop
in the piece checks and on the worksheet."""
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from test_sew_order import picture  # noqa: E402
from embroiderly import hoops  # noqa: E402


def test_listed_hoops_have_unique_ids_and_sensible_sizes():
    listed = [h for group in hoops.listed() for h in group['hoops']]
    assert len({h['id'] for h in listed}) == len(listed)
    assert all(hoops.MIN_MM <= h['width_mm'] <= hoops.MAX_MM and hoops.MIN_MM <= h['height_mm'] <= hoops.MAX_MM for h in listed)
    assert hoops.find(Path('.'), hoops.DEFAULT)['width_mm'] == 100


def test_own_hoops_are_saved_found_and_deleted(tmp_path):
    saved = hoops.save(tmp_path, dict(name=' Big frame ', width_mm=300, height_mm=200.04))
    mine = saved[0]
    assert mine['name'] == 'Big frame' and mine['height_mm'] == 200.0 and mine['id'].startswith('mine-')
    assert hoops.find(tmp_path, mine['id'])['brand'] == 'My hoops'
    assert hoops.delete(tmp_path, mine['id']) == [] and hoops.find(tmp_path, mine['id']) is None
    with pytest.raises(ValueError):
        hoops.delete(tmp_path, mine['id'])


@pytest.mark.parametrize('body', [None, dict(name='', width_mm=100, height_mm=100), dict(name='x'*41, width_mm=100, height_mm=100),
                                  dict(name='A', width_mm=5, height_mm=100), dict(name='A', width_mm=100, height_mm='big'),
                                  dict(name='A', width_mm=float('nan'), height_mm=100)])
def test_bad_hoops_are_refused(tmp_path, body):
    with pytest.raises(ValueError):
        hoops.save(tmp_path, body)


def test_at_most_fifty_own_hoops(tmp_path):
    for n in range(hoops.MAX_SAVED):
        hoops.save(tmp_path, dict(name=f'H{n}', width_mm=100, height_mm=100))
    with pytest.raises(ValueError, match='up to 50'):
        hoops.save(tmp_path, dict(name='one more', width_mm=100, height_mm=100))


def test_hoop_routes(tmp_path):
    from embroiderly.web import create_app
    client = create_app(tmp_path).test_client()
    body = client.get('/api/hoops').get_json()
    assert {g['brand'] for g in body['brands']} >= {'Common sizes', 'Brother', 'Janome'} and body['saved'] == []
    saved = client.post('/api/hoops', json=dict(name='Frame', width_mm=250, height_mm=180)).get_json()['saved']
    assert client.get('/api/hoops').get_json()['saved'] == saved
    assert client.post('/api/hoops', json=dict(name='Frame', width_mm=2, height_mm=180)).status_code == 400
    assert client.delete('/api/hoops/'+saved[0]['id']).get_json()['saved'] == []
    assert client.delete('/api/hoops/'+saved[0]['id']).status_code == 404


def setup(tmp_path, **extra):
    from embroiderly.web import create_app
    (tmp_path/'work/uploads').mkdir(parents=True)
    Image.fromarray(picture()).save(tmp_path/'work/uploads/p.png')
    client = create_app(tmp_path).test_client()
    options = {'height_mm': 80, 'floor_mm2': 1, 'smooth': 0, 'mask_holes_mm2': 0, 'count': 2, **extra}
    return client, options


def test_the_chosen_hoop_sets_the_piece_check(tmp_path):
    # The design is about 70 mm square: a 100 x 100 hoop and a turned 13 x 18 cm hoop hold it,
    # a 50 mm wide hoop of my own does not.
    client, options = setup(tmp_path)
    for field, outside in (([100, 100], False), ([180, 130], False), ([50, 120], True)):
        body = client.post('/artwork/p.png', json=dict(options={**options, 'hoop_id': 'common-130x180', 'piece_hoop_mm': field})).get_json()
        pieces = body['report']['piece_layout']
        assert pieces['hoop_mm'] == field
        assert any(p['audit']['outside_hoop'] for p in pieces['pieces']) is outside


def test_a_bad_hoop_id_is_refused(tmp_path):
    client, options = setup(tmp_path)
    body = client.post('/artwork/p.png', json=dict(options={**options, 'hoop_id': '<script>'})).get_json()
    assert 'listed hoop' in (body.get('error') or '')


def test_the_lock_guard_allows_a_new_hoop():
    from embroiderly.piece_layout import guard
    previous = {'piece_edits': {'a'*20: {'locked': True}}, 'piece_hoop_mm': [100, 100]}
    guard(previous, {**previous, 'hoop_id': 'janome-140x140', 'piece_hoop_mm': [140, 140]})


def test_stitches_with_a_turned_hoop_pass_the_release_gate_and_the_worksheet_names_it(tmp_path):
    from embroiderly.release_gate import checked_bytes
    client, options = setup(tmp_path, hoop_id='brother-130x180', piece_hoop_mm=[180, 130])
    body = client.post('/artwork/p.png', json=dict(options=options, subject_confirmed=True, digitize=True)).get_json()
    assert body.get('playback'), body.get('error')
    assert checked_bytes(tmp_path/'work'/'inkstitch-preview'/Path(body['prepared_name']).stem, 'dst')
    sheet = client.get('/worksheet/'+body['prepared_name']).get_data(as_text=True)
    assert 'Brother 5 × 7 in (180 × 130 mm)' in sheet and 'too small' not in sheet


def test_the_worksheet_warns_when_the_chosen_hoop_is_too_small():
    from embroiderly.worksheet import page
    steps = [dict(x=0, y=0, t='stitch', color='#000000'), dict(x=150, y=90, t='stitch', color='#000000')]
    sheet = page(dict(steps=steps, colors=['#000000']), 'Test', hoop=dict(name='Janome SQ14', field=[140, 140]))
    assert 'Janome SQ14 (140 × 140 mm) is too small; use 130 × 180 mm or larger' in sheet
