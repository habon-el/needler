"""No real network or real model prices: exercise the spending gate itself."""
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import pytest
from embroiderly.provider_budget import BudgetError, BudgetLedger, BudgetedProvider, money


def policy(root, design='0.002', month='0.003'):
    path=root/'work'/'provider-budget.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    data={'per_design_usd':design,'per_month_usd':month,'models':{'test-only':{
        'verified_by_user':True,'source_note':'Synthetic test pricing, not a real model',
        'valid_until':'2099-01-01','input_usd_per_million':'1','output_usd_per_million':'1'}}}
    path.write_text(json.dumps(data))
    return path,data


@pytest.mark.parametrize('missing',['per_design_usd','per_month_usd'])
def test_both_caps_required_before_adapter_initializes(tmp_path,missing):
    path,data=policy(tmp_path);del data[missing];path.write_text(json.dumps(data))
    with pytest.raises(BudgetError):BudgetedProvider(tmp_path,'design','test-only')
    assert not (tmp_path/'work'/'provider-spend.sqlite3').exists()


@pytest.mark.parametrize('value',[None,0,-1,'NaN','Infinity',True])
def test_invalid_money_rejected(value):
    with pytest.raises(BudgetError):money(value)


def test_unknown_unverified_expired_prices_fail_closed(tmp_path):
    path,data=policy(tmp_path)
    with pytest.raises(BudgetError):BudgetLedger(tmp_path,'unknown')
    data['models']['test-only']['verified_by_user']=False;path.write_text(json.dumps(data))
    with pytest.raises(BudgetError):BudgetLedger(tmp_path,'test-only')
    data['models']['test-only']['verified_by_user']=True
    data['models']['test-only']['valid_until']='2000-01-01';path.write_text(json.dumps(data))
    with pytest.raises(BudgetError):BudgetLedger(tmp_path,'test-only')


def test_atomic_design_and_month_limits(tmp_path):
    policy(tmp_path);ledger=BudgetLedger(tmp_path,'test-only')
    def reserve(_):
        try:ledger.reserve('same-design',500,500);return True
        except BudgetError:return False
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(reserve,range(8)))
    assert sum(results)==2
    ledger.reserve('second-design',500,500)
    with pytest.raises(BudgetError,match='monthly'):ledger.reserve('third-design',1,1)


def test_count_then_reserve_then_generate_and_retain_failed_reservation(tmp_path,monkeypatch):
    policy(tmp_path);monkeypatch.setenv('OPENAI_API_KEY','test-not-a-key')
    provider=BudgetedProvider(tmp_path,'design','test-only');calls=[]
    def fake(suffix,payload):
        calls.append(suffix)
        if suffix:return {'input_tokens':1000}
        with sqlite3.connect(provider.ledger.path) as db:
            assert db.execute('SELECT SUM(nanodollars) FROM reservations').fetchone()[0]==2_000_000
        assert payload['store'] is False and payload['service_tier']=='default'
        raise TimeoutError('Uncertain upstream result')
    monkeypatch.setattr(provider,'_post',fake)
    request={'model':'test-only','input':'test','max_output_tokens':1000}
    with pytest.raises(TimeoutError):provider.request(request)
    with pytest.raises(BudgetError,match='design'):provider.request(request)
    assert calls==['/input_tokens','','/input_tokens']


@pytest.mark.parametrize('count',[None,-1,True,'123'])
def test_no_estimation_fallback(tmp_path,monkeypatch,count):
    policy(tmp_path);monkeypatch.setenv('OPENAI_API_KEY','test-not-a-key')
    provider=BudgetedProvider(tmp_path,'design','test-only');calls=[]
    monkeypatch.setattr(provider,'_post',lambda suffix,payload:(calls.append(suffix) or {'input_tokens':count}))
    with pytest.raises(BudgetError):provider.request({'model':'test-only','input':'test','max_output_tokens':100})
    assert calls==['/input_tokens']


def test_legacy_and_photo_adapters_cannot_bypass_missing_caps(tmp_path,monkeypatch):
    from embroiderly.web import create_app
    from embroiderly.assistance import cloud_available
    from embroiderly.sewout_review import configured
    monkeypatch.setenv('OPENAI_API_KEY','test-not-a-key');monkeypatch.setenv('EMBROIDERLY_AI_MODEL','test-only')
    app=create_app(tmp_path)
    with app.test_request_context('/artwork/example.png') as ctx:
        ctx.request.view_args={'name':'example.png'}
        assert not cloud_available() and not configured()
