import copy
import hashlib
import json
from pathlib import Path
import numpy as np
import pytest
from PIL import Image,ImageDraw
from embroiderly.colour_knockout import remove_colour,propose_background,proposal_patch,defaults
from embroiderly.preparation import prepare
from embroiderly.web import create_app


def fixture():
    im=Image.new('RGB',(320,240),'white');d=ImageDraw.Draw(im)
    d.rectangle((20,20,300,220),fill='black')
    for x in (45,105,165,225):d.ellipse((x,40,x+30,90),fill='white')
    points=[(x,y) for y in range(120,210,9) for x in range(35,290,9)][:214]
    for point in points:d.point(point,fill='white')
    return im,points


def run(im,**overrides):
    a=np.asarray(im.convert('RGB'));return remove_colour(a,np.ones(a.shape[:2],bool),
        {'colour':'#ffffff','scope':'everywhere',**overrides},60)


def test_global_removes_enclosed_colour_and_fills_only_specks():
    im,points=fixture();rgb,mask,report=run(im)
    assert report['remaining_colour_area_mm2']==0
    assert report['filled_specks']==0 and len(report['parts'])==218
    assert all(not mask[y,x] for x,y in points)
    ids=[p['id'] for p in report['parts'] if p['review_hole']]
    rgb,mask,report=run(im,fill_parts=ids)
    assert report['filled_specks']==214
    assert all(mask[y,x] and max(rgb[y,x])==0 for x,y in points)
    assert all(not mask[65,x] for x in (60,120,180,240))
    assert not mask[0,0] and all(not p['keep'] for p in report['parts'])
    assert report['seed_verified'] is False and report['seed_citation'].startswith('knockout.json#')


def test_cleanup_undo_alone_preserves_background_removal():
    im,points=fixture();rgb,mask,report=run(im,cleanup=False)
    assert report['filled_specks']==0 and report['tiny_specks']==214
    assert all(not mask[y,x] for x,y in points)
    assert not mask[0,0] and not mask[65,60]


def test_connected_scope_does_not_remove_other_white_parts():
    im,_=fixture();_,mask,report=run(im,scope='this area',point=[0,0])
    assert not mask[0,0] and mask[65,60]
    assert report['remaining_colour_area_mm2']>0


def test_antialias_closer_lab_side_and_no_halo():
    im=Image.new('RGB',(100,100),'white');d=ImageDraw.Draw(im)
    d.rectangle((25,20,75,80),fill='black')
    d.line((24,20,24,80),fill=(190,190,190))
    d.line((25,20,25,80),fill=(100,100,100))
    rgb,mask,_=run(im,cleanup=False)
    assert not mask[40,24] and mask[40,25]
    assert max(rgb[40,25])<10 and np.max(rgb[mask])<10


def test_cartoon_white_eyes_are_recoverable_parts():
    im=Image.new('RGB',(160,140),'white');d=ImageDraw.Draw(im)
    d.ellipse((20,15,140,130),fill='#dd7722')
    d.ellipse((45,45,70,75),fill='white');d.ellipse((90,45,115,75),fill='white')
    d.ellipse((53,54,61,65),fill='black');d.ellipse((98,54,106,65),fill='black')
    _,mask,r=run(im);assert len(r['parts'])==2 and not mask[50,50]
    rgb,restored,r2=run(im,restore_parts=[r['parts'][0]['id']])
    assert restored[50,50] and np.all(rgb[50,50]==255)
    assert not restored[50,95] and not restored[0,0]


def test_badge_text_offered_not_destroyed():
    im=Image.new('RGB',(160,100),'white');d=ImageDraw.Draw(im)
    d.rectangle((15,15,145,85),fill='black')
    d.text((50,45),'HI',fill='white',stroke_width=1)
    original=np.asarray(im);_,mask,r=run(im,minimum_area_mm2=.05)
    assert r['parts'] and all(not p['keep'] for p in r['parts'])
    rgb,restored,_=run(im,minimum_area_mm2=.05,restore_parts=[p['id'] for p in r['parts']])
    text=(original[20:80,20:140]==255).all(2)
    assert restored[20:80,20:140][text].all()
    assert np.all(rgb[20:80,20:140][text]==255) and not restored[0,0]


def test_propose_only_flat_dominant_border_no_mutation():
    im,_=fixture();before=im.tobytes();proposal=propose_background(im.convert('RGBA'))
    assert proposal['scope']=='everywhere' and proposal['colour']=='#ffffff'
    assert before==im.tobytes()
    rng=np.random.default_rng(2);photo=Image.fromarray(rng.integers(0,256,(100,100,3),dtype=np.uint8))
    assert propose_background(photo) is None


def test_close_radius_is_in_physical_units_never_above_point_two():
    im,_=fixture()
    for height in (10,40,100,400):
        _,_,r=remove_colour(np.asarray(im),np.ones((240,320),bool),{'colour':'#ffffff','scope':'everywhere'},height)
        assert 0<=r['effective_close_radius_mm']<=defaults()['maximum_close_radius_mm']


@pytest.mark.parametrize('patch',[{'tolerance':float('nan')},{'scope':'all'},{'colour':'white'},{'cleanup':1},{'restore_parts':['fake']},{'close_radius_mm':.21}])
def test_invalid_operations_are_rejected(patch):
    im,_=fixture()
    with pytest.raises(ValueError):run(im,**patch)


def test_prepare_replay_save_and_determinism(tmp_path):
    im,_=fixture();path=tmp_path/'sample.png';im.save(path);before=hashlib.sha256(path.read_bytes()).hexdigest()
    patch=proposal_patch(im.convert('RGBA'),{});options=dict(height_mm=60,**patch);saved=copy.deepcopy(options)
    a,palette,report=prepare(path,options);b,_,other=prepare(path,options)
    assert a.tobytes()==b.tobytes() and report==other and options==saved
    assert [p['hex'] for p in palette]==['#000000']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before


def test_assistant_offline_propose_apply_save_flow(tmp_path):
    app=create_app(tmp_path);uploads=tmp_path/'work/uploads';uploads.mkdir(parents=True,exist_ok=True)
    im,_=fixture();im.save(uploads/'lettering.png');client=app.test_client()
    for command in ['remove the white','keep only the black']:
        response=client.post('/assist/lettering.png',json={'action':'edit','text':command,'options':{'height_mm':60}})
        assert response.status_code==200,response.json
        result=response.json;assert result['operation']=='colour-knockout'
        assert result['knockout']['remaining_colour_area_mm2']==0
        assert not (tmp_path/'work/decisions/lettering.png.preparation.json').exists()
    preview=client.post('/assist/lettering.png',json={'action':'preview','patch':result['patch'],'options':{'height_mm':60}})
    assert preview.status_code==200
    accepted={'height_mm':60,**result['patch']}
    applied=client.post('/artwork/lettering.png',json={'options':accepted,'save':True})
    assert applied.status_code==200,applied.json
    assert json.loads((tmp_path/'work/decisions/lettering.png.preparation.json').read_text())==accepted
@pytest.mark.parametrize('extra',[{'artwork_type':'portrait'},{'refinement_ops':[{'type':'add-region'}]}])
def test_incompatible_recovery_or_portrait_is_explicit(tmp_path,extra):
    im,_=fixture();path=tmp_path/'art.png';im.save(path)
    with pytest.raises(ValueError,match='Colour removal'):
        prepare(path,{**extra,**proposal_patch(im,{})})

