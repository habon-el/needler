import pyembroidery as emb
from flask import Flask
from embroiderly import lettering_trial as module


def client():
    app=Flask(__name__);module.register(app)
    return app.test_client()


def test_trial_refuses_bad_input_and_does_not_claim_release(monkeypatch):
    c=client()
    assert c.post('/lettering/small-trial',json={}).status_code==400
    monkeypatch.setattr(module,'trial',lambda body: {'release_approved':False,'pending':['Density']})
    result=c.post('/lettering/small-trial',json={'text':'Hello','font':'small_font','height_mm':4})
    assert result.status_code==200 and result.json['release_approved'] is False
    assert 'url' not in result.json


def test_trial_busy_and_recoverable_failure(monkeypatch):
    c=client();body={'text':'Hello','font':'small_font','height_mm':4}
    module.BUSY.acquire()
    try:assert c.post('/lettering/small-trial',json=body).status_code==409
    finally:module.BUSY.release()
    def fail(body):raise ValueError('bad generator')
    monkeypatch.setattr(module,'trial',fail)
    assert c.post('/lettering/small-trial',json=body).status_code==422
    assert not module.BUSY.locked()


def test_measure_counts_short_and_excludes_travel_from_preview():
    p=emb.EmbPattern();p.stitches=[[10,10,emb.JUMP],[10,10,0],[12,10,0],
        [12,10,emb.TRIM],[50,10,emb.JUMP],[50,10,0],[55,10,0]]
    result,bounds,spans=module.measure(p)
    assert result['short']==1 and result['long']==0
    assert result['stitches']==4 and len(spans)==2
    assert result['width_mm']==4.5
