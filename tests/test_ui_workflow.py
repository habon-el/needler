"""Presentation routes must not generate or approve embroidery."""
from pathlib import Path
from jinja2 import FileSystemLoader
from test_lettering_native import client, BODY
from embroiderly.lettering_workspace import register


def workspace(c, store):
    register(c.application, store.parent.parent)
    c.application.jinja_loader = FileSystemLoader(str(Path('src/embroiderly/templates').resolve()))


def test_new_text_is_an_empty_editor_not_a_generated_design(client):
    c, store, calls = client
    workspace(c, store)
    response = c.get('/text/new')
    assert response.status_code == 200
    assert b'"id": null' in response.data and b'"text": ""' in response.data
    assert b'/static/workflow.js' in response.data
    assert calls == []
    assert not store.exists() or not list(store.iterdir())


def test_ui_get_keeps_existing_recipe_and_approval_unchanged(client):
    c, store, calls = client
    workspace(c, store)
    result = c.post('/lettering/native/check', json=BODY).json
    before = c.get('/lettering/native/'+result['id']).json
    response = c.get('/text/'+result['id'])
    assert response.status_code == 200
    assert c.get('/lettering/native/'+result['id']).json == before
    assert len(calls) == 1 and not before['approved']


def test_start_choices_use_existing_editors():
    for name in ('landing', 'library'):
        template = Path('src/embroiderly/templates/'+name+'.html').read_text()
        assert 'href="/text/new"' in template
        assert '>Type text' in template and '>Upload image' in template


def test_workflow_delegates_to_existing_download_and_check_owners():
    source = Path('src/embroiderly/static/workflow.js').read_text()
    assert 'originalStitch.call' in source
    assert 'exportDst' in source and 'native' in source
    # UI reads the existing checked image download URL to show errors in-page.
    # It cannot generate, approve, or choose a replacement export endpoint.
    assert source.count('fetch(') == 1
    assert 'fetch(target.href,{signal:AbortSignal.timeout(60000)})' in source
    assert 'method:' not in source
    assert "if(native){$('native'" in source
    assert 'version!==downloadVersion' in source
    assert 'localStorage' not in source
    assert 'localStorage' not in source  # No duplicate persistent settings owner.
