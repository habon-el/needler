import numpy as np
import pytest
from PIL import Image,ImageDraw
from embroiderly.preparation import prepare
from embroiderly.portrait import proposal
from embroiderly.web import create_app


def test_merge_threshold_recovery_preview(tmp_path):
    app=create_app(tmp_path);source=tmp_path/'work/uploads/p.png'
    im=Image.new('RGB',(100,100),'#c8a080');ImageDraw.Draw(im).rectangle((20,30,70,40),fill='#604030');im.save(source)
    options={**proposal(),'height_mm':150,'portrait_merge_delta_e':100}
    client=app.test_client();before=client.post('/details/p.png',json={'options':options}).json
    finding=next(f for f in before['audit']['findings'] if f['cause']=='recorded palette merge')
    result=client.post('/details/p.png',json={'options':options,'action':'recover','strategy':'merge_threshold','id':finding['id']})
    assert result.status_code==200
    assert result.json['patch']=={'portrait_merge_delta_e':0}
    assert result.json['after_colours']>result.json['colours']
    assert len(result.json['after_audit']['findings'])<len(before['audit']['findings'])


def test_recovery_bounds_and_palette_budget(tmp_path):
    source=tmp_path/'p.png';im=Image.new('RGB',(60,60),'red');im.save(source)
    with pytest.raises(ValueError):prepare(source,{'detail_recoveries':[{'bounds':[-1,0,40,40],'colour':'#000000'}]})
    with pytest.raises(ValueError):prepare(source,{'detail_recoveries':[{'bounds':[0,0,40,40],'colour':'invalid'}]})


def test_small_mask_cleanup_has_location(tmp_path):
    source=tmp_path/'p.png';im=Image.new('RGBA',(100,100),(0,0,0,0));d=ImageDraw.Draw(im)
    d.rectangle((10,10,80,80),fill='red');d.point((95,95),fill='red');im.save(source)
    _,_,report=prepare(source,{'height_mm':20,'floor_mm2':1})
    assert any(v['bounds']==[95,95,96,96] for v in report['detail_loss']['mask_cleanup_changes'])
