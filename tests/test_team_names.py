import io
from pathlib import Path
from tempfile import TemporaryDirectory
import zipfile

import numpy as np
import pyembroidery as emb
import pytest
from flask import Flask

from embroiderly import lettering_native as native
from embroiderly import team_names
from embroiderly.release_gate import FORMAT_SETTINGS, check_pattern, checked_bytes, converted_bytes, read_context


def glyphs(text):
    groups = ''.join(f'<g i:letter-group="glyph" k:label="{c}"><path i:satin_column="true" d="M0 0L0 10M3 0L3 10"/></g>'
                     for c in text if c not in ' \n')
    return ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:i="http://inkstitch.org/namespace" '
            f'xmlns:k="http://www.inkscape.org/namespaces/inkscape">{groups}</svg>')


@pytest.fixture
def client(tmp_path, monkeypatch):
    calls = []

    def generate(body, **kwargs):
        # A zigzag 4 mm wide per letter, 2 mm tall: long names are wide.
        calls.append(body['text'])
        letters = sum(c not in ' \n' for c in body['text'])
        left = -20*letters
        stitches = [[left, -10, 'JUMP']]
        for step in range(0, 40*letters+1, 5):
            stitches.append([left+step, -10 if step % 10 == 0 else 10, 'STITCH'])
        stitches.append([stitches[-1][0], stitches[-1][1], 'END'])
        thread = dict(color='#000000', description='Black', catalog_number=None, details=None, brand=None, chart=None, weight=None)
        return dict(svg=glyphs(body['text']), plan={'extras': {}, 'threadlist': [thread], 'stitches': stitches},
                    nominal_height_mm=5, rebuild_report=dict(mask=np.ones((1500, 1500), dtype=bool),
                                                             origin=[30, 30], columns=letters, added_cuts=0))
    monkeypatch.setattr(native.small_lettering, 'generate', generate)
    # The stand-in letters are not traced from a font, so there are no font strokes to compare.
    from embroiderly import lettering_coverage
    monkeypatch.setattr(lettering_coverage, 'missing_columns', lambda svg, pattern: [])
    app = Flask(__name__)
    native.register(app, tmp_path)
    team_names.register(app, tmp_path)
    return app.test_client(), tmp_path/'work/lettering-native', calls


SETUP = dict(font='small_font', height_mm=5, available_width_mm=30, align='center', colour='#123456')


def passes_gate(folder, fmt, data):
    """The zipped file is the release gate's own: the checked bytes for PES and DST,
    and for other formats a file whose readback passes the same checks."""
    if fmt in ('dst', 'pes'):
        assert data == checked_bytes(folder, fmt)
        return
    converted_bytes(folder, fmt)
    record, mask = read_context(folder)
    with TemporaryDirectory() as temporary:
        path = Path(temporary)/('design.'+fmt)
        path.write_bytes(data)
        check_pattern(emb.EmbPattern(str(path), settings=FORMAT_SETTINGS.get(fmt, (None, None))[1]),
                      mask, record['scale'], record['origin'])


def make_all(c, text):
    listed = c.post('/lettering/native/team/list', json={'names': text})
    assert listed.status_code == 200, listed.json
    rows = []
    for item in listed.json['names']:
        r = c.post('/lettering/native/team/name', json={**SETUP, 'text': item['name']})
        assert r.status_code == 200, r.json
        rows.append(r.json)
    return listed.json['names'], rows


def test_every_name_gets_a_checked_file_in_the_zip(client):
    c, store, calls = client
    listed, rows = make_all(c, 'ANN 7\n\n  BOB  \nCY\n')
    assert [n['name'] for n in listed] == ['ANN 7', 'BOB', 'CY']
    assert all(r['ready'] and r['fits'] and r['reason'] is None for r in rows)
    assert rows[0]['width_mm'] > rows[2]['width_mm'] and rows[0]['stitches'] > 0
    for fmt in ('dst', 'pes', 'jef'):
        response = c.post('/lettering/native/team/zip', json={'format': fmt, 'names': [dict(name=r['name'], id=r['id']) for r in rows]})
        assert response.status_code == 200, response.json
        archive = zipfile.ZipFile(io.BytesIO(response.data))
        assert archive.namelist() == [f'ANN-7.{fmt}', f'BOB.{fmt}', f'CY.{fmt}']
        for r, member in zip(rows, archive.namelist()):
            data = archive.read(member)
            passes_gate(store/r['id'], fmt, data)
    # Made again: every name comes from the cache, nothing is stitched twice.
    before = len(calls)
    make_all(c, 'ANN 7\nBOB\nCY')
    assert len(calls) == before


