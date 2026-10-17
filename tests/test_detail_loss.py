import json
import numpy as np
from PIL import Image,ImageDraw
from embroiderly.preparation import prepare
from embroiderly.detail_loss import check
from embroiderly.subject_model import propose_mask,unpack_mask,_cache
from embroiderly.web import create_app


def artwork(path):
    image=Image.new('RGB',(120,120),'#c8a080');draw=ImageDraw.Draw(image)
    draw.rectangle((20,35,49,42),fill='#604030');draw.rectangle((70,35,99,42),fill='#604030')
    draw.rectangle((30,80,90,90),fill='#ffffff');image.save(path)
    return image


def test_loss_provenance_repeatability_and_local_recovery(tmp_path):
    source=tmp_path/'brows.png';artwork(source)
    options=dict(count=4,smooth=0,floor_mm2=0,mask_holes_mm2=0,height_mm=120,merges={'#604030':'#c8a080'})
    before,palette,report=prepare(source,options)
    findings=report['detail_loss']['findings']
    assert len(findings)==2
    assert all(f['cause']=='recorded palette merge' for f in findings)
    assert findings[0]['merged_colours']==[{'source':'#604030','target':'#c8a080'}]
    assert report==prepare(source,options)[2]
    f=findings[0];x,y,r,b=f['bounds']
    after,new_palette,new_report=prepare(source,{**options,'detail_recoveries':[dict(bounds=f['bounds'],colour=f['source_tone'],distance=8)]})
    assert len(new_palette)==len(palette)+1
    assert len(new_report['detail_loss']['findings'])<len(findings)
    outside=np.ones((120,120),bool);outside[y:b,x:r]=False
    assert np.array_equal(np.asarray(before)[outside],np.asarray(after)[outside])


def test_clipped_uniform_boundary_and_alternative():
    image=Image.new('RGBA',(100,100),'white');ImageDraw.Draw(image).rectangle((20,10,80,90),fill='brown')
    correct=np.zeros((100,100),bool);correct[10:91,20:81]=True
    clipped=correct.copy();clipped[:35]=False
    def audit(mask):
        output=np.array(image);output[:,:,3]=mask*255
        return check(np.array(image)[:,:,:3],output,mask,100)
    assert len(audit(clipped)['boundary'])>len(audit(correct)['boundary'])
    assert audit(clipped)==audit(clipped)


def test_all_model_candidates_retained(tmp_path):
    image=Image.new('RGBA',(100,100),'white');ImageDraw.Draw(image).rectangle((20,10,80,90),fill='brown')
    correct=np.zeros((100,100),bool);correct[10:91,20:81]=True
    clipped=correct.copy();clipped[:35]=False
    class Predictor:
        def set_image(self,rgb):pass
        def predict(self,**kwargs):return np.array([clipped,correct]),np.array([.9,.8]),None
    _cache.clear()
    mask,info=propose_mask(image,[{'point':[50,50],'label':1}],factory=Predictor)
    assert len(info['candidates'])==2
    assert np.array_equal(mask,clipped)
    assert np.array_equal(unpack_mask(info['candidates'][1]['mask_runs'],correct.shape),correct)
    _cache.clear()


def test_recovery_is_preview_only_and_models_not_required(tmp_path,monkeypatch):
    monkeypatch.delenv('EMBROIDERLY_SAM2_CHECKPOINT',raising=False)
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    app=create_app(tmp_path);source=tmp_path/'work/uploads/brows.png';artwork(source)
    options=dict(count=4,smooth=0,floor_mm2=0,mask_holes_mm2=0,height_mm=120,merges={'#604030':'#c8a080'})
    client=app.test_client();check_result=client.post('/details/brows.png',json={'options':options}).get_json()
    f=check_result['audit']['findings'][0]
    response=client.post('/details/brows.png',json={'options':options,'action':'recover','id':f['id']})
    assert response.status_code==200
    result=response.get_json();assert result['after_colours']==result['colours']+1
    assert not list((tmp_path/'work/decisions').glob('*.preparation.json'))
    assert client.post('/details/brows.png',json={'options':options,'action':'recover','id':'stale'}).status_code==400
