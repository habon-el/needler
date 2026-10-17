"""AI tool execution tests. Provider doubles are not live-model evidence."""
import copy
import json
import time
import threading

import numpy as np
import pytest

from embroiderly import ai_draft as draft
from embroiderly.web import create_app
from test_design_review import character, OPTIONS, hashes


PLAN = dict(action='select_subject', subject='Cartoon face', message='Keep the face.', width_mm=60,
            points=[dict(x=500, y=500, keep=True), dict(x=10, y=10, keep=False)], box=[80, 40, 930, 950])


def response(value):
    if 'summary' in value:
        value = {**dict(selection_status='acceptable', artwork_concerns=[], corrections=[]), **value}
    return dict(model=draft.MODEL, status='completed', usage=dict(input_tokens=100, output_tokens=20),
                output=[{'content': [{'type': 'output_text', 'text': json.dumps(value)}]}])


@pytest.fixture
def setup(tmp_path, monkeypatch):
    app = create_app(tmp_path)
    character(tmp_path/'work/uploads/art.png')
    calls, tools = [], []
    class Fake:
        def __init__(self, root, name, model):
            assert root == tmp_path and name == 'art.png' and model == draft.MODEL
        def request(self, payload):
            calls.append(payload)
            return response(copy.deepcopy(PLAN) if payload['text']['format']['name']=='subject_plan'
                            else dict(summary='Synthetic review.', concerns=[], artwork_concerns=['Inspect colour reduction.']))
    def segment(image, points, box, **kwargs):
        assert kwargs == {'border_background': False}
        tools.append((points, box))
        a = np.asarray(image)
        return np.any(a[:, :, :3] < 240, axis=2), dict(method='SAM2')
    monkeypatch.setattr(draft, 'BudgetedProvider', Fake)
    monkeypatch.setattr(draft, 'propose_mask', segment)
    return app.test_client(), tmp_path, calls, tools


def body(**kw):
    return dict(options=OPTIONS, question='Keep the face, remove background, 60 mm wide.', consent=True, **kw)


def finish(client, data):
    assert data.status_code in (200, 202), data.get_json()
    ident = data.get_json()['id']
    for _ in range(200):
        result = client.get('/ai-draft/art.png/'+ident).get_json()
        if result['state'] in draft.TERMINAL: return result
        time.sleep(.02)
    raise AssertionError(result)


def test_plan_executes_selection_then_reviews_without_writing(setup):
    client, root, calls, tools = setup
    before = hashes(root)
    result = finish(client, client.post('/ai-draft/art.png', json=body()))
    assert result['state'] == 'ready', result
    assert len(calls) == 2 and len(tools) == 1
    assert result['subject_width_mm'] == 60
    assert result['tools_used'] == ['select_subject', 'set_subject_width']
    assert set(result['patch']) == {'selection', 'mask_runs', 'hints', 'edge', 'height_mm'}
    assert result['review']['summary'] == 'Synthetic review.'
    assert hashes(root) == before
    assert sum(p['type']=='input_image' for p in calls[1]['input'][0]['content']) == 3
    assert all(p['store'] is False and 'tools' not in p for p in calls)
    again = finish(client, client.post('/ai-draft/art.png', json=body()))
    assert again['id'] == result['id'] and len(calls) == 2
    apply = client.post('/ai-draft/art.png/'+result['id'], json=body())
    assert apply.status_code == 200 and apply.get_json()['patch'] == result['patch']
    assert hashes(root) == before
    assert client.post('/ai-draft/art.png/'+result['id'], json={**body(), 'options': {**OPTIONS, 'height_mm': 50}}).status_code == 409


@pytest.mark.parametrize('override', [{'consent':False}, {'question':''}, {'question':'sk-proj-'+'a'*30}, {'options':None}])
def test_invalid_request_no_paid_calls(setup, override):
    client, _, calls, tools = setup
    assert client.post('/ai-draft/art.png', json={**body(), **override}).status_code == 400
    assert not calls and not tools


def test_native_origin_and_saved_lock_boundaries(setup):
    client, root, calls, _ = setup
    assert client.post('/ai-draft/art.png', json=body(), headers={'Origin':'https://bad.invalid'}).status_code == 403
    (root/'work/decisions/art.png.lettering.json').write_text('{}')
    assert client.post('/ai-draft/art.png', json=body()).status_code == 400
    assert not calls


@pytest.mark.parametrize('value', [dict(PLAN, width_mm=-1), dict(PLAN, width_mm=float('nan')),
    dict(PLAN, points=[]), dict(PLAN, box=[0,0,0,0]), dict(PLAN, box=[1,2,3])])
def test_invalid_geometry_not_executed(value, tmp_path):
    image = character(tmp_path/'c.png')
    with pytest.raises(ValueError): draft.arguments(value, image)