def test_shared_recipe_differs_only_in_text(client):
    c, store, _ = client
    _, rows = make_all(c, 'ANN\nBO')
    recipes = [native.load(store/r['id'], r['id'])['recipe'] for r in rows]
    assert [r.pop('text') for r in recipes] == ['ANN', 'BO']
    assert recipes[0] == recipes[1]


def test_too_wide_name_is_reported_not_resized(client):
    c, store, _ = client
    # 9 letters x 4 mm = 36 mm, more than the 30 mm max width.
    _, rows = make_all(c, 'ALEXANDRA\nBO')
    wide, short = rows
    assert not wide['fits'] and not wide['ready']
    assert '30 mm' in wide['reason'] and 'Not resized' in wide['reason']
    assert 0 < wide['fit_height_mm'] < 5
    recipe = native.load(store/wide['id'], wide['id'])['recipe']
    assert recipe['height_mm'] == 5.0 and native.load(store/wide['id'], wide['id'])['reports']['dst']['width_mm'] > 30
    assert short['ready'] and 'fit_height_mm' not in short
    # A name that is not ready is never put in the zip.
    response = c.post('/lettering/native/team/zip', json={'format': 'dst', 'names': [dict(name=r['name'], id=r['id']) for r in rows]})
    assert response.status_code == 422 and 'ALEXANDRA' in response.json['error']
    ok = c.post('/lettering/native/team/zip', json={'format': 'dst', 'names': [dict(name='BO', id=short['id'])]})
    assert ok.status_code == 200 and zipfile.ZipFile(io.BytesIO(ok.data)).namelist() == ['BO.dst']


def test_name_with_missing_letters_reports_its_reason(client):
    c, _, calls = client
    r = c.post('/lettering/native/team/name', json={**SETUP, 'text': '🦉'})
    assert r.status_code == 200 and not r.json['ready'] and r.json['id'] is None and r.json['reason']
    assert not calls


def test_safe_file_names():
    assert team_names.file_name('José Müller #10') == 'Jose-Muller-10'
    assert team_names.file_name('../../etc/passwd') == 'etc-passwd'
    assert team_names.file_name('a:b*c?"<>|') == 'a-b-c'
    assert team_names.file_name('CON') == 'CON_' and team_names.file_name('lpt1') == 'lpt1_'
    assert team_names.file_name('★★') == 'name'
    assert team_names.file_names(['Sam', 'sam', 'SAM!', '★', '☆']) == ['Sam', 'sam-2', 'SAM-3', 'name', 'name-2']
    for name in team_names.file_names(['a/b\\c', '..', ' .x. ', 'Zoë 9']):
        assert all(ch.isascii() and (ch.isalnum() or ch in '-_') for ch in name) and name


def test_unsafe_names_get_safe_files_in_the_zip(client):
    c, _, _ = client
    _, rows = make_all(c, 'A/B\nA:B')
    response = c.post('/lettering/native/team/zip', json={'format': 'dst', 'names': [dict(name=r['name'], id=r['id']) for r in rows]})
    assert response.status_code == 200, response.json
    assert zipfile.ZipFile(io.BytesIO(response.data)).namelist() == ['A-B.dst', 'A-B-2.dst']


