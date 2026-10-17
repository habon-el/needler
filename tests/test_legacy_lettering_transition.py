"""Old text remains intact; never quietly digitize its PNG as small text."""
import json
from PIL import Image
from embroiderly.web import create_app


def test_old_typed_text_offers_rebuild_without_changing_image(tmp_path, monkeypatch):
    app=create_app(tmp_path);c=app.test_client()
    path=tmp_path/'work/uploads/lettering-legacy.png'
    Image.new('RGBA',(30,30),'black').save(path)
    saved=tmp_path/'work/decisions'/('lettering-legacy.png.lettering.json')
    saved.write_text(json.dumps(dict(text='Hello',font='keep-this-font')))
    before=path.read_bytes(),saved.read_bytes()
    from embroiderly import engine
    def not_raster(*a,**kw):raise AssertionError('Raster engine reached for typed words')
    monkeypatch.setattr(engine,'digitize',not_raster)
    r=c.post('/artwork/lettering-legacy.png',json={'options':{},'digitize':True,'subject_confirmed':True})
    assert r.status_code==400
    assert 'choose an embroidery font' in r.json['error']
    assert before==(path.read_bytes(),saved.read_bytes())


def test_old_native_bookmark_goes_to_text_workspace_not_underlying_image(tmp_path):
    c=create_app(tmp_path).test_client()
    key='a'*64
    r=c.get('/artwork/missing-original.png?native_text='+key)
    assert r.status_code==302
    assert r.headers['Location']=='/text/'+key