def test_unknown_actions_and_wrong_model_rejected():
    with pytest.raises(ValueError): draft.decoded(response(dict(PLAN, action='run_shell')), draft.PLAN)
    with pytest.raises(ValueError): draft.decoded({**response(PLAN), 'model':'other-model'}, draft.PLAN)
    with pytest.raises(ValueError): draft.decoded(response(dict(PLAN, patch={'count':2})), draft.PLAN)


def test_clarification_no_selection_or_review(setup, monkeypatch):
    client, _, calls, tools = setup
    class Clarify:
        def __init__(self, *a): pass
        def request(self, p):
            calls.append(p)
            return response(dict(PLAN, action='clarify', message='Which person should I keep?', points=[], box=[]))
    monkeypatch.setattr(draft, 'BudgetedProvider', Clarify)
    result = finish(client, client.post('/ai-draft/art.png', json=body()))
    assert result['state'] == 'question' and result['patch'] == {} and len(calls) == 1 and not tools


def test_cancel_prevents_second_call_and_apply(setup, monkeypatch):
    client, _, calls, tools = setup
    started, release = threading.Event(), threading.Event()
    class Slow:
        def __init__(self, *a): pass
        def request(self, p):
            calls.append(p); started.set(); release.wait(5); return response(PLAN)
    monkeypatch.setattr(draft, 'BudgetedProvider', Slow)
    start = client.post('/ai-draft/art.png', json=body()).get_json()
    assert started.wait(2)
    url = '/ai-draft/art.png/'+start['id']
    assert client.delete(url).get_json()['state'] == 'cancelled'
    release.set(); time.sleep(.1)
    assert len(calls) == 1 and not tools
    assert client.post(url, json=body()).status_code == 409


def test_review_failure_keeps_explicitly_unreviewed_draft(setup, monkeypatch):
    client, _, calls, _ = setup
    class FailReview:
        def __init__(self, *a): pass
        def request(self, p):
            calls.append(p)
            if len(calls)>1: raise RuntimeError('secret provider error')
            return response(PLAN)
    monkeypatch.setattr(draft, 'BudgetedProvider', FailReview)
    result = finish(client, client.post('/ai-draft/art.png', json=body()))
    assert result['state']=='ready' and result['review'] is None and 'secret' not in result['review_error']


def test_no_width_request_preserves_size(setup, monkeypatch):
    client, _, calls, _ = setup
    class NoWidth:
        def __init__(self, *a): pass
        def request(self, p):
            calls.append(p)
            return response(dict(PLAN, width_mm=None) if len(calls)==1 else dict(summary='Review', concerns=[]))
    monkeypatch.setattr(draft, 'BudgetedProvider', NoWidth)
    result = finish(client, client.post('/ai-draft/art.png', json=body()))
    assert result['state']=='ready' and 'height_mm' not in result['patch']


def test_saved_lock_is_authoritative_even_if_client_omits_it(setup):
    client, root, calls, _ = setup
    saved = root/'work/decisions/art.png.preparation.json'
    saved.write_text(json.dumps({**OPTIONS, 'piece_edits': {'a'*20: {'locked': True}}}))
    result = client.post('/ai-draft/art.png', json=body())
    assert result.status_code == 400 and 'locked' in result.get_json()['error']
    assert not calls


def test_lock_added_after_draft_blocks_approval(setup):
    client, root, calls, _ = setup
    result = finish(client, client.post('/ai-draft/art.png', json=body()))
    (root/'work/decisions/art.png.preparation.json').write_text(
        json.dumps({**OPTIONS, 'piece_edits': {'a'*20: {'locked': True}}}))
    assert client.post('/ai-draft/art.png/'+result['id'], json=body()).status_code == 409
    assert len(calls) == 2


@pytest.mark.parametrize('bad', [None, [], {'question': 'Keep face', 'options': None}])
def test_invalid_approval_is_conflict_not_server_error(setup, bad):
    client, _, _, _ = setup
    result = finish(client, client.post('/ai-draft/art.png', json=body()))
    assert client.post('/ai-draft/art.png/'+result['id'], json=bad).status_code == 409


def test_cancelled_before_execution_never_calls_provider(setup, monkeypatch):
    _, root, calls, _ = setup
    result = draft.run_draft(root, 'art.png', root/'work/uploads/art.png', OPTIONS, 'Keep face',
                             lambda *a: None, lambda: True)
    assert result is None and not calls


