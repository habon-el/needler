import pytest
from PIL import Image,ImageDraw
from embroiderly.preparation import prepare
from embroiderly.web import create_app


def detail(path):
    image=Image.new('RGBA',(100,100),'red')
    ImageDraw.Draw(image).rectangle((48,48,49,49),fill='black');image.save(path)


OPTIONS=dict(count=2,height_mm=25,floor_mm2=1,smooth=0)


@pytest.mark.parametrize('smooth',[0,1])
def test_half_mm_review_has_actual_size_and_keep_restores(tmp_path,smooth):
    source=tmp_path/'detail.png';detail(source)
    settings={**OPTIONS,'smooth':smooth}
    _,_,report=prepare(source,settings)
    item=report['cleanup_review'][0]
    assert (item['width_mm'],item['height_mm'],item['area_mm2'])==(.5,.5,.25)
    assert item['bounds']==[48,48,50,50] and item['decision']=='pending'
    options={**settings,'cleanup_decisions':{item['id']:'keep'}}
    image,_,after=prepare(source,options)
    assert image.getpixel((48,48))==(0,0,0,255)
    assert after['cleanup_review'][0]['decision']=='keep'


def test_save_requires_each_cleanup_decision(tmp_path):
    client=create_app(tmp_path).test_client();detail(tmp_path/'work/uploads/detail.png')
    response=client.post('/artwork/detail.png',json={'options':OPTIONS,'save':True})
    assert response.status_code==400
    assert 'Review cleanup' in response.json['error']
    preview=client.post('/artwork/detail.png',json={'options':OPTIONS}).json
    decisions={i['id']:'drop' for i in preview['report']['cleanup_review']}
    assert client.post('/artwork/detail.png',json={'options':{**OPTIONS,'cleanup_decisions':decisions},'save':True}).status_code==200
