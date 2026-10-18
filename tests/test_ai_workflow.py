"""Automatic reviews: explicit synthetic providers, no paid calls or image edits."""
import copy
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from PIL import Image

from embroiderly import ai_workflow as workflow
from embroiderly.web import create_app

OPTIONS = dict(count=2, smooth=0, floor_mm2=0, mask_holes_mm2=0,
               protect_selection=True, height_mm=20)
RESULT = dict(summary='Synthetic review: which details should stay?', details=[dict(
    label='Eye', note='Check this detail.', bounds=[100, 100, 300, 300], certainty='uncertain')])


def response(value=RESULT):
    return dict(status='completed', model=workflow.MODEL, usage={'input_tokens':100,'output_tokens':25},
                output=[dict(content=[dict(type='output_text', text=json.dumps(value))])])


@pytest.fixture
def setup(tmp_path, monkeypatch):
    app = create_app(tmp_path)
    image = Image.new('RGBA', (100, 100), 'black')
    image.save(tmp_path/'work/uploads/test.png')
    calls = []
    class Fake:
        def __init__(self, root, name, model):
            assert name == 'test.png' and model == workflow.MODEL
        def request(self, payload):
            calls.append(payload)
            return response()
    monkeypatch.setattr(workflow, 'BudgetedProvider', Fake)
    return app, tmp_path, calls


def post(app, stage='upload', **extra):
    return app.test_client().post('/ai-workflow/test.png', json=dict(
        consent=True, stage=stage, options=OPTIONS, **extra))


def test_no_request_without_explicit_consent_or_valid_stage(setup):
    app, _, calls = setup
    for body in ({}, {'consent':False}, {'consent':True, 'stage':'other', 'options':{}}, []):
        assert app.test_client().post('/ai-workflow/test.png', json=body).status_code == 400
    assert app.test_client().post('/ai-workflow/test.png', json={}, headers={'Origin':'https://bad.invalid'}).status_code == 403
    assert calls == []


def test_readiness_uses_existing_budget_gate(setup, monkeypatch):
    app, _, calls = setup
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    assert app.test_client().get('/ai-workflow/test.png').get_json()['available'] is False
    assert calls == []


def test_cached_across_reload_and_server_restart(setup):
    app, root, calls = setup
    before = (root/'work/uploads/test.png').read_bytes()
    first = post(app)
    assert first.status_code == 200, first.get_json()
    assert first.get_json()['cached'] is False
    assert first.get_json()['details'][0]['bounds'] == [10, 10, 30, 30]
    assert first.get_json()['operations'] == []
    assert post(app).get_json()['cached'] is True
    assert post(create_app(root)).get_json()['cached'] is True
    assert len(calls) == 1
    assert calls[0]['store'] is False and not calls[0].get('tools')
    assert calls[0]['text']['format']['strict'] is True
    assert (root/'work/uploads/test.png').read_bytes() == before
    assert not list((root/'work/decisions').iterdir())


def test_finished_without_current_saved_plan_makes_no_call(setup):
    app, _, calls = setup
    result = post(app, 'finished')
    assert result.status_code == 400 and 'current stitches' in result.get_json()['error']
    assert not calls


def test_native_letters_never_sent_to_picture_review(setup):
    app, root, calls = setup
    (root/'work/decisions/test.png.lettering.json').write_text('{}')
    assert post(app).status_code == 400
    assert not calls


def test_final_review_contains_saved_stitch_render_and_new_plan_invalidates_cache(setup, monkeypatch):
    app, _, calls = setup
    plan = dict(stitch_count=2, trim_count=0, marker=1)
    monkeypatch.setattr(workflow, 'matching_plan', lambda *a: {'playback':plan})
    rendered = []
    def render(p, **kwargs):
        rendered.append(copy.deepcopy(p))
        return Image.new('RGB', (40, 40), 'red')
    monkeypatch.setattr(workflow, 'render_finished', render)
    assert post(app, 'finished').status_code == 200
    assert len([i for i in calls[0]['input'][0]['content'] if i['type']=='input_image']) == 3
    assert rendered[0] == plan
    assert post(app, 'finished').get_json()['cached'] is True
    plan['marker'] = 2
    assert post(app, 'finished').get_json()['cached'] is False
    assert len(calls) == 2


@pytest.mark.parametrize('change', ['bad_bounds','extra','wrong_model','refused'])
def test_invalid_model_reply_cannot_edit_or_look_successful(setup, monkeypatch, change):
    app, _, calls = setup
    value = copy.deepcopy(RESULT)
    if change == 'bad_bounds': value['details'][0]['bounds'] = [500, 200, 100, 300]
    if change == 'extra': value['execute'] = 'erase'
    body = response(value)
    if change == 'wrong_model': body['model'] = 'unexpected-model'
    if change == 'refused': body['output'][0]['content'] = [{'type':'refusal','refusal':'No'}]
    class Fake:
        def __init__(self,*a): pass
        def request(self,p): calls.append(p); return body
    monkeypatch.setattr(workflow, 'BudgetedProvider', Fake)
    assert post(app).status_code == 400
    assert post(app).status_code == 409
    assert len(calls) == 1


def test_failure_only_retries_when_user_requests_it(setup, monkeypatch):
    app, _, calls = setup
    class Fake:
        def __init__(self,*a): pass
        def request(self,p): calls.append(p); raise TimeoutError('Do not expose provider details')
    monkeypatch.setattr(workflow, 'BudgetedProvider', Fake)
    assert post(app).status_code == 503
    assert post(app).status_code == 409
    assert len(calls) == 1
    assert post(app, retry=True).status_code == 503
    assert len(calls) == 2


def test_concurrent_tabs_do_not_repeat_paid_call(setup, monkeypatch):
    app, _, calls = setup
    started, finish = threading.Event(), threading.Event()
    class Fake:
        def __init__(self,*a): pass
        def request(self,p):
            calls.append(p); started.set(); assert finish.wait(15)
            return response()
    monkeypatch.setattr(workflow, 'BudgetedProvider', Fake)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(post, app)
        assert started.wait(10)
        second = post(app)
        finish.set()
        assert second.status_code == 202
        assert first.result().status_code == 200
    assert len(calls) == 1
    assert post(app).get_json()['cached'] is True
