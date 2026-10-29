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
    settings={**OPTIONS,'smooth':smooth,'cleanup_choice':'review'}
    _,_,report=prepare(source,settings)
    item=report['cleanup_review'][0]
    assert (item['width_mm'],item['height_mm'],item['area_mm2'])==(.5,.5,.25)
    assert item['bounds']==[48,48,50,50] and item['decision']=='pending'
    options={**settings,'cleanup_decisions':{item['id']:'keep'}}
    image,_,after=prepare(source,options)
    assert image.getpixel((48,48))==(0,0,0,255)
    assert after['cleanup_review'][0]['decision']=='keep'


def test_review_choice_requires_each_cleanup_decision(tmp_path):
    client=create_app(tmp_path).test_client();detail(tmp_path/'work/uploads/detail.png')
    options={**OPTIONS,'cleanup_choice':'review'}
    response=client.post('/artwork/detail.png',json={'options':options,'save':True})
    assert response.status_code==400
    assert 'Review cleanup' in response.json['error']
    preview=client.post('/artwork/detail.png',json={'options':options}).json
    decisions={i['id']:'drop' for i in preview['report']['cleanup_review']}
    assert client.post('/artwork/detail.png',json={'options':{**options,'cleanup_decisions':decisions},'save':True}).status_code==200


def specks(path):
    # A 0.5 mm speck and a 1.5 mm square, both under the 3 mm² area floor.
    image=Image.new('RGBA',(100,100),'red');draw=ImageDraw.Draw(image)
    draw.rectangle((20,20,21,21),fill='black');draw.rectangle((60,60,65,65),fill='black');image.save(path)
    return image


def test_automatic_choice_asks_nothing_lets_specks_go_and_keeps_larger_details(tmp_path):
    source=tmp_path/'specks.png';specks(source)
    image,_,report=prepare(source,{**OPTIONS,'floor_mm2':3})
    assert report['cleanup_choice']=='auto'
    decisions={tuple(r['bounds']):r['decision'] for r in report['cleanup_review']}
    assert decisions=={(20,20,22,22):'auto',(60,60,66,66):'keep'}
    assert image.getpixel((20,20))[:3]==(255,0,0) and image.getpixel((62,62))[:3]==(0,0,0)
    client=create_app(tmp_path).test_client();specks(tmp_path/'work/uploads/specks.png')
    assert client.post('/artwork/specks.png',json={'options':{**OPTIONS,'floor_mm2':3},'save':True}).status_code==200


@pytest.mark.parametrize('choice,dot,square',[('keep',(0,0,0),(0,0,0)),('drop',(255,0,0),(255,0,0))])
def test_one_choice_keeps_or_lets_go_every_change(tmp_path,choice,dot,square):
    source=tmp_path/'specks.png';specks(source)
    image,_,report=prepare(source,{**OPTIONS,'floor_mm2':3,'cleanup_choice':choice})
    assert image.getpixel((20,20))[:3]==dot and image.getpixel((62,62))[:3]==square
    assert not any(r['decision']=='pending' for r in report['cleanup_review'])


def test_designs_saved_with_old_per_detail_choices_map_to_the_nearest_choice(tmp_path):
    from embroiderly.cleanup_review import cleanup_choice
    assert cleanup_choice({})=='auto'
    assert cleanup_choice({'cleanup_decisions':{'a':'keep','b':'keep'}})=='keep'
    assert cleanup_choice({'cleanup_decisions':{'a':'drop'}})=='drop'
    assert cleanup_choice({'cleanup_decisions':{'a':'keep','b':'drop'}})=='auto'
    with pytest.raises(ValueError,match='cleanup choice'):cleanup_choice({'cleanup_choice':'all thirty'})
    # The old per-detail choice still decides its own detail.
    source=tmp_path/'specks.png';specks(source)
    _,_,report=prepare(source,{**OPTIONS,'floor_mm2':3,'cleanup_choice':'review'})
    old={r['id']:'drop' for r in report['cleanup_review'] if r['bounds']==[60,60,66,66]}
    image,_,report=prepare(source,{**OPTIONS,'floor_mm2':3,'cleanup_decisions':old})
    assert report['cleanup_choice']=='drop' and image.getpixel((62,62))[:3]==(255,0,0)
