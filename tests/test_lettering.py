import json
import xml.etree.ElementTree as ET
import cv2
import numpy as np
import pytest
from PIL import Image
from embroiderly.lettering import catalogue, outline
from embroiderly.web import create_app


def settings(text='Baby 0689'):
    font=next(f for f in catalogue().values() if f['family']=='DejaVu Sans' and f['style']=='Book')
    return dict(text=text,font=font['id'],height_mm=25,spacing=0,align='left',colour='#202020')


def test_deterministic_vector_holes_and_safe_text():
    a=outline(settings('O'));b=outline(settings('O'))
    assert a==b
    tree=ET.fromstring(a[1]);paths=tree.findall('.//{http://www.w3.org/2000/svg}path')
    assert len(paths)==1 and paths[0].attrib['d'].count('M')>=2
    assert not tree.findall('.//{http://www.w3.org/2000/svg}rect')
    assert '<script' not in outline(settings('<script>'))[1]


@pytest.mark.parametrize('patch',[
    {'font':'../../private.ttf'}, {'text':''}, {'text':'a'*201}, {'text':'a\n'*6},
    {'height_mm':float('nan')},{'height_mm':5},{'spacing':-1},{'colour':'url(bad)'},
    {'align':'bad'}, {'text':'مرحبا'}, {'text':'नमस्ते'}, {'text':'\x00'},
])
def test_invalid_recipe_rejected(patch):
    with pytest.raises(ValueError):outline({**settings(),**patch})


def test_create_reopen_and_transparency(tmp_path):
    app=create_app(tmp_path);client=app.test_client()
    fonts=client.get('/lettering/fonts').get_json()
    assert len(fonts['fonts'])>=30 and fonts['families']>=5
    assert all('path' not in f for f in fonts['fonts'])
    assert client.get('/lettering/license/fonts-lato').status_code==200
    assert client.get('/lettering/license/private').status_code==404
    recipe=settings('O')
    preview=client.post('/lettering/preview',json=recipe)
    assert preview.status_code==200 and preview.json['image'].startswith('data:image/svg+xml;base64,')
    result=client.post('/lettering/create',json=recipe)
    assert result.status_code==200,result.json
    name=result.json['name'];path=tmp_path/'work/uploads'/name
    image=Image.open(path).convert('RGBA');alpha=np.asarray(image.getchannel('A'))
    assert alpha[0,0]==0 and alpha[alpha.shape[0]//2,alpha.shape[1]//2]==0
    assert alpha.max()==255
    assert client.get('/lettering/recipe/'+name).json['recipe']==recipe
    saved=json.loads((tmp_path/'work/decisions'/(name+'.preparation.json')).read_text())
    assert saved['mask_holes_mm2']==0 and saved['floor_mm2']==0
    assert saved['height_mm']==27
    # The normal preparation path must preserve the counter too.
    prepared=client.post('/artwork/'+name,json={'options':saved})
    assert prepared.status_code==200,prepared.json
    before=path.read_bytes()
    revised=client.post('/lettering/create',json=settings('Hello'))
    assert revised.status_code==200 and revised.json['name']!=name
    assert path.read_bytes()==before
