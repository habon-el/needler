import json
import time

import numpy as np
from PIL import Image, ImageDraw

from embroiderly.auto_digitize import adjust, assess, classify, parse_request, plan, score, size_fit
from embroiderly.web import create_app


def badge(size=(400, 300)):
    image = Image.new('RGB', size, 'white')
    draw = ImageDraw.Draw(image)
    draw.ellipse((80, 30, 320, 270), fill='#1d4f91')
    draw.ellipse((115, 65, 285, 235), fill='#f3e6d2')
    draw.polygon([(200, 85), (225, 150), (290, 150), (238, 190), (258, 250), (200, 212), (142, 250), (162, 190), (110, 150), (175, 150)], fill='#e09a1f')
    return image


def test_classify_picks_line_art_ink_logo_and_photo():
    lines = Image.new('RGB', (300, 300), 'black')
    ImageDraw.Draw(lines).line([(20, 20), (280, 200), (40, 280)], fill='white', width=4)
    assert classify(lines)[0] == 'line_art'
    ink = Image.new('RGB', (300, 300), 'white')
    ImageDraw.Draw(ink).line([(20, 20), (280, 200), (40, 280)], fill='black', width=4)
    assert classify(ink)[0] == 'ink'
    kind, facts = classify(badge())
    assert kind == 'logo' and facts['background'] and facts['thread_colours'] == 3
    noise = Image.fromarray(np.random.default_rng(1).integers(0, 255, (200, 200, 3), dtype=np.uint8))
    assert classify(noise)[0] == 'photo'


def test_request_parser_reads_sizes_colours_and_kind():
    assert parse_request('cap front, 6 cm wide, 3 colours') == {'width_mm': 60.0, 'colours': 3, 'fabric': 'cap'}
    assert parse_request('2.5 inch tall line art') == {'height_mm': 63.5, 'kind': 'line_art'}
    assert parse_request('80mm high logo') == {'height_mm': 80.0, 'kind': 'logo'}
    assert parse_request('') == {} and parse_request('9000 mm wide') == {}


def test_plan_keeps_saved_choices_and_converts_width():
    options = plan('logo', {'thread_colours': 3}, {'width_mm': 60}, (400, 300), {'fabric': 'x', 'ink_only': True})
    assert options['fabric'] == 'x' and options['ink_only'] is False and options['count'] == 3
    assert options['height_mm'] == 45.0


def test_rules_retry_cuts_and_fit_size():
    many = dict(stitches=1000, trims=40)
    assert [i['kind'] for i in assess(many)] == ['cuts'] and not assess(dict(stitches=5000, trims=9))
    nxt, kind, why = adjust({'count': 4}, 'logo', assess(many), 1)
    assert kind == 'logo' and nxt['count'] == 3 and nxt['floor_mm2'] >= 2.5 and 'colours' in why
    nxt, kind, _ = adjust({}, 'line_art', assess(many), 1)
    assert kind == 'line_art' and nxt['line_retrace_mm'] == 12
    assert adjust({'line_retrace_mm': 24}, 'line_art', assess(many), 3) is None
    nxt, kind, _ = adjust({}, 'line_art', [dict(kind='error', text='No drawn lines were found.')], 1)
    assert kind == 'logo' and nxt['line_art'] is False
    fitted, label = size_fit({'width_mm': 60}, {'width_mm': 37.5, 'height_mm': 37.5}, {'height_mm': 45})
    assert fitted['height_mm'] == 72.0 and label == '60 mm width'
    assert size_fit({'width_mm': 60}, {'width_mm': 59.5}, {'height_mm': 45}) is None
    assert score(dict(stitches=1000, trims=5, width_mm=40), {'width_mm': 60}) > score(dict(stitches=1000, trims=5, width_mm=60), {'width_mm': 60})


