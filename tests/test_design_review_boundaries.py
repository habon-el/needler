"""Read-only boundary regressions independent of the provider's real API."""
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

from embroiderly import design_review as review
from embroiderly.web import create_app
from test_design_review import character, OPTIONS, altered, response


def test_no_candidates_never_calls_model(tmp_path, monkeypatch):
    app=create_app(tmp_path);character(tmp_path/'work/uploads/art.png')
    def forbidden(*args): raise AssertionError('No reason to spend')
    monkeypatch.setattr(review,'BudgetedProvider',forbidden)
    client=app.test_client()
    snapshot=client.post('/design-review/art.png',json={'options':OPTIONS}).get_json()['snapshot']
    result=client.post('/design-review/art.png',json=dict(options=OPTIONS,mode='ai',consent=True,snapshot=snapshot))
    assert result.status_code==200 and result.get_json()['ai']['status']=='not_needed'


def test_failed_provider_not_cached_and_no_settings_saved(tmp_path, monkeypatch):
    app=create_app(tmp_path);character(tmp_path/'work/uploads/art.png');calls=[]
    class Fake:
        def __init__(self,*args): pass
        def request(self,payload): calls.append(1);raise TimeoutError('secret provider text must not leak')
    monkeypatch.setattr(review,'BudgetedProvider',Fake)
    client=app.test_client();snap=client.post('/design-review/art.png',json={'options':altered()}).get_json()['snapshot']
    for _ in range(2):
        result=client.post('/design-review/art.png',json=dict(options=altered(),mode='ai',consent=True,snapshot=snap))
        assert result.status_code==503 and 'secret' not in result.get_data(as_text=True)
    assert len(calls)==2
    assert not list((tmp_path/'work/decisions').glob('*.preparation.json'))


def test_review_works_on_locked_design_without_changing_locks(tmp_path):
    from test_piece_routes import setup
    client, options, key, preview = setup(tmp_path)
    locked = client.post('/artwork/p.png', json=dict(
        options=options, piece_revision=preview['piece_revision'],
        piece_command=dict(ids=[key], field='locked', value=True)))
    assert locked.status_code == 200
    settings = locked.get_json()['options']
    saved = tmp_path/'work/decisions/p.png.preparation.json'
    before = saved.read_bytes()
    result = client.post('/design-review/p.png', json={'options': settings})
    assert result.status_code == 200, result.get_json()
    assert saved.read_bytes() == before


def test_review_does_not_hold_edit_lock_during_network(tmp_path,monkeypatch):
    app=create_app(tmp_path);character(tmp_path/'work/uploads/art.png')
    client=app.test_client();snap=client.post('/design-review/art.png',json={'options':altered()}).get_json()['snapshot']
    started,finish=threading.Event(),threading.Event()
    class Fake:
        def __init__(self,*a): pass
        def request(self,payload):
            started.set();assert finish.wait(20);return response([])
    monkeypatch.setattr(review,'BudgetedProvider',Fake)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending=pool.submit(lambda:app.test_client().post('/design-review/art.png',json=dict(options=altered(),mode='ai',consent=True,snapshot=snap)))
        assert started.wait(10)
        try:
            edit=pool.submit(lambda:app.test_client().post('/artwork/art.png',json={'options':OPTIONS}))
            assert edit.result(timeout=10).status_code==200
        finally:finish.set()
        assert pending.result().status_code==200


def test_region_limit_is_honest_and_no_alignment_guess():
    source=Image.new('RGBA',(100,100),'white');output=source.copy()
    for y in range(10):
        for x in range(10):output.putpixel((x*9,y*9),(0,0,0,255))
    result=review.comparison(source,output,100,{})
    assert result['total_regions']==100 and result['shown_regions']==50
    assert result['changed_pixels']==100
    import pytest
    with pytest.raises(ValueError,match='not aligned'):
        review.comparison(source,output.resize((50,50)),100,{})
