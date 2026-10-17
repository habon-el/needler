import json
import pytest
from embroiderly.web import create_app
from test_piece_layout import make_image,sample


def setup(tmp_path):
    app=create_app(tmp_path);client=app.test_client()
    make_image(tmp_path/'work/uploads/p.png');_,options=sample()
    response=client.post('/artwork/p.png',json={'options':options}).get_json()
    key=response['report']['piece_layout']['pieces'][0]['id']
    return client,options,key,response


def test_saved_lock_cannot_be_omitted_or_bypassed_by_assistant(tmp_path):
    client,o,key,r=setup(tmp_path)
    response=client.post('/artwork/p.png',json=dict(options=o,piece_revision=r['piece_revision'],piece_command=dict(ids=[key],field='locked',value=True)))
    assert response.status_code==200,response.get_json()
    saved=response.get_json();locked=saved['options']
    for options in (o,{**locked,'height_mm':40},{**locked,'piece_edits':{}}):
        response=client.post('/artwork/p.png',json=dict(options=options,save=True))
        assert response.status_code==409 and 'locked' in response.get_json()['error']
    response=client.post('/assist/p.png',json=dict(options=locked,action='edit',text='make it larger'))
    assert response.status_code==400 and 'locked' in response.get_json()['error']
    response=client.post('/portrait/p.png',json=dict(options=locked))
    assert response.status_code==409
    response=client.post('/artwork/p.png',json=dict(options=locked,piece_revision=saved['piece_revision'],piece_command=dict(ids=[key],field='locked',value=False)))
    assert response.status_code==200,response.get_json()


def test_generation_failure_keeps_saved_geometry_and_stale_tab_refused(tmp_path,monkeypatch):
    client,o,key,r=setup(tmp_path)
    saved=client.post('/artwork/p.png',json=dict(options=o,save=True)).get_json()
    path=tmp_path/'work/decisions/p.png.preparation.json';before=path.read_bytes()
    command=dict(ids=[key],field='width_mm',value=20)
    stale=client.post('/artwork/p.png',json=dict(options=o,piece_command=command,subject_confirmed=True,piece_revision='old'))
    assert stale.status_code==409 and path.read_bytes()==before
    def fail(*args,**kwargs):raise ValueError('Synthetic generation failure')
    monkeypatch.setattr('embroiderly.engine.digitize',fail)
    response=client.post('/artwork/p.png',json=dict(options=o,piece_command=command,subject_confirmed=True,piece_revision=saved['piece_revision']))
    assert response.status_code==400 and path.read_bytes()==before


def test_tiny_and_hidden_pieces_save_without_export_or_silent_removal(tmp_path,monkeypatch):
    client,o,key,r=setup(tmp_path)
    def fail(*args,**kwargs):pytest.fail('Unsafe tiny/empty layout must not generate')
    monkeypatch.setattr('embroiderly.engine.digitize',fail)
    for field,value in [('width_mm',.5),('visible',False)]:
        response=client.post('/artwork/p.png',json=dict(options=o,piece_revision=r['piece_revision'],subject_confirmed=True,piece_command=dict(ids=[key],field=field,value=value)))
        assert response.status_code==200,response.get_json()
        r=response.get_json();o=r['options']
        assert r['piece_blocked'] and not r.get('playback')
        assert len(r['report']['piece_layout']['pieces'])==1
