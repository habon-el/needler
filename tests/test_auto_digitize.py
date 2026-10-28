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


class _ScriptedClaude:
    """A fake Claude that plays a script: each turn is a tool input dict (name, input) or a stop reason."""
    def __init__(self, turns):
        self.turns, self.calls, self.beta = list(turns), [], self
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        turn = self.turns.pop(0) if self.turns else ('finish', {'attempt': 1, 'summary': 'Done.'})
        if isinstance(turn, str):
            return _Block(stop_reason=turn, content=[], usage=_Usage())
        name, data = turn
        return _Block(stop_reason='tool_use', usage=_Usage(),
                      content=[_Block(type='tool_use', id=f't{len(self.calls)}', name=name, input=data)])

    def replies(self):
        """What Needler sent back for each make_stitches call: (summary dict or error text)."""
        out = []
        for message in self.calls[-1]['messages']:
            if message['role'] != 'user' or not isinstance(message['content'], list):
                continue
            for block in message['content']:
                if isinstance(block, dict) and block.get('type') == 'tool_result' and block['content'] != 'Finished.':
                    content = block['content']
                    out.append(json.loads(content[0]['text']) if isinstance(content, list) else content)
        return out


def _run_claude(tmp_path, monkeypatch, fake, request='', spent=None):
    import anthropic
    monkeypatch.setattr(anthropic, 'Anthropic', lambda **kw: fake)
    app = create_app(tmp_path)
    badge().save(tmp_path / 'work/uploads/badge.png')
    if spent is not None:
        (tmp_path / 'work/decisions/claude-spend.json').write_text(json.dumps(dict(usd=spent)))
    client = app.test_client()
    assert client.post('/api/auto-digitize/badge.png', json={'use_claude': True, 'request': request}).status_code == 202
    return _wait(client, 'badge.png')


def test_scripted_claude_uses_the_new_controls_and_its_plan_reaches_the_person(tmp_path, monkeypatch):
    plan_rows = [dict(colour='#1d4f91', what='ring', style='automatic', why='a clean edge'),
                 dict(colour='#f3e6d2', what='centre', style='3D puff', why='you asked for it raised'),
                 dict(colour='#e09a1f', what='star', style='gradient fill', why='soft light')]
    fake = _ScriptedClaude([
        ('make_stitches', dict(note='Badge with a satin edge, as asked.', mode='colour', colours=3, height_mm=40,
                               plan=plan_rows, border=dict(style='satin', width_mm=2.5, line_inside=True),
                               colour_styles=[dict(colour='#f3e6d2', style='puff'),
                                              dict(colour='#e09a1f', style='gradient', angle=30)],
                               colour_holes=[dict(colour='#f3e6d2', up_to_mm2=5)],
                               outlines=dict(on=True, colour='auto'), density='lighter', sew_order='layers')),
        ('make_stitches', dict(note='The centre is too wide for puff: back to automatic.',
                               colour_styles=[dict(colour='#e09a1f', style='gradient', angle=30)])),
        ('finish', dict(attempt=2, summary='A badge with a satin edge and a soft star.',
                        request='The edge is satin as you asked; the centre is too wide for puff, so it is flat.',
                        tools_used=['satin border', 'line inside the border', 'gradient fill', 'outlines'])),
    ])
    job = _run_claude(tmp_path, monkeypatch, fake, request='a badge with a satin edge and a raised centre')
    assert job['state'] == 'done', job
    first, second = fake.replies()
    assert 'per_colour' in first and first['file_check'] == 'passed', first
    # Feedback per colour: the centre refused puff and said why; the star took the gradient.
    rows = {r['colour'].lower(): r for r in first['per_colour'] if 'areas' in r}
    centre = next(r for c, r in rows.items() if sum(abs(int(c[i:i+2], 16)-v) for i, v in zip((1, 3, 5), (243, 230, 210))) < 40)
    assert centre['style_refused'][0]['style'] == 'puff' and 'mm wide' in centre['style_refused'][0]['why']
    assert any('gradient' in r['styles_used'] for r in rows.values())
    assert all(r['area_mm2'] > 0 and r['widest_mm'] > 0 for r in rows.values())
    assert not any('style_refused' in r for r in second['per_colour'])
    # The person sees the plan, how the request was followed and the tools used.
    steps = [s['text'] for s in job['steps']]
    assert 'Plan: Centre (#f3e6d2): 3D puff - you asked for it raised' in steps
    result = job['result']
    assert result['plan'][0] == 'Ring (#1d4f91): automatic - a clean edge' and len(result['plan']) == 3
    assert result['request'].startswith('The edge is satin') and 'gradient fill' in result['tools_used']
    assert 'request leads' in fake.calls[0]['system'][0]['text']
    assert 'a raised centre' in fake.calls[0]['messages'][0]['content'][1]['text']


def test_scripted_claude_out_of_attempts_keeps_the_best_and_a_bad_finish_is_safe(tmp_path, monkeypatch):
    from embroiderly import auto_claude
    monkeypatch.setattr(auto_claude, 'MAX_ATTEMPTS', 2)
    stitch = ('make_stitches', dict(note='Try.', mode='colour', colours=3, height_mm=40))
    fake = _ScriptedClaude([stitch, stitch, stitch, ('finish', dict(attempt=9, summary='Kept one.'))])
    job = _run_claude(tmp_path, monkeypatch, fake)
    assert job['state'] == 'done' and job['result']['attempts'] == 2
    assert 'No attempts left' in fake.replies()[-1]
    assert job['result']['plan'] == [] and job['result']['tools_used'] == []


def test_scripted_claude_refusal_and_spend_cap_fall_back_to_the_rules(tmp_path, monkeypatch):
    from embroiderly import auto_claude
    job = _run_claude(tmp_path / 'refused', monkeypatch, _ScriptedClaude(['refusal']))
    assert job['state'] == 'done' and any('declined' in s['text'] and 'built-in rules' in s['text'] for s in job['steps'])
    fake = _ScriptedClaude([])
    job = _run_claude(tmp_path / 'capped', monkeypatch, fake, spent=auto_claude.TOTAL_LIMIT)
    assert job['state'] == 'done' and not fake.calls
    assert any('limit' in s['text'] and 'built-in rules' in s['text'] for s in job['steps'])
