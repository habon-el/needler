from embroiderly.preparation_identity import preparation_key
import json

from PIL import Image
from embroiderly.web import create_app
from embroiderly.saved_plans import matching_plan, read_plan, DEFAULTS


def setup_plan(tmp_path, options=None):
    app=create_app(tmp_path)
    source=tmp_path/'work/uploads/restore.png'
    Image.new('RGB',(30,30),'red').save(source)
    options=options or dict(DEFAULTS,interactions=5)
    key=preparation_key(source.read_bytes(),options)
    name='prepared_'+key
    (source.parent/(name+'.prep.json')).write_text(json.dumps({'source':source.name,'options':options}))
    (tmp_path/'work/decisions/restore.png.preparation.json').write_text(json.dumps(options))
    directory=tmp_path/'work/inkstitch-preview'/name;directory.mkdir(parents=True)
    payload={'colors':['#ff0000'],'steps':[{'x':0,'y':0,'t':'jump','color':'#ff0000'},{'x':1,'y':1,'t':'stitch','color':'#ff0000'}],'origin_mm':[15,15]}
    plan=directory/'playback.json';plan.write_text(json.dumps(payload))
    return app.test_client(),source,options,plan


def test_restores_after_ui_counter_changes_and_undo(tmp_path):
    client,source,options,_=setup_plan(tmp_path)
    restored=client.post('/artwork/restore.png',json={'options':dict(options,interactions=8)})
    assert restored.status_code==200
    assert restored.json['playback']['stitch_count']==1
    assert restored.json['playback']['trim_count']==0
    changed=client.post('/artwork/restore.png',json={'options':dict(options,height_mm=120,interactions=9)})
    assert changed.status_code==200 and 'playback' not in changed.json
    undone=client.post('/artwork/restore.png',json={'options':dict(options,interactions=10)})
    assert 'playback' in undone.json


def test_omitted_defaults_can_restore_matching_plan(tmp_path):
    _,source,_,_=setup_plan(tmp_path)
    assert matching_plan(tmp_path,source,{}).get('playback')


def test_changed_source_does_not_restore_previous_geometry(tmp_path):
    _,source,options,_=setup_plan(tmp_path)
    Image.new('RGB',(30,30),'blue').save(source)
    assert matching_plan(tmp_path,source,options)=={}


def test_changed_selection_does_not_restore_plan(tmp_path):
    _,source,options,_=setup_plan(tmp_path)
    assert matching_plan(tmp_path,source,dict(options,selection='lasso',outline=[[1,1],[10,1],[5,9]]))=={}


def test_corrupt_saved_plan_does_not_break_page(tmp_path):
    client,_,options,plan=setup_plan(tmp_path)
    plan.write_text('{truncated')
    assert client.get('/artwork/restore.png').status_code==200
    response=client.post('/artwork/restore.png',json={'options':options})
    assert response.status_code==200 and 'playback' not in response.json
    assert b'id="stitchEmptyGenerate"' in client.get('/artwork/restore.png').data


def test_empty_or_invalid_plans_are_not_playable(tmp_path):
    _,_,_,plan=setup_plan(tmp_path)
    good=json.loads(plan.read_text())
    for payload in ({}, {'steps':[], 'colors':['#ff0000']}, {**good,'origin_mm':[None,0]}, {**good,'colors':['bad']}):
        plan.write_text(json.dumps(payload))
        assert read_plan(plan) is None

def test_exact_plan_does_not_scan_previous_preparations(tmp_path,monkeypatch):
    from pathlib import Path
    _,source,options,_=setup_plan(tmp_path)
    def unexpected_scan(*args,**kwargs):
        raise AssertionError('Exact cache hit must not scan unrelated plans')
    monkeypatch.setattr(Path,'glob',unexpected_scan)
    assert matching_plan(tmp_path,source,options)['playback']['stitch_count']==1
