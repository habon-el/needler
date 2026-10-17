"""Fidelity review: no live API calls; explicit fake AI responses are labelled."""
import copy
import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image, ImageDraw
import pytest

from embroiderly import design_review as review
from embroiderly.web import create_app


def character(path):
    image = Image.new('RGBA', (140, 160), '#ffffff')
    draw = ImageDraw.Draw(image)
    draw.ellipse((15, 10, 125, 145), fill='#604030')
    draw.ellipse((25, 35, 115, 120), fill='#ffccaa')
    for x in (47, 87):
        draw.ellipse((x, 55, x+7, 64), fill='#101010')
    for x in (33, 97):
        draw.ellipse((x, 76, x+11, 87), fill='#ff8899')
    draw.ellipse((55, 90, 85, 110), fill='#101010')
    draw.rectangle((63, 100, 77, 105), fill='#dd2244')
    image.save(path)
    return image


OPTIONS = dict(count=6, smooth=0, floor_mm2=0, mask_holes_mm2=0,
               protect_selection=True, height_mm=80)


@pytest.fixture
def setup(tmp_path):
    app = create_app(tmp_path)
    path = tmp_path/'work/uploads/character.png'
    character(path)
    return app, path


def altered():
    return {**OPTIONS, 'merges': {'#ff8899': '#ffccaa', '#dd2244': '#101010'}}


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def response(findings):
    return {'status': 'completed', 'output': [{'content': [
        {'type': 'output_text', 'text': json.dumps({'findings': findings})}]}]}


def fake_observation(result):
    return {'region_id': result['regions'][0]['id'], 'detail': 'Possible lost cheek',
            'observation': 'Synthetic test response: compare this colour change.', 'certainty': 'possible'}


def test_local_missing_cheeks_and_mouth_without_writes_or_network(setup, monkeypatch):
    app, path = setup
    monkeypatch.setattr(review, 'BudgetedProvider', lambda *a: pytest.fail('Local must not initialise AI'))
    before = hashes(path.parents[2])
    result = app.test_client().post('/design-review/character.png', json={'options': altered()})
    assert result.status_code == 200
    data = result.get_json()
    assert data['total_regions'] == 3
    assert data['changed_pixels'] > 0 and data['removed_pixels'] == 0
    assert data['operations'] == [] and data['advisory_only'] is True
    assert data['stages_checked'] == ['subject_to_artwork']
    assert data['ai']['status'] == 'not_requested'
    assert {r['bounds'][0] for r in data['regions']} == {33, 63, 97}
    assert hashes(path.parents[2]) == before
    again = app.test_client().post('/design-review/character.png', json={'options': altered()}).get_json()
    assert again == data


def test_unchanged_artwork_not_flagged(setup):
    app, _ = setup
    data = app.test_client().post('/design-review/character.png', json={'options': OPTIONS}).get_json()
    assert data['total_regions'] == data['changed_pixels'] == 0


def test_selection_excludes_unselected_pixels_and_tiny_regions_count():
    source = Image.new('RGBA', (20, 20), (0, 0, 0, 0))
    source.putpixel((5, 5), (255, 0, 0, 255))
    after = Image.new('RGBA', source.size, 'blue')
    result = review.comparison(source, after, 20, {})
    assert result['changed_pixels'] == 1
    assert result['regions'][0]['width_mm'] == 1
    assert result['total_regions'] == 1


def test_lost_alpha_detected_even_same_rgb():
    source = Image.new('RGBA', (10, 10), 'red')
    after = source.copy(); after.putpixel((2, 3), (255, 0, 0, 0))
    result = review.comparison(source, after, 10, {})
    assert result['removed_pixels'] == 1
    assert result['regions'][0]['bounds'] == [2, 3, 3, 4]


def test_explicit_erase_and_paint_are_not_loss(setup):
    app, _ = setup
    edits = [dict(kind='erase', points=[[3, 3]], radius=2),
             dict(kind='paint', points=[[70, 135]], radius=3, colour='#101010')]
    data = app.test_client().post('/design-review/character.png', json={'options': {**OPTIONS, 'edits': edits}}).get_json()
    assert data['total_regions'] == 0


