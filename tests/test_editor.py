from PIL import Image
from embroiderly.web import create_app


def test_editor_saves_size_and_drives_playback(tmp_path):
    uploads=tmp_path/'work'/'uploads'
    uploads.mkdir(parents=True)
    Image.new('RGB',(100,100),'white').save(uploads/'test.png')
    client=create_app(tmp_path).test_client()
    state={'height_mm':50,'paths':[{'points':[[10,10],[30,10]],'colour':'#000000','kind':'sewn'}]}
    assert client.post('/editor/test.png',json=state).status_code==200
    response=client.get('/simulate/test.png')
    assert response.status_code==200
    import json
    payload=json.loads((tmp_path/'work/machine-preview/test/playback.json').read_text())
    assert any(s['x']==15 and s['y']==5 for s in payload['steps'])
    state['height_mm']=-1
    assert client.post('/editor/test.png',json=state).status_code==400