def test_limits_are_enforced(client):
    c, _, calls = client
    many = '\n'.join(f'N{i}' for i in range(team_names.MAX_NAMES+1))
    assert c.post('/lettering/native/team/list', json={'names': many}).status_code == 400
    assert c.post('/lettering/native/team/list', json={'names': 'N'*(team_names.MAX_CHARS+1)}).status_code == 400
    assert c.post('/lettering/native/team/list', json={'names': ' \n \n'}).status_code == 400
    assert c.post('/lettering/native/team/list', json={'names': 7}).status_code == 400
    ok = c.post('/lettering/native/team/list', json={'names': '\n'.join(f'N{i}' for i in range(team_names.MAX_NAMES))})
    assert ok.status_code == 200 and len(ok.json['names']) == team_names.MAX_NAMES
    # One name per request, each within the length limit.
    assert c.post('/lettering/native/team/name', json={**SETUP, 'text': 'A\nB'}).status_code == 400
    assert c.post('/lettering/native/team/name', json={**SETUP, 'text': 'A'*(team_names.MAX_CHARS+1)}).status_code == 400
    assert not calls
    entries = [dict(name=f'N{i}', id='0'*64) for i in range(team_names.MAX_NAMES+1)]
    assert c.post('/lettering/native/team/zip', json={'format': 'dst', 'names': entries}).status_code == 422
    assert c.post('/lettering/native/team/zip', json={'format': 'exe', 'names': entries[:1]}).status_code == 422


def test_zip_refuses_tampered_or_mixed_names(client):
    c, store, _ = client
    _, rows = make_all(c, 'ANN\nBO')
    swapped = [dict(name='ANN', id=rows[1]['id']), dict(name='BO', id=rows[0]['id'])]
    assert c.post('/lettering/native/team/zip', json={'format': 'dst', 'names': swapped}).status_code == 422
    other = c.post('/lettering/native/team/name', json={**SETUP, 'colour': '#654321', 'text': 'CY'}).json
    mixed = [dict(name='ANN', id=rows[0]['id']), dict(name='CY', id=other['id'])]
    response = c.post('/lettering/native/team/zip', json={'format': 'dst', 'names': mixed})
    assert response.status_code == 422 and 'different settings' in response.json['error']
    assert c.post('/lettering/native/team/zip', json={'format': 'dst', 'names': [dict(name='ANN', id='../x')]}).status_code == 422
    # A file changed on disk after it was made fails the release gate.
    (store/rows[0]['id']/'design.pes').write_bytes(b'corrupt')
    response = c.post('/lettering/native/team/zip', json={'format': 'dst', 'names': [dict(name='ANN', id=rows[0]['id'])]})
    assert response.status_code == 422 and response.json['error'].startswith('ANN: Export blocked')


def test_busy_lock_is_shared_and_released(client):
    c, _, _ = client
    native.BUSY.acquire()
    try:
        assert c.post('/lettering/native/team/name', json={**SETUP, 'text': 'ANN'}).status_code == 409
    finally:
        native.BUSY.release()
    assert c.post('/lettering/native/team/name', json={**SETUP, 'text': 'ANN'}).status_code == 200
    assert not native.BUSY.locked()



def test_name_failing_a_check_says_why(client, monkeypatch):
    c, _, _ = client
    generator = native.small_lettering.generate
    def broken(body, **kwargs):
        result = generator(body, **kwargs)
        if body['text'] == 'BO':
            result['plan']['stitches'][2] = [result['plan']['stitches'][1][0]+1, -10, 'STITCH']
        return result
    monkeypatch.setattr(native.small_lettering, 'generate', broken)
    _, rows = make_all(c, 'ANN\nBO')
    assert rows[0]['ready'] and not rows[1]['ready'] and rows[1]['fits']
    assert rows[1]['reason'].startswith('Did not pass the file checks') and 'fit_height_mm' not in rows[1]


def test_real_font_names_zip(tmp_path):
    # The real embroidery font, end to end: two short names, one zip, every file through the gate.
    app = Flask(__name__)
    native.register(app, tmp_path)
    team_names.register(app, tmp_path)
    c = app.test_client()
    rows = [c.post('/lettering/native/team/name', json={**SETUP, 'height_mm': 8, 'available_width_mm': 100, 'text': name}).json
            for name in ('ANNA 7', 'BOB')]
    assert all(r['ready'] for r in rows), rows
    assert rows[0]['height_mm'] == pytest.approx(rows[1]['height_mm'], abs=.6)
    response = c.post('/lettering/native/team/zip', json={'format': 'pes', 'names': [dict(name=r['name'], id=r['id']) for r in rows]})
    assert response.status_code == 200, response.json
    archive = zipfile.ZipFile(io.BytesIO(response.data))
    assert archive.namelist() == ['ANNA-7.pes', 'BOB.pes']
    for r, member in zip(rows, archive.namelist()):
        passes_gate(tmp_path/'work/lettering-native'/r['id'], 'pes', archive.read(member))
