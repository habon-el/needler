import io
import json
from pathlib import Path
import numpy as np
import pytest
from PIL import Image,ImageDraw
from embroiderly.web import create_app


def test_prepared_legacy_preview_redirects_to_current_stitches(tmp_path):
    app=create_app(tmp_path);client=app.test_client();uploads=tmp_path/'work/uploads'
    Image.new('RGB',(30,30),'black').save(uploads/'source.png')
    Image.new('RGB',(30,30),'black').save(uploads/'prepared_test.png')
    (uploads/'prepared_test.prep.json').write_text(json.dumps({'source':'source.png','options':{}}))
    for suffix in ['', '?view=1']:
        response=client.get('/engine/prepared_test.png'+suffix,follow_redirects=True)
        assert response.status_code==200
        assert response.request.path=='/artwork/source.png'
        assert response.request.args['view']=='stitched'
        assert b'workspace-ui.js' in response.data and b'View stitches' in response.data
        assert b'Advanced playback' not in response.data
    assert not (tmp_path/'work/decisions/source.png.preparation.json').exists()


def test_invalid_workspace_view_is_not_propagated(tmp_path):
    app=create_app(tmp_path);client=app.test_client();uploads=tmp_path/'work/uploads'
    for name in ['source.png','prepared.png']:Image.new('RGB',(30,30),'black').save(uploads/name)
    (uploads/'prepared.prep.json').write_text(json.dumps({'source':'source.png'}))
    response=client.get('/artwork/prepared.png?view=javascript:bad')
    assert response.location=='/artwork/source.png'
    assert client.get('/engine/missing.png?view=1').status_code==404


@pytest.mark.parametrize('background,ink,format',[
    ('white','black','PNG'),((248,246,240),(18,18,18),'JPEG'),
    ('black','white','PNG'),('#286bb9','#f3ac35','PNG')])
def test_new_uploads_share_colour_knockout(tmp_path,monkeypatch,background,ink,format):
    # Different, generated art: three closed outlines, not the Big thanks asset.
    im=Image.new('RGB',(300,220),background);draw=ImageDraw.Draw(im)
    for x in [25,120,215]:
        draw.rectangle((x,30,x+60,180),fill=ink)
        draw.rectangle((x+15,50,x+45,160),fill=background)
    encoded=io.BytesIO();im.save(encoded,format=format);source=encoded.getvalue()
    monkeypatch.setattr('embroiderly.subject_model.warm_image',lambda image:None)
    app=create_app(tmp_path);client=app.test_client()
    response=client.post('/upload',data={'image':(io.BytesIO(source),'new-art.'+format.lower())})
    assert response.status_code==302
    name=response.location.split('/')[-1]
    before=client.post('/artwork/'+name,json={'options':{}}).get_json()
    op=before['report']['background_proposal'];assert op and op['scope']=='everywhere'
    proposed=client.post('/assist/'+name,json={'action':'remove_colour','operation':op,'options':{}})
    assert proposed.status_code==200,proposed.get_json()
    result=proposed.get_json();assert result['knockout']['remaining_colour_area_mm2']==0
    assert len(result['knockout']['parts'])==3 and not any(p['keep'] for p in result['knockout']['parts'])
    assert not (tmp_path/'work/decisions'/(name+'.preparation.json')).exists(), 'Proposal must not apply or save'
    applied=client.post('/artwork/'+name,json={'options':result['patch'],'save':True}).get_json()
    import base64
    pixels=np.asarray(Image.open(io.BytesIO(base64.b64decode(applied['image'].split(',')[1]))))
    assert pixels[0,0,3]==0
    for x in [25,120,215]:
        assert pixels[100,x+30,3]==0 and pixels[100,x+5,3]==255
    assert (tmp_path/'work/uploads'/name).read_bytes()==source
