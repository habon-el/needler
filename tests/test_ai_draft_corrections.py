import numpy as np
from embroiderly import ai_draft as draft
from test_ai_draft import setup, body, finish, response, PLAN


def test_unchanged_correction_does_not_bill_for_same_review(setup, monkeypatch):
    client, _, calls, tools = setup
    class Model:
        def __init__(self,*args): pass
        def request(self,payload):
            calls.append(payload)
            if len(calls)==1: return response(PLAN)
            return response(dict(summary='Background remains.', concerns=['Background remains.'],
                selection_status='revise', corrections=[dict(x=200,y=100,keep=False)]))
    monkeypatch.setattr(draft,'BudgetedProvider',Model)
    result=finish(client,client.post('/ai-draft/art.png',json=body()))
    assert result['state']=='ready' and len(calls)==2 and len(tools)==2
    assert result['selection_review']=='revise'
    assert result['review_history'][-1]['unchanged'] is True


def test_ai_cannot_clear_unmet_keep_remove_hints(setup, monkeypatch):
    client, _, _, _ = setup
    monkeypatch.setattr(draft,'propose_mask',lambda im,*a,**kw:
        (np.any(np.asarray(im)[:,:,:3]<240,axis=2), dict(method='SAM2',prompt_conflicts=1)))
    result=finish(client,client.post('/ai-draft/art.png',json=body()))
    assert result['state']=='ready' and result['selection_review']=='uncertain'
    assert result['prompt_conflicts']==1
    assert 'hints' in result['review']['concerns'][0]
