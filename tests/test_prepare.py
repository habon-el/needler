from io import BytesIO
from PIL import Image
from embroiderly.web import create_app


def test_upload_prepares_before_analysis_and_preserves_original(tmp_path):
    client=create_app(tmp_path).test_client()
    buf=BytesIO(); Image.new('RGB',(100,80),'white').save(buf,format='PNG');buf.seek(0)
    response=client.post('/upload',data={'image':(buf,'art.png')})
    assert '/prepare/' in response.location
    url=response.location
    assert '/artwork/' in client.get(url).location
    assert client.get(url,follow_redirects=True).status_code==200
    assert client.post(url,data={'left':0,'top':0,'right':101,'bottom':80}).status_code==400
    result=client.post(url,data={'left':10,'top':20,'right':90,'bottom':70})
    assert '/review/' in result.location
    name=result.location.rsplit('/',1)[1]
    assert Image.open(tmp_path/'work/uploads'/name).size==(80,50)
    original=url.rsplit('/',1)[1]
    assert Image.open(tmp_path/'work/uploads'/original).size==(100,80)
    import json
    cut=client.post(url,data={'left':0,'top':0,'right':100,'bottom':80,
        'outline':json.dumps([[10,10],[80,10],[10,70]])})
    assert cut.status_code==302
    subject=Image.open(tmp_path/'work/uploads'/cut.location.rsplit('/',1)[1])
    assert subject.getpixel((20,20))[3]==255
    assert subject.getpixel((90,70))[3]==0
    assert Image.open(tmp_path/'work/uploads'/original).mode=='RGB'
