import hashlib,json
from pathlib import Path
import numpy as np
import pytest
from PIL import Image,ImageDraw
from embroiderly.preparation import prepare
from embroiderly.portrait import proposal,feature_report
from embroiderly.photo_stitch import generate,verify_file


def test_logo_explicit_mode_is_unchanged(tmp_path):
    p=tmp_path/'logo.png';im=Image.new('RGB',(100,100),'white');ImageDraw.Draw(im).rectangle((15,10,80,85),fill='red');im.save(p)
    a,pal,report=prepare(p,{'count':4})
    b,bpal,breport=prepare(p,{'count':4,'artwork_type':'logo'})
    assert a.tobytes()==b.tobytes() and pal==bpal and report==breport


def test_portrait_palette_ceiling_and_named_feature(tmp_path):
    p=tmp_path/'portrait.png';im=Image.new('RGB',(100,100),(170,110,80));draw=ImageDraw.Draw(im)
    for i in range(12):draw.rectangle((i*8,0,i*8+7,99),fill=(50+i*15,30+i*12,20+i*10))
    draw.rectangle((40,62,60,70),fill=(45,20,20));draw.rectangle((44,63,57,65),fill='white');im.save(p)
    options={**proposal(),'count':12,'height_mm':150,'portrait_features':[{'kind':'mouth','bounds':[40,62,61,71]},{'kind':'teeth','bounds':[44,63,58,66]}]}
    out,palette,r=prepare(p,options)
    assert len(palette)>8
    assert r['portrait_features'][0]['prepared_colours']>=2
    assert 'one light shape' in r['portrait_features'][1]['alternative']
    assert 'portrait_removals' in r
    with pytest.raises(ValueError):prepare(p,{**options,'floor_mm2':0})


def test_every_small_component_change_is_reported(tmp_path):
    p=tmp_path/'small.png';im=Image.new('RGB',(50,50),'red');draw=ImageDraw.Draw(im)
    for xy in [(4,4),(10,10),(20,20)]:draw.point(xy,fill='black')
    im.save(p);_,_,report=prepare(p,{**proposal(),'height_mm':10})
    removed=[r for r in report['portrait_removals'] if r['colour']=='#000000']
    assert len(removed)==3
    assert all(r['canvas_height_for_area_mm']>10 for r in removed)


def test_photo_stitch_interlocks_and_exports_deterministically(tmp_path):
    path=tmp_path/'prepared.png';image=Image.new('RGBA',(100,80),(190,140,100,255))
    ImageDraw.Draw(image).rectangle((50,0,99,79),fill=(90,40,25,255));image.save(path)
    a=generate(path,tmp_path/'a',20,{'photo_angle':0})
    b=generate(path,tmp_path/'b',20,{'photo_angle':0})
    assert 0<a['portrait_audit']['max_planned_penetration_mm']<=.6
    assert a['portrait_audit']['overlap_count']>0
    for ext in ('pes','dst'):
        audit=verify_file(tmp_path/'a'/('design.'+ext))
        assert .3-1e-8<=audit['shortest_stitch_mm']<=audit['longest_stitch_mm']<=7+1e-8
        assert (tmp_path/'a'/('design.'+ext)).read_bytes()==(tmp_path/'b'/('design.'+ext)).read_bytes()
    assert a['colors']==['#be8c64','#5a2819']


def test_photo_stitch_guides_are_applied_and_validated(tmp_path):
    path=tmp_path/'guide.png';Image.new('RGBA',(50,50),'red').save(path)
    a=generate(path,tmp_path/'a',15,{})
    b=generate(path,tmp_path/'b',15,{'direction_lines':[[[20,20],[20,40]]]})
    assert a['steps']!=b['steps']
    with pytest.raises(ValueError):generate(path,tmp_path/'bad',15,{'direction_lines':[[[20,20],[20,20]]]})
