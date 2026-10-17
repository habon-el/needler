import copy,json
import numpy as np
import pytest
from PIL import Image,ImageDraw
from embroiderly.refinement import replay,digest,worklist,make_operation
from embroiderly.subject_model import mask_runs,propose_mask,_cache
from embroiderly.preparation import prepare
from embroiderly.web import create_app


def fixture(tmp_path):
    source=Image.new('RGBA',(100,100),'#c8a080');draw=ImageDraw.Draw(source)
    draw.rectangle((20,30,44,36),fill='#604030');draw.rectangle((60,30,84,36),fill='#604030')
    path=tmp_path/'source.png';source.save(path)
    options=dict(count=4,smooth=0,floor_mm2=0,mask_holes_mm2=0,height_mm=100,merges={'#604030':'#c8a080'})
    output,_,report=prepare(path,options)
    # A deterministic full-coverage sewn raster of the deliberately flat preparation.
    steps=[]
    for y in range(100):steps.extend([dict(x=-50,y=y-50,t='jump',color='#c8a080'),dict(x=49,y=y-50,t='stitch',color='#c8a080')])
    payload=dict(height_mm=100,origin_mm=[50,50],thread_width_mm=1,steps=steps)
    return source,path,options,output,report,payload


def test_worklist_diagnoses_merge_not_mask_and_is_repeatable(tmp_path):
    source,path,options,output,report,payload=fixture(tmp_path)
    a,_=worklist(source,output,payload,report);b,_=worklist(source,output,payload,report)
    assert a==b
    assert len(a['patches'])==2
    assert all(p['diagnosis']=='colour-merge' for p in a['patches'])
    assert all('add-region' not in p['remedies'] for p in a['patches'])
    with pytest.raises(ValueError):make_operation(source,output,a['patches'][0],'add-region',options)


def test_local_split_replay_preserves_other_region_and_reopens(tmp_path):
    source,path,options,output,report,payload=fixture(tmp_path)
    audit,_=worklist(source,output,payload,report);p=audit['patches'][0]
    op,_=make_operation(source,output,p,'split-region',options)
    after,history=replay(source,output,[op]);again,_=replay(source,output,json.loads(json.dumps([op])))
    assert after.tobytes()==again.tobytes()
    assert history[0]['changed_pixels']>0
    assert history[0]['outside_rgba_hash_before']==history[0]['outside_rgba_hash_after']
    assert history[0]['outside_mask_hash_before']==history[0]['outside_mask_hash_after']
    p2=audit['patches'][1];x,y,r,b=p2['bounds']
    assert digest(np.array(output)[y:b,x:r])==digest(np.array(after)[y:b,x:r])
    assert op['local_threshold_delta_e76']<op['measured_delta_e76']
    regenerated=prepare(path,{**options,'refinement_ops':[op]})[0]
    assert regenerated.tobytes()==after.tobytes()


def test_mask_add_is_union_and_interior_click_changes_nothing(tmp_path):
    source,path,options,output,report,payload=fixture(tmp_path)
    base=np.array(output);base[25:40,15:50]=0
    op=dict(version=1,type='add-region',bounds=[15,25,50,40],point=[20,30],mask_runs=mask_runs(np.ones((15,35),bool)),colour='#c8a080',image_hash=digest(np.array(source)))
    after,history=replay(source,Image.fromarray(base),[op]);assert np.all(np.array(after)[25:40,15:50,3]==255)
    assert history[0]['outside_mask_hash_before']==history[0]['outside_mask_hash_after']
    same,history=replay(source,output,[op]);assert same.tobytes()==output.tobytes();assert history[0]['changed_pixels']==0
    op['type']='subtract-region';removed,_=replay(source,output,[op]);assert not np.array(removed)[25:40,15:50,3].any()


def test_small_retained_region_reports_physical_width(tmp_path):
    source,path,options,output,report,payload=fixture(tmp_path)
    # One-pixel vertical detail at 60 mm canvas height is 0.6 mm wide.
    source=Image.new('RGBA',(100,100),'#c8a080');ImageDraw.Draw(source).rectangle((40,30,40,50),fill='#604030')
    report={'height_mm':60,'detail_loss':{}};payload['height_mm']=60;payload['origin_mm']=[30,30]
    payload['steps']=[dict(x=s['x']*.6,y=s['y']*.6,t=s['t'],color=s['color']) for s in payload['steps']]
    audit,_=worklist(source,source,payload,report)
    patch=next(p for p in audit['patches'] if p['diagnosis']=='physical-limit')
    assert patch['width_mm']==.6 and patch['canvas_height_for_shape_mm']==100
    assert patch['remedies']==[]


def test_cached_click_never_reencodes_with_predictor_fixture():
    class Predictor:
        encodes=0
        def set_image(self,image):self.shape=image.shape[:2];Predictor.encodes+=1
        def predict(self,**kwargs):return np.ones((1,*self.shape),bool),np.array([1.]),None
    _cache.clear();image=Image.new('RGBA',(40,40),'red')
    _,first=propose_mask(image,[{'point':[15,15],'label':1}],factory=Predictor)
    _,second=propose_mask(image,[{'point':[20,20],'label':1}],factory=Predictor)
    assert Predictor.encodes==1 and second['embedding_reused'] is True
    assert second['encoder_ms']==0 and second['decoder_ms']>=0
    _cache.clear()


def test_no_current_stitch_plan_no_fake_comparison(tmp_path):
    client=create_app(tmp_path).test_client();Image.new('RGB',(30,30),'red').save(tmp_path/'work/uploads/p.png')
    assert client.post('/refine/p.png',json={'options':{}}).status_code==409