def test_route_runs_attempts_and_reaches_requested_size(tmp_path):
    app = create_app(tmp_path)
    badge().save(tmp_path / 'work/uploads/badge.png')
    client = app.test_client()
    assert client.post('/api/auto-digitize/badge.png', json={'request': '50 mm wide'}).status_code == 202
    for _ in range(240):
        job = client.get('/api/auto-digitize/badge.png').get_json()
        if job['state'] != 'running':
            break
        time.sleep(.5)
    assert job['state'] == 'done', job
    result = job['result']
    assert result['ok'] and result['stitches'] > 500 and abs(result['width_mm'] - 50) <= 1.5
    assert any('Looked at the picture' in s['text'] for s in job['steps'])
    saved = json.loads((tmp_path / 'work/decisions/badge.png.preparation.json').read_text())
    assert saved['count'] == 3
    assert (tmp_path / 'work/decisions/badge.png.auto.json').is_file()
    assert client.post('/api/auto-digitize/missing.png', json={}).status_code == 404


class _Usage:
    input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens = 3000, 400, 0, 0


class _Block:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _FakeClaude:
    """Stands in for the Anthropic client: one make_stitches call, then finish."""
    def __init__(self):
        self.calls, self.beta = [], self
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        if len(self.calls) == 1:
            content = [_Block(type='tool_use', id='a', name='make_stitches',
                              input={'note': 'Flat badge: three colours.', 'mode': 'colour', 'colours': 3, 'height_mm': 40})]
            return _Block(stop_reason='tool_use', content=content, usage=_Usage())
        content = [_Block(type='tool_use', id='b', name='finish',
                          input={'attempt': 1, 'summary': 'A clean three-colour badge.', 'check': ['Small letters']})]
        return _Block(stop_reason='tool_use', content=content, usage=_Usage())


def _wait(client, name):
    for _ in range(240):
        job = client.get('/api/auto-digitize/' + name).get_json()
        if job['state'] != 'running':
            return job
        time.sleep(.5)
    return job


def test_claude_path_uses_tools_records_spend_and_keeps_its_choice(tmp_path, monkeypatch):
    import anthropic
    fake = _FakeClaude()
    monkeypatch.setattr(anthropic, 'Anthropic', lambda **kw: fake)
    app = create_app(tmp_path)
    badge().save(tmp_path / 'work/uploads/badge.png')
    client = app.test_client()
    assert client.post('/api/auto-digitize/badge.png', json={'use_claude': True}).status_code == 202
    job = _wait(client, 'badge.png')
    assert job['state'] == 'done', job
    assert job['result']['summary'] == 'A clean three-colour badge.' and job['result']['check'] == ['Small letters']
    assert any(s['text'].startswith('Claude: Flat badge') for s in job['steps'])
    # The tool result carried numbers and a drawing of the stitches back to Claude.
    reply = fake.calls[1]['messages'][2]['content'][0]
    assert reply['type'] == 'tool_result' and [c['type'] for c in reply['content']] == ['text', 'image']
    assert fake.calls[0]['model'] == 'claude-opus-5-5' and fake.calls[0]['fallbacks'] == 'default'
    # The tools sent carry Needler's own lists (test_claude_tools.py checks them in full).
    offered = fake.calls[0]['tools'][0]['input_schema']['properties']
    assert 'leather' in offered['fabric']['enum'] and 'blanket' in offered['border']['properties']['style']['enum']
    spent = json.loads((tmp_path / 'work/decisions/claude-spend.json').read_text())['usd']
    assert 0 < spent < .1 and job['result']['claude_usd'] == round(spent, 4)
    assert 'ANTHROPIC' not in json.dumps(job)


def test_claude_failure_falls_back_to_rules(tmp_path, monkeypatch):
    import anthropic

    def broken(**kw):
        raise RuntimeError('no network')
    monkeypatch.setattr(anthropic, 'Anthropic', broken)
    app = create_app(tmp_path)
    badge().save(tmp_path / 'work/uploads/badge.png')
    client = app.test_client()
    client.post('/api/auto-digitize/badge.png', json={'use_claude': True})
    job = _wait(client, 'badge.png')
    assert job['state'] == 'done' and any('built-in rules' in s['text'] for s in job['steps'])
