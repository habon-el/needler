import json
from pathlib import Path
import pytest
from PIL import Image
from embroiderly.web import create_app
from embroiderly.library import LibraryConflict


@pytest.fixture
def library(tmp_path):
    app=create_app(tmp_path)
    uploads=tmp_path/'work'/'uploads'
    Image.new('RGB',(60,40),'red').save(uploads/'flower.png')
    Image.new('RGB',(60,40),'blue').save(uploads/'prepared_cache.png')
    decision=tmp_path/'work'/'decisions'/'flower.png.preparation.json'
    decision.write_text(json.dumps({'height_mm':80,'edits':[]}))
    lib=app.extensions['design_library'];lib.adopt()
    return lib,app.test_client()


def item(row): return {'id':row['id'],'revision':row['revision']}


def test_adoption_excludes_caches_and_does_not_mutate_original(library):
    lib,client=library
    assert [row['id'] for row in lib.list()]==['flower.png']
    assert lib.get('flower.png')['owner_id'] is None
    assert lib.facts('flower.png')=={'width_mm':120,'height_mm':80,'thread_count':None,'stitch_count':None,'status':'Not generated'}
    assert client.get('/').status_code==200
    assert client.get('/api/library/flower.png/preview').mimetype=='image/png'


def test_remove_recent_independent_of_trash_restore(library):
    lib,client=library
    source=lib.uploads/'flower.png';before=source.read_bytes()
    row=lib.change('remove_recent',[item(lib.get('flower.png'))])[0]
    assert not lib.list()
    assert len(lib.list('all'))==1
    row=lib.change('delete',[item(row)])[0]
    assert len(lib.list('trash'))==1
    assert not lib.list('all')
    assert client.get('/artwork/flower.png').status_code==410
    assert client.post('/artwork/flower.png',json={}).status_code==410
    row=lib.change('restore',[item(row)])[0]
    assert row['removed_recent']==1
    assert not lib.list('recent')
    assert len(lib.list('all'))==1
    row=lib.change('opened',[item(row)])[0]
    assert row['removed_recent']==0 and row['opened_at']
    assert source.read_bytes()==before


def test_duplicate_copies_design_options_without_changing_original(library):
    lib,_=library
    row=lib.get('flower.png');copy=lib.duplicate(row['id'],row['revision'])
    assert copy['id']!=row['id'] and copy['name']=='flower (copy)'
    assert (lib.uploads/copy['source']).read_bytes()==(lib.uploads/row['source']).read_bytes()
    assert (lib.decisions/(copy['source']+'.preparation.json')).read_bytes()==(lib.decisions/'flower.png.preparation.json').read_bytes()
    lib.change('rename',[item(copy)],'<script>not executable</script>')
    assert lib.get(row['id'])['name']=='flower'


def test_bulk_is_atomic_if_one_revision_is_stale(library):
    lib,_=library
    row=lib.get('flower.png');copy=lib.duplicate(row['id'],row['revision'])
    lib.change('rename',[item(copy)],'Changed elsewhere')
    with pytest.raises(LibraryConflict):lib.change('delete',[item(row),item(copy)])
    assert lib.get(row['id'])['deleted_at'] is None
    assert len(lib.list('all'))==2


def test_api_validation_and_mutation_origin(library):
    lib,client=library
    payload={'action':'delete','items':[item(lib.get('flower.png'))]}
    assert client.post('/api/library/action',json=payload,headers={'Origin':'https://outside.example'}).status_code==403
    for bad in [[],{}, {'action':'delete','items':[]}, {'action':'delete','items':[{'id':'../flower.png','revision':0}]}, {'action':'rename','items':payload['items'],'name':''}]:
        assert client.post('/api/library/action',json=bad).status_code in {400,404}
    result=client.post('/api/library/action',json=payload)
    assert result.status_code==200
    assert client.post('/api/library/action',json=payload).status_code==409
    assert client.get('/api/library?view=bogus').status_code==400


def test_failed_preview_is_an_error_not_placeholder_artwork(library):
    lib,client=library
    (lib.uploads/'flower.png').write_bytes(b'not an image')
    assert client.get('/api/library/flower.png/preview').status_code==422
    assert client.get('/api/library/flower.png/facts').status_code==422


def test_save_as_template_and_start_a_design_from_it(library):
    lib,client=library
    row=lib.get('flower.png')
    saved=client.post('/api/library/action',json={'action':'save_template','items':[item(row)]})
    assert saved.status_code==200
    template=saved.get_json()['designs'][0]
    assert template['template']==1 and template['name']=='flower' and template['id']!='flower.png'
    assert [r['id'] for r in lib.list('templates')]==[template['id']]
    assert template['id'] not in {r['id'] for r in lib.list('all')+lib.list('recent')}
    assert (lib.decisions/(template['source']+'.preparation.json')).read_bytes()==(lib.decisions/'flower.png.preparation.json').read_bytes()
    # A template cannot be saved as a template again; a design is not a template to start from.
    assert client.post('/api/library/action',json={'action':'save_template','items':[item(template)]}).status_code==400
    assert client.post('/api/library/action',json={'action':'use_template','items':[item(row)]}).status_code==400
    used=client.post('/api/library/action',json={'action':'use_template','items':[item(template)]}).get_json()['designs'][0]
    assert used['template']==0 and used['name']=='flower' and used['id'] not in {'flower.png',template['id']}
    assert {r['id'] for r in lib.list('all')}=={'flower.png',used['id']}
    # Editing the new design never changes the template it came from.
    (lib.decisions/(used['source']+'.preparation.json')).write_text(json.dumps({'height_mm':40,'edits':[]}))
    assert json.loads((lib.decisions/(template['source']+'.preparation.json')).read_text())['height_mm']==80
    lib.change('delete',[item(lib.get(template['id']))])
    assert not lib.list('templates') and template['id'] in {r['id'] for r in lib.list('trash')}
    assert client.get('/api/library?view=templates').status_code==200
