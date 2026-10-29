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


def test_upload_never_waits_for_the_subject_model_and_answers_the_library_in_json(tmp_path,monkeypatch):
    import threading
    import embroiderly.subject_model as model
    release=threading.Event();started=threading.Event()
    def slow(image):
        started.set();release.wait(20)
    monkeypatch.setattr(model,'warm_image',slow)
    client=create_app(tmp_path).test_client()
    buf=BytesIO();Image.new('RGB',(40,30),'white').save(buf,format='PNG');buf.seek(0)
    import time
    try:
        began=time.monotonic()
        response=client.post('/upload',data={'image':(buf,'art.png')},headers={'Accept':'application/json'})
        assert time.monotonic()-began<10
        assert response.status_code==200 and response.json['url'].startswith('/prepare/')
        assert started.wait(5)
    finally:
        release.set()
    bad=client.post('/upload',data={'image':(BytesIO(b'not a picture'),'art.png')},headers={'Accept':'application/json'})
    assert bad.status_code==400 and 'could not be read' in bad.json['error']
    assert not any(p.suffix=='.png' and p.stat().st_size==13 for p in (tmp_path/'work/uploads').iterdir())
    kind=client.post('/upload',data={'image':(BytesIO(b'x'),'art.txt')},headers={'Accept':'application/json'})
    assert kind.status_code==400 and 'Supported formats' in kind.json['error']
    assert client.post('/upload',data={'image':(BytesIO(b'x'),'art.txt')}).status_code==400


def test_library_upload_ends_in_the_editor_or_an_error_with_try_again(tmp_path):
    script=create_app(tmp_path).test_client().get('/static/library.js').get_data(as_text=True)
    upload=script[script.index('let uploading=null'):script.index("window.addEventListener('pageshow'")]
    # Timed out, refused and failed uploads all reach the error path with a retry.
    assert 'AbortController' in upload and 'clearTimeout' in upload and "'Try again'" in upload
    assert "Accept:'application/json'" in upload and 'location.assign(data.url)' in upload
    assert "input.value=''" in upload and 'event.preventDefault()' in upload