def test_real_local_segmentation_preserves_synthetic_face_features(setup, monkeypatch):
    from embroiderly.subject_model import propose_mask, unpack_mask
    from embroiderly.preparation import prepare
    client, root, calls, _ = setup
    monkeypatch.setattr(draft, 'propose_mask', propose_mask)
    monkeypatch.setenv('EMBROIDERLY_SAM2_LOCAL', '0')
    monkeypatch.delenv('EMBROIDERLY_SAM2_CHECKPOINT', raising=False)
    monkeypatch.delenv('EMBROIDERLY_SAM2_CONFIG', raising=False)
    before = hashes(root)
    result = finish(client, client.post('/ai-draft/art.png', json=body()))
    assert result['state'] == 'ready', result
    assert result['method'] == 'GrabCut fallback'
    mask = unpack_mask(result['patch']['mask_runs'], (160, 140))
    for x, y in [(60,20), (50,60), (90,60), (38,80), (102,80), (70,102)]:
        assert mask[y, x]  # hair, eyes, cheeks, mouth
    assert not mask[5,5] and not mask[150,130]
    artwork, _, report = prepare(root/'work/uploads/art.png', {**OPTIONS, **result['patch']})
    assert artwork.getpixel((5,5))[3] == 0
    assert artwork.getpixel((70,102))[:3] == (221,34,68)
    assert hashes(root) == before and len(calls) == 2


def test_crop_aware_fallback_retains_subject_touching_frame(monkeypatch):
    from PIL import Image, ImageDraw
    from embroiderly.subject_model import propose_mask
    monkeypatch.setenv('EMBROIDERLY_SAM2_LOCAL', '0')
    monkeypatch.delenv('EMBROIDERLY_SAM2_CHECKPOINT', raising=False)
    monkeypatch.delenv('EMBROIDERLY_SAM2_CONFIG', raising=False)
    im = Image.new('RGBA', (100,100), 'wheat')
    ImageDraw.Draw(im).rectangle((30,0,70,99), fill='#222222')
    points = [{'point':[50,50],'label':1}, {'point':[10,50],'label':0}, {'point':[90,50],'label':0}]
    old, _ = propose_mask(im, points, [20,0,80,99])
    fixed, _ = propose_mask(im, points, [20,0,80,99], border_background=False)
    repeated, _ = propose_mask(im, points, [20,0,80,99], border_background=False)
    assert not old[0,50] and not old[99,50]  # reproduces the old border deletion
    assert fixed[0,50] and fixed[99,50] and not fixed[50,10]
    assert np.array_equal(fixed,repeated)


def test_review_images_make_transparency_explicit():
    from PIL import Image
    im = Image.new('RGBA', (32,32), (0,0,0,0))
    im.putpixel((2,2),(0,0,0,255))
    before = im.tobytes()
    view = draft.review_image(im)
    assert view.mode == 'RGB' and view.getpixel((2,2)) == (0,0,0)
    assert view.getpixel((0,0)) == (245,245,245)
    assert view.getpixel((20,0)) == (205,205,205)
    assert im.tobytes() == before


@pytest.mark.parametrize('mode', ['corrected', 'limit', 'artwork_only', 'budget', 'contradictory'])
def test_bounded_correction_and_stage_separation(setup, monkeypatch, mode):
    client, root, calls, tools = setup
    original = hashes(root)
    class Model:
        def __init__(self,*a): pass
        def request(self,p):
            calls.append(p)
            if len(calls)==1: return response(PLAN)
            if mode=='budget' and len(calls)==3: raise draft.BudgetError('Design budget reached.')
            if mode=='artwork_only':
                return response(dict(summary='Cutout okay; mouth changed in artwork.', concerns=[],
                    artwork_concerns=['Mouth colour lost.']))
            if mode=='contradictory':
                return response(dict(summary='Inspect', concerns=['Hair missing.']))
            okay = mode=='corrected' and len(calls)==3
            return response(dict(summary='Inspect selection', concerns=[] if okay else ['Background remains.'],
                selection_status='acceptable' if okay else 'revise',
                corrections=[] if okay else [dict(x=100*len(calls), y=100, keep=False)]))
    def segment(im, points, box, **kw):
        tools.append(points)
        mask = np.any(np.asarray(im)[:,:,:3] < 240, axis=2)
        mask[10:10+len(tools),70] = False
        return mask, dict(method='GrabCut fallback')
    monkeypatch.setattr(draft,'BudgetedProvider',Model)
    monkeypatch.setattr(draft,'propose_mask',segment)
    result = finish(client, client.post('/ai-draft/art.png',json=body()))
    assert result['state']=='ready' and hashes(root)==original
    expected = {'corrected':3,'limit':4,'artwork_only':2,'budget':3,'contradictory':2}[mode]
    assert len(calls)==expected
    if mode=='corrected': assert result['selection_review']=='acceptable' and result['correction_rounds']==1
    if mode=='limit': assert result['selection_review']=='revise' and result['correction_rounds']==2
    if mode=='artwork_only': assert len(tools)==1 and result['review']['artwork_concerns']==['Mouth colour lost.']
    if mode=='budget': assert result['selection_review']=='unreviewed' and result['review'] is None and 'budget' in result['review_error']
    if mode=='contradictory': assert result['selection_review']=='uncertain'


def test_invalid_options_validated_in_worker_before_paid_request(setup):
    client, _, calls, tools = setup
    result = finish(client, client.post('/ai-draft/art.png',json={**body(),'options':{**OPTIONS,'count':999}}))
    assert result['state']=='failed' and not calls and not tools
