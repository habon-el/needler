from PIL import Image, ImageDraw
from embroiderly.web import create_app
import json


def test_colour_selection_recolours_and_excludes_playback(tmp_path):
    uploads=tmp_path/'work/uploads'
    uploads.mkdir(parents=True)
    im=Image.new('RGB',(100,100),'white')
    ImageDraw.Draw(im).line((10,10,80,80),fill='black',width=2)
    im.save(uploads/'art.png')
    client=create_app(tmp_path).test_client()
    assert client.get('/colours/art.png').status_code==200
    choices={'#000000':{'include':True,'thread':'#ff8000'},'#ffffff':{'include':False,'thread':'#ffffff'}}
    assert client.post('/colours/art.png',json=choices).status_code==200
    assert client.get('/simulate/art.png').status_code==200
    payload=json.loads((tmp_path/'work/machine-preview/art/playback.json').read_text())
    assert payload['colors']==['#ff8000']
    choices['#000000']['include']=False
    client.post('/colours/art.png',json=choices)
    response=client.get('/simulate/art.png')
    assert b'0 stitch commands' in response.data
