import numpy as np
import pytest
from PIL import Image,ImageDraw
from embroiderly.web import create_app
from embroiderly.subject_model import mask_runs


@pytest.fixture
def client(tmp_path):
    app=create_app(tmp_path)
    image=Image.new('RGBA',(40,40),'white')
    ImageDraw.Draw(image).rectangle((10,10,30,30),fill='red')
    image.save(tmp_path/'work/uploads/safety.png')
    return app.test_client()


def test_cloud_never_called_without_consent(client,monkeypatch):
    monkeypatch.setattr('embroiderly.assistance.cloud_available',lambda:True)
    def forbidden(*args):raise AssertionError('No consent')
    monkeypatch.setattr('embroiderly.assistance.cloud_advice',forbidden)
    result=client.post('/assist/safety.png',json={'options':{'count':4},'action':'edit','text':'fewer colours'})
    assert result.status_code==200
    assert result.json['patch']=={'count':3}
    assert result.json['method']=='Offline suggestion'


def test_cloud_failure_preserves_offline_edit(client,monkeypatch):
    monkeypatch.setattr('embroiderly.assistance.cloud_available',lambda:True)
    def unavailable(*args):raise TimeoutError()
    monkeypatch.setattr('embroiderly.assistance.cloud_advice',unavailable)
    result=client.post('/assist/safety.png',json={'options':{'count':4},'action':'edit','text':'fewer colours','cloud_consent':True})
    assert result.status_code==200
    assert result.json['patch']=={'count':3}
    assert 'unavailable' in result.json['reasons'][0]


@pytest.mark.parametrize('body',[{'changes':[]},{'measurements':[]},[],None])
def test_malformed_correction_event_returns_400(client,body):
    assert client.post('/assist-events/safety.png',json=body).status_code==400


def test_frozen_mask_preview_does_not_call_model(client,monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('Preview must reuse proposal')
    monkeypatch.setattr('embroiderly.assistance.propose_mask',forbidden)
    mask=np.zeros((40,40),bool);mask[10:31,10:31]=True
    patch={'selection':'assisted','mask_runs':mask_runs(mask),'hints':[],'edge':0}
    response=client.post('/assist/safety.png',json={'options':{'count':4},'action':'preview','patch':patch})
    assert response.status_code==200,response.json
    assert response.json['patch']==patch
    assert response.json['after']['colours_after']==1


def test_mask_preview_cannot_smuggle_unsupported_changes(client):
    response=client.post('/assist/safety.png',json={'options':{},'action':'preview','patch':{'selection':'assisted','mask_runs':[0,1600],'hints':[],'edge':0,'stitches':[]}})
    assert response.status_code==400
