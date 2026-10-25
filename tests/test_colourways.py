"""Named colourways: save, rename, switch and delete colour versions of a design; the machine
files follow the active colourway."""
import sys
from pathlib import Path

import pyembroidery as emb
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from test_sew_order import picture  # noqa: E402
from embroiderly import colourways  # noqa: E402

BLUE, RED = '#78a0e6', '#c81e3c'
SUMMER = dict(merges={BLUE: '#1e8c3c', RED: '#f0c800'})


def test_colourways_are_saved_renamed_and_deleted(tmp_path):
    saved = colourways.save(tmp_path, 'p.png', dict(name=' Summer ', threads=dict(merges={BLUE.upper(): '#1E8C3C'})))
    summer = saved[0]
    assert summer['name'] == 'Summer' and summer['id'].startswith('cw-') and summer['threads'] == dict(merges={BLUE: '#1e8c3c'})
    assert (tmp_path/'work/decisions/p.png.colourways.json').is_file()
    colourways.save(tmp_path, 'p.png', dict(name='Winter', threads=dict(merges={}, border_colour='#202020')))
    with pytest.raises(ValueError, match='already exists'):
        colourways.rename(tmp_path, 'p.png', summer['id'], 'winter')
    assert colourways.rename(tmp_path, 'p.png', summer['id'], 'Beach')[0]['name'] == 'Beach'
    assert [c['name'] for c in colourways.delete(tmp_path, 'p.png', summer['id'])] == ['Winter']
    with pytest.raises(ValueError, match='no longer saved'):
        colourways.delete(tmp_path, 'p.png', summer['id'])
    assert colourways.saved(tmp_path, 'other.png') == []


@pytest.mark.parametrize('body', [None, dict(name='', threads=dict(merges={})), dict(name='x'*41, threads=dict(merges={})),
                                  dict(name='A', threads=None), dict(name='A', threads=dict(merges={BLUE: 'green'})),
                                  dict(name='A', threads=dict(merges={}, border_colour='#12')),
                                  dict(name='A', threads=dict(merges={}, fabric_preset='denim'))])
def test_bad_colourways_are_refused(tmp_path, body):
    with pytest.raises(ValueError):
        colourways.save(tmp_path, 'p.png', body)


def test_at_most_twenty_colourways(tmp_path):
    for n in range(colourways.MAX_SAVED):
        colourways.save(tmp_path, 'p.png', dict(name=f'C{n}', threads=dict(merges={})))
    with pytest.raises(ValueError, match='up to 20'):
        colourways.save(tmp_path, 'p.png', dict(name='one more', threads=dict(merges={})))


def setup(tmp_path):
    from embroiderly.web import create_app
    (tmp_path/'work/uploads').mkdir(parents=True)
    Image.fromarray(picture()).save(tmp_path/'work/uploads/p.png')
    client = create_app(tmp_path).test_client()
    options = {'height_mm': 80, 'floor_mm2': 1, 'smooth': 0, 'mask_holes_mm2': 0, 'count': 2}
    return client, options


def test_colourway_routes(tmp_path):
    client, _ = setup(tmp_path)
    assert client.get('/api/colourways/p.png').get_json()['saved'] == []
    assert client.get('/api/colourways/missing.png').status_code == 404
    saved = client.post('/api/colourways/p.png', json=dict(name='Summer', threads=SUMMER)).get_json()['saved']
    assert client.post('/api/colourways/p.png', json=dict(name='Summer', threads=SUMMER)).status_code == 400
    ident = saved[0]['id']
    assert client.patch(f'/api/colourways/p.png/{ident}', json=dict(name='Beach')).get_json()['saved'][0]['name'] == 'Beach'
    assert client.patch(f'/api/colourways/p.png/{ident}', json={}).status_code == 400
    assert client.delete(f'/api/colourways/p.png/{ident}').get_json()['saved'] == []
    assert client.delete(f'/api/colourways/p.png/{ident}').status_code == 404


def test_the_studio_page_loads_the_colourway_control(tmp_path):
    client, _ = setup(tmp_path)
    assert 'colourway-controls.js' in client.get('/artwork/p.png').get_data(as_text=True)


def threads(directory):
    return sorted(t.hex_color() for t in emb.EmbPattern(str(directory/'design.pes')).threadlist)


def test_switching_colourways_changes_the_checked_machine_files(tmp_path):
    from embroiderly.release_gate import checked_bytes
    client, options = setup(tmp_path)
    preview = tmp_path/'work'/'inkstitch-preview'
    original = client.post('/artwork/p.png', json=dict(options=options, subject_confirmed=True, digitize=True)).get_json()
    assert original.get('playback'), original.get('error')
    assert threads(preview/Path(original['prepared_name']).stem) == sorted([BLUE, RED])
    # Switching to the saved colourway puts its thread choices into the options.
    saved = client.post('/api/colourways/p.png', json=dict(name='Summer', threads=SUMMER)).get_json()['saved']
    summer = client.post('/artwork/p.png', json=dict(options={**options, **saved[0]['threads']}, subject_confirmed=True, digitize=True)).get_json()
    assert summer.get('playback'), summer.get('error')
    folder = preview/Path(summer['prepared_name']).stem
    assert checked_bytes(folder, 'dst') and checked_bytes(folder, 'pes')
    assert threads(folder) == sorted(SUMMER['merges'].values())
    assert sorted(summer['playback']['colors']) == sorted(SUMMER['merges'].values())
    # Same parts, same order: only the thread colours differ.
    assert summer['playback']['stitch_count'] == original['playback']['stitch_count']
    # Switching back finds the first plan again without generating.
    back = client.post('/artwork/p.png', json=dict(options=options, subject_confirmed=True)).get_json()
    assert sorted(back['playback']['colors']) == sorted([BLUE, RED])