def test_caps_consent_and_stale_snapshot_gate_before_paid_adapter(setup, monkeypatch):
    app, _ = setup
    monkeypatch.setattr(review, 'BudgetedProvider', lambda *a: pytest.fail('Must not reach provider'))
    client = app.test_client()
    assert client.get('/design-review/character.png').get_json()['ai_available'] is False
    assert client.post('/design-review/character.png', json={'options': altered(), 'mode': 'ai'}).status_code == 400
    assert client.post('/design-review/character.png', json={'options': altered(), 'mode': 'ai', 'consent': True, 'snapshot': 'old'}).status_code == 409
    assert client.post('/design-review/character.png', json={'options': OPTIONS}, headers={'Origin': 'https://external.invalid'}).status_code == 403


def test_missing_budget_preserves_local_result(setup, monkeypatch):
    app, _ = setup
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    client = app.test_client()
    data = client.post('/design-review/character.png', json={'options': altered()}).get_json()
    result = client.post('/design-review/character.png', json={'options': altered(), 'mode': 'ai', 'consent': True, 'snapshot': data['snapshot']})
    assert result.status_code == 503
    assert result.get_json()['total_regions'] == 3
    assert result.get_json()['ai']['status'] == 'unavailable'


def test_ai_cached_per_snapshot_model_and_design(setup, monkeypatch):
    app, path = setup
    client = app.test_client(); calls = []
    data = client.post('/design-review/character.png', json={'options': altered()}).get_json()
    class Fake:
        def __init__(self, root, name, model):
            assert model == review.MODEL
            calls.append(name)
        def request(self, payload):
            assert payload['store'] is False and 'tools' not in payload
            assert payload['text']['format']['strict'] is True
            return response([fake_observation(data)])
    monkeypatch.setattr(review, 'BudgetedProvider', Fake)
    def run(options, name='character.png'):
        local = client.post('/design-review/'+name, json={'options': options}).get_json()
        return client.post('/design-review/'+name, json={'options': options, 'mode': 'ai', 'consent': True, 'snapshot': local['snapshot']}).get_json()
    before = hashes(path.parents[2])
    assert run(altered())['ai']['cached'] is False
    assert run(altered())['ai']['cached'] is True
    assert len(calls) == 1
    assert run({**altered(), 'height_mm': 70})['ai']['cached'] is False
    path.with_name('second.png').write_bytes(path.read_bytes())
    run(altered(), 'second.png')
    assert calls == ['character.png', 'character.png', 'second.png']
    assert all(hashes(path.parents[2])[key] == value for key, value in before.items())


@pytest.mark.parametrize('change', ['foreign', 'extra', 'duplicate', 'incomplete', 'refusal', 'too_long'])
def test_bad_ai_output_rejected(setup, change):
    _, path = setup
    _, _, data = review.snapshot(path, altered())
    item = fake_observation(data); body = response([item])
    if change == 'foreign': item['region_id'] = 'foreign'
    if change == 'extra': item['execute'] = 'erase'
    if change == 'too_long': item['detail'] = 'x'*161
    if change == 'duplicate': body = response([item, item])
    elif change == 'incomplete': body['status'] = 'incomplete'
    elif change == 'refusal': body['output'][0]['content'].append({'type': 'refusal'})
    else: body = response([item])
    with pytest.raises(ValueError): review.observations(body, data)


def test_inflight_duplicate_does_not_send_twice(setup, monkeypatch):
    app, _ = setup
    data = app.test_client().post('/design-review/character.png', json={'options': altered()}).get_json()
    started, finish = threading.Event(), threading.Event()
    class Fake:
        def __init__(self, *a): pass
        def request(self, payload):
            started.set(); assert finish.wait(60)
            return response([])
    monkeypatch.setattr(review, 'BudgetedProvider', Fake)
    body = dict(options=altered(), mode='ai', consent=True, snapshot=data['snapshot'])
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(lambda: app.test_client().post('/design-review/character.png', json=body))
        assert started.wait(10)
        second = app.test_client().post('/design-review/character.png', json=body)
        finish.set()
        assert first.result().status_code == 200
        assert second.status_code == 409


def test_transformed_and_native_projects_not_raster_reviewed(setup):
    app, path = setup
    (path.parents[1]/'decisions/character.png.lettering.json').write_text('{}')
    result = app.test_client().post('/design-review/character.png', json={'options': OPTIONS})
    assert result.status_code == 400 and 'native text' in result.get_json()['error']
    with pytest.raises(ValueError, match='not ready'):
        review.snapshot(path, {**OPTIONS, 'refinement_ops': [{}]})
