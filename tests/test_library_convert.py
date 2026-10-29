"""Batch convert in the Library: several designs' checked stitches in one machine format, as a zip."""
import io
import sys
import zipfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from test_piece_editing import route_setup  # noqa: E402


def made(tmp_path):
    client, options, _ = route_setup(tmp_path)
    body = client.post('/artwork/p.png', json=dict(options=options, subject_confirmed=True, digitize=True, save=True)).get_json()
    assert body.get('playback'), body.get('error')
    # A second design with no stitches yet.
    Image.new('RGB', (60, 40), 'blue').save(tmp_path/'work'/'uploads'/'plain.png')
    library = client.application.extensions['design_library']
    library.adopt()
    return client, library


def test_selected_designs_download_as_one_zip_in_the_chosen_format(tmp_path):
    client, library = made(tmp_path)
    library.change('rename', [dict(id='p.png', revision=library.get('p.png')['revision'])], 'Red rose')
    response = client.post('/api/library/convert', json=dict(ids=['p.png', 'plain.png'], format='jef'))
    assert response.status_code == 200, response.get_json()
    assert response.headers['X-Converted'] == '1' and response.headers['X-Skipped'] == '1'
    archive = zipfile.ZipFile(io.BytesIO(response.data))
    assert sorted(archive.namelist()) == ['Red-rose.jef', 'not-included.txt']
    assert 'plain' in archive.read('not-included.txt').decode() and 'make the stitches' in archive.read('not-included.txt').decode()
    # The file is the one the single download gives (checked through the same gate).
    single = client.get('/studio-export/'+library_folder(tmp_path).name+'/dst').data
    dst = zipfile.ZipFile(io.BytesIO(client.post('/api/library/convert', json=dict(ids=['p.png'], format='dst')).data))
    assert dst.namelist() == ['Red-rose.dst'] and dst.read('Red-rose.dst') == single


def library_folder(tmp_path):
    import json
    from embroiderly.saved_plans import matching_folder
    options = json.loads((tmp_path/'work'/'decisions'/'p.png.preparation.json').read_text())
    return matching_folder(tmp_path, tmp_path/'work'/'uploads'/'p.png', options)


def test_nothing_to_convert_and_bad_requests_are_refused(tmp_path):
    client, library = made(tmp_path)
    nothing = client.post('/api/library/convert', json=dict(ids=['plain.png'], format='dst'))
    assert nothing.status_code == 422 and 'plain' in nothing.get_json()['error']
    assert client.post('/api/library/convert', json=dict(ids=['p.png'], format='vp3')).status_code == 400
    assert client.post('/api/library/convert', json=dict(ids=[], format='dst')).status_code == 400
    assert client.post('/api/library/convert', json=dict(ids=['p.png', 'p.png'], format='dst')).status_code == 400
    assert client.post('/api/library/convert', json=dict(ids=['missing.png'], format='dst')).status_code == 404
    library.change('delete', [dict(id='p.png', revision=library.get('p.png')['revision'])])
    assert client.post('/api/library/convert', json=dict(ids=['p.png'], format='dst')).status_code == 409


def test_the_library_page_offers_every_machine_format(tmp_path):
    from embroiderly.release_gate import FORMATS
    from embroiderly.web import create_app
    html = create_app(tmp_path).test_client().get('/designs').get_data(as_text=True)
    assert 'id="convertZip"' in html and all(f'<option value="{key}">' in html for key in FORMATS)
