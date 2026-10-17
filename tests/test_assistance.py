import copy
import json
import numpy as np
import pytest
from PIL import Image, ImageDraw

from embroiderly.assistance import classify, validate_patch, local_edit
from embroiderly.subject_model import mask_runs, unpack_mask, propose_mask, _cache
from embroiderly.preparation import prepare
from embroiderly.web import create_app


@pytest.fixture
def design(tmp_path, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('EMBROIDERLY_AI_MODEL', raising=False)
    monkeypatch.delenv('EMBROIDERLY_SAM2_CHECKPOINT', raising=False)
    monkeypatch.delenv('EMBROIDERLY_SAM2_CONFIG', raising=False)
    monkeypatch.setenv('EMBROIDERLY_SAM2_LOCAL', '0')  # This fixture explicitly tests fallback.
    _cache.clear()
    client=create_app(tmp_path).test_client()
    path=tmp_path/'work/uploads/test.png'
    image=Image.new('RGBA',(80,80),'white')
    ImageDraw.Draw(image).ellipse((20,15,60,65),fill='red')
    image.save(path)
    return client,path,{'selection':'full','count':4,'height_mm':100,'floor_mm2':1,'smooth':1}


@pytest.mark.parametrize('mask', [np.zeros((4,5),bool),np.ones((4,5),bool),np.eye(5,dtype=bool)])
def test_mask_roundtrip(mask):
    assert np.array_equal(mask,unpack_mask(mask_runs(mask),mask.shape))


@pytest.mark.parametrize('runs', [[999], [-1,21], [1.0,19], [True,19], []])
def test_bad_mask_rejected(runs):
    with pytest.raises(ValueError):unpack_mask(runs,(4,5))


@pytest.mark.parametrize('patch',[{'stitches':[]},{'height_mm':float('nan')},{'count':2.3},{'count':True},{'count':99}])
def test_model_cannot_set_geometry_or_invalid_options(patch):
    with pytest.raises(ValueError):validate_patch(patch)


def test_recommend_does_not_save_or_change_options(design):
    client,path,options=design; original=copy.deepcopy(options)
    before=path.read_bytes()
    r=client.post('/assist/test.png',json={'options':options,'action':'recommend'})
    assert r.status_code==200, r.json
    assert r.json['method']=='Offline suggestion'
    assert r.json['patch']
    assert options==original and path.read_bytes()==before
    assert not list(path.parent.glob('prepared_*'))
    assert not (path.parents[1]/'decisions/test.png.preparation.json').exists()


def test_subject_fallback_and_frozen_mask_are_deterministic(design):
    client,path,options=design
    body={'options':options,'action':'segment','points':[{'point':[40,40],'label':1}]}
    a=client.post('/assist/test.png',json=body)
    b=client.post('/assist/test.png',json=body)
    assert a.status_code==200,a.json
    assert a.json['method']=='GrabCut fallback'
    assert a.json['patch']==b.json['patch']
    assert a.json['patch']['selection']=='assisted'
    mask=unpack_mask(a.json['patch']['mask_runs'],(80,80))
    assert mask[40,40] and not mask[0,0]
    proposed={**options,**a.json['patch']}
    first,_,_=prepare(path,proposed)
    second,_,_=prepare(path,proposed)
    assert np.array_equal(first,second)


def test_encoder_cached_per_image_not_per_click():
    _cache.clear();calls={'encode':0,'decode':0}
    class Predictor:
        def set_image(self,image):calls['encode']+=1;self.shape=image.shape[:2]
        def predict(self,**kwargs):
            calls['decode']+=1
            return np.ones((1,*self.shape),bool),np.array([1]),None
    image=Image.new('RGBA',(30,30),'red')
    for p in ([15,15],[17,18]):
        _,info=propose_mask(image,[{'point':p,'label':1}],factory=Predictor)
    assert calls=={'encode':1,'decode':2}
    assert info['embedding_reused']
    propose_mask(Image.new('RGBA',(30,30),'blue'),[{'point':[10,10],'label':1}],factory=Predictor)
    assert calls['encode']==2
    _cache.clear()


def test_review_requires_consent_and_handles_missing_model(design):
    client,_,options=design
    assert client.post('/assist/test.png',json={'options':options,'action':'review'}).status_code==400
    assert client.post('/assist/test.png',json={'options':options,'action':'review','cloud_consent':True}).status_code==503
    assert client.get('/artwork/test.png').status_code==200


def test_ambiguous_request_does_not_guess(design):
    client,_,options=design
    response=client.post('/assist/test.png',json={'options':options,'action':'edit','text':'remove the small text at the bottom'})
    assert response.status_code==200
    assert response.json['patch']=={}
    assert 'Which area' in response.json['reasons'][0]


def test_local_exact_request_and_locked_colours(design):
    client,_,options=design
    response=client.post('/assist/test.png',json={'options':options,'action':'edit','text':'fewer colours'})
    assert response.json['patch']=={'count':3}
    patch,_=local_edit('fewer colours',{'count':4,'locks':['a','b','c','d']},None)
    assert patch['count']==4


def test_correction_records_are_local_numeric_only(design):
    client,path,_=design
    r=client.post('/assist-events/test.png',json={'changes':{'count':[4,3],'prompt':['secret','secret'],'mask_runs':[[0],[1]]},'measurements':{'regions_after':10,'image':'private'}})
    assert r.json['recorded']
    files=list((path.parents[1]/'corrections').glob('*.json'));assert len(files)==1
    record=json.loads(files[0].read_text())
    assert record['changes']=={'count':[4,3]}
    assert record['measurements']=={'regions_after':10}
    assert 'secret' not in files[0].read_text()


def test_subject_mask_size_tampering_rejected(design):
    client,_,options=design
    r=client.post('/artwork/test.png',json={'options':{**options,'selection':'assisted','mask_runs':[0,1]}})
    assert r.status_code==400


def test_model_provider_validation(monkeypatch):
    from embroiderly.assistance import cloud_advice
    monkeypatch.setenv('OPENAI_API_KEY','test-not-a-key')
    monkeypatch.setenv('EMBROIDERLY_AI_MODEL','mock')
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self):return json.dumps({'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps({'changes':[{'setting':'height_mm','value':99999}],'question':'','explanation':'','findings':[]})}]}]}).encode()
    monkeypatch.setattr('urllib.request.urlopen',lambda *a,**k:Response())
    with pytest.raises(ValueError):cloud_advice('edit','anything',[],{}, {})
