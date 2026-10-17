"""The workspace uses the native recipe/files, not image preparation."""
import json
from pathlib import Path

import pyembroidery as emb
import pytest
from jinja2 import FileSystemLoader
from test_lettering_native import client, BODY
from embroiderly.lettering_workspace import workspace_data, register
from embroiderly.machine_files import read_pattern


def test_workspace_reads_exact_dst_without_rasterizing_or_rewriting(client, monkeypatch):
    c, store, calls = client
    data = c.post('/lettering/native/check', json=BODY).json
    folder = store/data['id']
    before = {p.name:p.read_bytes() for p in folder.iterdir() if p.is_file()}
    from embroiderly import preparation, engine
    def forbidden(*a, **kw):
        raise AssertionError('Native letters must never pass through picture processing')
    monkeypatch.setattr(preparation, 'prepare', forbidden)
    monkeypatch.setattr(engine, 'digitize', forbidden)
    view = workspace_data(folder, data['id'])
    written = read_pattern(folder/'design.dst')
    assert view['result']['recipe'] == data['recipe']
    assert view['image'].startswith('data:image/svg+xml;base64,')
    assert [(s['x'],s['y']) for s in view['playback']['steps']] == [(x/10,y/10) for x,y,_ in written.stitches]
    assert view['playback']['trim_count'] == written.count_stitch_commands(emb.TRIM)
    assert before == {p.name:p.read_bytes() for p in folder.iterdir() if p.is_file()}
    assert not list(store.rglob('*.png'))


def test_workspace_routes_and_invalid_ids(client):
    c, store, calls = client
    register(c.application, store.parent.parent)
    c.application.jinja_loader = FileSystemLoader(str(Path('src/embroiderly/templates').resolve()))
    data = c.post('/lettering/native/check', json=BODY).json
    page = c.get('/text/'+data['id'])
    assert page.status_code == 200
    assert b'window.nativeTextConfig=' in page.data
    assert b'"text": "A"' in page.data
    assert c.get('/text/not-a-recipe').status_code == 404
    assert c.get('/lettering/native/no/workspace-data').status_code == 422
    view = c.get('/lettering/native/'+data['id']+'/workspace-data')
    assert view.status_code == 200 and view.json['result']['id'] == data['id']


def test_corrupted_machine_pair_cannot_be_shown_as_checked(client):
    c, store, calls = client
    data = c.post('/lettering/native/check', json=BODY).json
    folder = store/data['id']
    (folder/'design.pes').write_bytes(b'broken')
    with pytest.raises(ValueError, match='changed since generation'):
        workspace_data(folder, data['id'])


def test_resize_uses_new_font_recipe_and_keeps_original_version(client):
    c, store, calls = client
    first = c.post('/lettering/native/check', json=BODY).json
    original = (store/first['id']/'design.dst').read_bytes()
    second = c.post('/lettering/native/check', json={**BODY,'height_mm':4}).json
    assert second['id'] != first['id']
    assert [b['height_mm'] for b in calls] == [5,4]
    assert second['approved'] is False
    assert (store/first['id']/'design.dst').read_bytes() == original
    assert json.loads((store/first['id']/'result.json').read_text())['recipe']['height_mm'] == 5
