import ast
import copy
import io
import json
from pathlib import Path
import pytest
from PIL import Image

from embroiderly import advisors
from embroiderly.knowledge_store import load_knowledge
from embroiderly.web import create_app


def test_advisor_has_no_io_or_editor_imports():
    tree=ast.parse(Path(advisors.__file__).read_text())
    imports=[alias.name for n in ast.walk(tree) if isinstance(n,ast.Import) for alias in n.names]
    assert imports==['math']
    assert not any(isinstance(n,ast.ImportFrom) for n in ast.walk(tree))
    for n in ast.walk(tree):
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name):
            assert n.func.id not in {'open','exec','eval','__import__','compile'}


def test_versioned_seed_rows_have_sources_and_flags():
    knowledge=load_knowledge()
    for book in knowledge.values():
        assert book['version']>=1 and book['seed_data'] is True
        for row in book['rows']:
            assert row['source_note'] and row['verified_by_user'] is False


@pytest.mark.parametrize('issue',[None,'lettering_closed','puckering'])
def test_observation_reasoning_good_lettering_puckering_is_not_photo_validation(issue):
    knowledge=load_knowledge();before=copy.deepcopy(knowledge)
    observation={'quality':'usable','findings':[] if issue is None else [{'issue_id':issue,'box':[.1,.1,.9,.9]}]}
    report=advisors.advise_sewout(observation,{'stitch_count':500},knowledge)
    assert report['operations']==[] and report['patch']=={}
    assert len(report['findings'])==(0 if issue is None else 1)
    if issue:
        assert report['findings'][0]['citation']['row_id']==issue
        assert report['findings'][0]['adjustment'] is None
    else: assert 'No listed visible defects' in report['message']
    assert knowledge==before


def test_poor_photo_does_not_diagnose_or_invent_measurement():
    report=advisors.advise_sewout({'quality':'poor','findings':[{'issue_id':'puckering','box':[0,0,1,1]}]}, {},load_knowledge())
    assert not report['findings'] and not report['operations']


@pytest.mark.parametrize('finding',[{'issue_id':'tension','box':[0,0,1,1]}, {'issue_id':'puckering','box':[0,0,0,1]}, {'issue_id':'puckering','box':[0,0,1,1],'patch':{'count':2}}])
def test_untrusted_model_cannot_supply_remedies_or_bad_boxes(finding):
    with pytest.raises(ValueError):advisors.advise_sewout({'quality':'usable','findings':[finding]}, {},load_knowledge())


def test_three_mm_satin_text_has_cited_threshold_and_three_options():
    report=advisors.check_lettering(3,'satin','unspecified',load_knowledge())
    assert report['minimum_cap_height_mm']==5 and report['below_seed_minimum']
    assert report['scale_factor']==pytest.approx(5/3)
    assert len(report['options'])==3 and not report['operations']
    assert report['citations'][0]['row_id']=='satin.default'


def test_placement_uses_data_not_literal_cap_number():
    from embroiderly.assistance import local_edit
    patch,reason=local_edit('fit a cap',{'selection':'full'},Image.new('RGBA',(40,40),'red'))
    cap=next(r for r in load_knowledge()['placements.json']['rows'] if r['id']=='cap.front')
    assert patch['height_mm']==cap['height_range_mm'][1]
    assert 'placements.json#cap.front' in reason and 'unverified' in reason


@pytest.fixture
def review_app(tmp_path,monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False);monkeypatch.delenv('EMBROIDERLY_AI_MODEL',raising=False)
    (tmp_path/'work'/'uploads').mkdir(parents=True)
    image=Image.new('RGB',(40,40),'red');image.save(tmp_path/'work'/'uploads'/'test.png')
    plan={'steps':[{'t':'stitch','x':0,'y':0,'color':'#000000'},{'t':'stitch','x':1,'y':1,'color':'#000000'}],
          'colors':['#000000'],'stitch_count':2}
    monkeypatch.setattr('embroiderly.saved_plans.matching_plan',lambda *a,**k:{'playback':plan})
    app=create_app(tmp_path)
    return app,app.test_client(),tmp_path,plan


def post_photo(client,consent=True,colour='blue'):
    file=io.BytesIO();Image.new('RGB',(40,40),colour).save(file,format='PNG');file.seek(0)
    return client.post('/advisors/sewout/test.png',data={'photo':(file,'sample.png'),'options':'{}','consent':str(consent).lower()})


def test_no_consent_no_model_and_manual_tools_still_work(review_app):
    app,client,root,plan=review_app
    assert post_photo(client,False).status_code==400
    assert post_photo(client).status_code==503
    assert client.get('/advisors/sewout/test.png').json['history']==[]
    result=client.post('/artwork/test.png',json={'options':{'selection':'full','height_mm':100,'count':2}})
    assert result.status_code==200


def test_cached_repeat_persists_reports_without_mutating_design(review_app,monkeypatch):
    app,client,root,plan=review_app
    monkeypatch.setenv('OPENAI_API_KEY','not-real');monkeypatch.setenv('EMBROIDERLY_AI_MODEL','mock')
    # Cache tests isolate observation; the real dollar gate has separate tests.
    monkeypatch.setattr('embroiderly.sewout_review.configured',lambda:True)
    calls=[]
    def fake(photo,reference,knowledge,limit):
        calls.append(1);assert photo.info=={}
        return {'quality':'usable','findings':[{'issue_id':'puckering','box':[.1,.1,.9,.9]}]}
    monkeypatch.setattr('embroiderly.sewout_review.observe',fake)
    original=(root/'work'/'uploads'/'test.png').read_bytes()
    reports=[post_photo(client).json['report'] for _ in range(3)]
    assert calls==[1]
    assert all(r['operations']==[] and r['patch']=={} for r in reports)
    assert reports[0]['findings']==reports[1]['findings']==reports[2]['findings']
    history=client.get('/advisors/sewout/test.png').json
    assert len(history['history'])==3 and history['requests_used']==1
    assert not list((root/'work'/'decisions').glob('*'))
    assert (root/'work'/'uploads'/'test.png').read_bytes()==original
    plan['stitch_count']=3
    changed=post_photo(client,False).json['report']
    assert changed['comparison_plan_changed'] and calls==[1]


def test_budget_limits_new_model_requests_and_bad_output_never_saved(review_app,monkeypatch):
    app,client,root,plan=review_app
    monkeypatch.setenv('OPENAI_API_KEY','not-real');monkeypatch.setenv('EMBROIDERLY_AI_MODEL','mock')
    # Cache tests isolate observation; the real dollar gate has separate tests.
    monkeypatch.setattr('embroiderly.sewout_review.configured',lambda:True)
    calls=[]
    def bad(*args):calls.append(1);return {'quality':'usable','findings':[],'patch':{'count':2}}
    monkeypatch.setattr('embroiderly.sewout_review.observe',bad)
    for colour in ['red','green','blue']:assert post_photo(client,colour=colour).status_code==503
    result=post_photo(client,colour='yellow')
    assert result.status_code==400 and 'limit' in result.json['error']
    assert len(calls)==3
    assert client.get('/advisors/sewout/test.png').json['history']==[]
