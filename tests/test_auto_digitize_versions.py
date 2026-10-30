"""Session 28: pick from 2–3 versions (Cleaner, Balanced, More detail). Each is made like one run;
only versions that pass the file checks are offered; the pick becomes the kept result and its look
the choice for later changes."""
import json
import shutil
import subprocess
import time

import pytest

from embroiderly.auto_digitize import AutoDigitizer, classify, plan, version_options, wish_for
from embroiderly.web import create_app
from test_auto_digitize import _Block, _Usage, _wait, badge
from test_auto_digitize_start import HARNESS, SCRIPT


def test_each_version_changes_only_its_look():
    image = badge()
    kind, facts = classify(image)
    wish = {'width_mm': 60.0, 'fabric': 'cap'}
    options = {**plan(kind, facts, wish, image.size, {}), 'colour_knockouts': [{'colour': '#ffffff'}]}
    cleaner, wish_c = version_options(kind, facts, wish, image.size, {}, options, 'less')
    balanced, _ = version_options(kind, facts, wish, image.size, {}, options, '')
    more, wish_m = version_options(kind, facts, wish, image.size, {}, options, 'more')
    assert balanced == options and wish_c['detail'] == 'less' and wish_m['detail'] == 'more'
    assert cleaner['count'] < options['count'] < more['count']
    assert cleaner['floor_mm2'] > more['floor_mm2']
    # What the run decided (background left out, size, fabric) stays in every version.
    for version in (cleaner, more):
        assert version['colour_knockouts'] == options['colour_knockouts']
        assert version['height_mm'] == options['height_mm'] and version['fabric_preset'] == 'cap'
    # A tapped look is replaced by the version's own, not added to it.
    simple = {**wish, 'detail': 'less'}
    assert version_options(kind, facts, simple, image.size, {}, plan(kind, facts, simple, image.size, {}), '')[0]['count'] \
        == options['count']


def test_the_picked_look_wins_over_words_and_taps_and_later_changes_still_win():
    picked = {'detail': 'less', 'fabric': 'cap', 'picked_detail': 'more'}
    assert wish_for('make it simple', picked)['detail'] == 'more'
    assert 'detail' not in wish_for('make it simple', {**picked, 'picked_detail': ''})
    assert 'picked_detail' not in wish_for('', picked)
    assert wish_for('', picked, ['simpler please'])['detail'] == 'less'


def _fake_attempts(monkeypatch, gate_for=None, calls=None):
    """Stand-in for the slow generation: colours follow the count; one look can fail the file check."""
    def attempt(self, path, options, drop_below=.8, keep_playback=False):
        count = int(options.get('count', 4))
        if calls is not None:
            calls.append(count)
        result = dict(stitches=1000 * count, trims=count, colours=min(count, 3), width_mm=60.0, height_mm=45.0,
                      prepared='badge.png')
        if gate_for and count == gate_for:
            result['gate'] = 'Export blocked: 5 stitches cross empty areas.'
        if keep_playback:
            result['playback'] = dict(steps=[dict(t='stitch', x=0, y=0, color='#123456'),
                                             dict(t='stitch', x=10, y=8, color='#123456')], colors=['#123456'])
        return result, options
    monkeypatch.setattr(AutoDigitizer, '_attempt', attempt)
    monkeypatch.setattr(AutoDigitizer, '_keep_inside', lambda self, path, options: 0)


def test_only_versions_that_pass_are_offered_and_twins_are_shown_once(tmp_path, monkeypatch):
    calls = []
    _fake_attempts(monkeypatch, gate_for=2, calls=calls)
    app = create_app(tmp_path)
    badge().save(tmp_path / 'work/uploads/badge.png')
    client = app.test_client()
    assert client.post('/api/auto-digitize/badge.png', json={'versions': True, 'look': 'detailed'}).status_code == 202
    job = _wait(client, 'badge.png')
    assert job['state'] == 'done', job
    shown = {v['key']: v for v in job['result']['versions']}
    # Cleaner (2 colours) failed the file check: named, not offered, and said plainly.
    assert shown['cleaner']['ok'] is False and 'cross empty areas' in shown['cleaner']['problem']
    assert 'cleaner' not in job['version_settings']
    assert any(s['text'] == 'Cleaner version did not pass the file checks, so it is not offered.' for s in job['steps'])
    # The detailed look was tapped, so More detail is made last and kept until a pick.
    assert job['result']['picked'] == 'more' and calls[-1] == max(calls)
    assert job['choices']['picked_detail'] == 'more'
    # Every version is shown in the same order with its facts.
    assert [v['key'] for v in job['result']['versions'] if not v.get('same_as')] == ['cleaner', 'balanced', 'more']
    assert shown['balanced']['ok'] and shown['balanced']['stitches'] == 3000
    # A pick of a version that failed is refused; the one kept already needs no work.
    assert client.post('/api/auto-digitize/badge.png/pick', json={'version': 'cleaner'}).status_code == 400
    assert client.post('/api/auto-digitize/badge.png/pick', json={'version': 'more'}).status_code == 200
    assert client.post('/api/auto-digitize/missing.png/pick', json={'version': 'more'}).status_code == 409


def test_versions_that_sew_the_same_stitches_are_shown_once(tmp_path, monkeypatch):
    _fake_attempts(monkeypatch)
    # Balanced (3 colours) and More detail (4) sew alike when only 3 can be sewn: one card, said plainly.
    original = AutoDigitizer._attempt
    monkeypatch.setattr(AutoDigitizer, '_attempt', lambda self, path, options, *a, **k: original(
        self, path, {**options, 'count': min(3, options['count'])}, *a, **k))
    app = create_app(tmp_path)
    badge().save(tmp_path / 'work/uploads/badge.png')
    client = app.test_client()
    client.post('/api/auto-digitize/badge.png', json={'versions': True})
    job = _wait(client, 'badge.png')
    keys = [(v['key'], v.get('same_as')) for v in job['result']['versions']]
    assert keys == [('cleaner', None), ('balanced', None), ('more', 'balanced')], keys
    assert any(s['text'] == 'More detail came out the same as Balanced, so it is shown once.' for s in job['steps'])


def test_picking_a_version_keeps_it_and_change_it_builds_on_it(tmp_path):
    app = create_app(tmp_path)
    badge().save(tmp_path / 'work/uploads/badge.png')
    client = app.test_client()
    assert client.post('/api/auto-digitize/badge.png', json={'versions': True, 'size': 'small'}).status_code == 202
    job = _wait(client, 'badge.png')
    assert job['state'] == 'done', job
    offered = [v for v in job['result']['versions'] if v.get('ok')]
    assert len(offered) >= 2 and job['result']['picked'] == 'balanced'
    # Each offered version comes with a small picture of its stitches and its facts.
    for version in offered:
        assert version['preview'].startswith('data:image/jpeg;base64,') and len(version['preview']) < 60000
        assert version['stitches'] > 500 and version['colours'] >= 1 and abs(version['width_mm'] - 70) <= 2
    cleaner = next(v for v in offered if v['key'] == 'cleaner')
    assert cleaner['colours'] < job['result']['colours']
    assert client.post('/api/auto-digitize/badge.png/pick', json={'version': 'cleaner'}).status_code == 202
    job = _wait(client, 'badge.png')
    assert job['state'] == 'done' and job['result']['picked'] == 'cleaner'
    assert job['result']['stitches'] == cleaner['stitches'] and job['result']['colours'] == cleaner['colours']
    assert job['steps'][-2]['text'] == 'Keeping the Cleaner version…'
    # The kept result is what the studio opens (the saved settings) and what Change it builds on.
    saved = json.loads((tmp_path / 'work/decisions/badge.png.preparation.json').read_text())
    assert saved['count'] == cleaner['colours']
    stored = json.loads((tmp_path / 'work/decisions/badge.png.auto.json').read_text())
    assert stored['result']['picked'] == 'cleaner' and stored['choices']['picked_detail'] == 'less'
    said = client.post('/api/auto-digitize/badge.png/change', json={'text': 'more detail'}).get_json()
    assert said['understood'] == ['Keep more small details.']


class _VersionClaude:
    """A fake Claude: for each version one make_stitches call, then finish."""
    def __init__(self):
        self.calls, self.beta, self.requests = [], self, []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        if len(kw['messages']) == 1:
            self.requests.append(json.loads(kw['messages'][0]['content'][1]['text'].split('\n', 1)[1])['request'])
            content = [_Block(type='tool_use', id='a', name='make_stitches', input={'note': 'Flat badge.', 'mode': 'colour'})]
        else:
            content = [_Block(type='tool_use', id='b', name='finish', input={'attempt': 1, 'summary': 'A clean badge.'})]
        return _Block(stop_reason='tool_use', content=content, usage=_Usage())


def test_with_claude_each_version_is_asked_for_and_the_cost_adds_up(tmp_path, monkeypatch):
    import anthropic
    _fake_attempts(monkeypatch)
    fake = _VersionClaude()
    monkeypatch.setattr(anthropic, 'Anthropic', lambda **kw: fake)
    app = create_app(tmp_path)
    badge().save(tmp_path / 'work/uploads/badge.png')
    client = app.test_client()
    client.post('/api/auto-digitize/badge.png', json={'versions': True, 'use_claude': True, 'request': 'for a cap'})
    job = _wait(client, 'badge.png')
    assert job['state'] == 'done', job
    assert fake.requests == ['for a cap\nMake the Cleaner version: simpler, fewer colours.',
                             'for a cap\nMake the More detail version: small parts and more colours kept.',
                             'for a cap\nMake the Balanced version: the usual balance.']
    spent = json.loads((tmp_path / 'work/decisions/claude-spend.json').read_text())['usd']
    # Three runs, three times the credit, all said in the result.
    assert len(fake.calls) == 6 and job['result']['claude_usd'] == pytest.approx(spent, abs=1e-4)
    assert job['result']['decided_by'].startswith('Claude (') and job['request'] == 'for a cap'
    assert 'playback' not in json.dumps(job)


PICKER = r"""
let picked = null, started = null, jobNow = null;
global.fetch = async (url, init = {}) => {
  if (url.endsWith('/brief')) return {json: async () => ({brief: 'Flat-colour artwork.'})};
  if (url.includes('claude')) return {json: async () => ({available: true, spent_usd: 0, total_limit_usd: 4.5})};
  if (url.endsWith('/pick')) { picked = JSON.parse(init.body).version; return {ok: true, status: 202, json: async () => ({})} }
  if (init.method === 'POST') { started = JSON.parse(init.body); return {ok: true, status: 202, json: async () => ({})} }
  return {json: async () => jobNow || {state: 'none'}};
};
"""

PICKER_CHECKS = r"""
(async () => {
  for (let i = 0; i < 20; i++) await Promise.resolve();
  const versions = $('autoVersions'), claude = $('autoClaude'), report = {};
  report.onByDefault = versions.checked;
  claude.checked = true; claude.onchange();
  report.offWithClaude = versions.checked; report.priced = $('autoVersionsText').textContent;
  versions.checked = true;
  jobNow = {state: 'done', steps: [], result: {stitches: 3000, trims: 3, colours: 3, width_mm: 60, height_mm: 45, picked: 'balanced',
    versions: [{key: 'cleaner', label: 'Cleaner', ok: true, preview: 'data:image/jpeg;base64,AA', stitches: 2000, trims: 2, colours: 2, width_mm: 60, height_mm: 45},
               {key: 'balanced', label: 'Balanced', ok: true, preview: 'data:image/jpeg;base64,AB', stitches: 3000, trims: 3, colours: 3, width_mm: 60, height_mm: 45},
               {key: 'more', label: 'More detail', ok: false, problem: 'Export blocked'}]}};
  await $('autoStart').onclick();
  for (let i = 0; i < 50; i++) await Promise.resolve();
  report.sent = started.versions;
  const box = $('autoResult').children[1], cards = box.children[1].children;
  const text = c => c.children.map(x => x.textContent || '').join(' | ');
  report.cards = cards.map(c => ({text: text(c), disabled: c.disabled, clickable: !!c.onclick, img: c.children[0].src || null}));
  report.notes = box.children.slice(2).map(p => p.textContent);
  await cards[0].onclick();
  for (let i = 0; i < 50; i++) await Promise.resolve();
  report.picked = picked;
  console.log(JSON.stringify(report));
  process.exit(0);
})();
"""


@pytest.mark.skipif(not shutil.which('node'), reason='needs Node')
def test_the_panel_offers_versions_and_a_click_keeps_one(tmp_path):
    harness = tmp_path / 'harness.js'
    head = HARNESS.split('(async () => {')[0]
    harness.write_text(head.replace('eval(fs.readFileSync', PICKER + 'eval(fs.readFileSync') + PICKER_CHECKS)
    out = subprocess.run(['node', str(harness), str(SCRIPT)], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    report = json.loads(out.stdout.strip().splitlines()[-1])
    # On by default with the built-in rules; off and priced when Claude is turned on.
    assert report['onByDefault'] is True and report['offWithClaude'] is False and '3×' in report['priced']
    assert report['sent'] is True
    cleaner, balanced, more = report['cards']
    assert cleaner['clickable'] and not cleaner['disabled'] and cleaner['img'].startswith('data:image/jpeg')
    assert 'Cleaner' in cleaner['text'] and '2,000 stitches' in cleaner['text'] and '2 colours · 2 cuts' in cleaner['text']
    assert 'File checks passed' in cleaner['text']
    assert '✓ Kept' in balanced['text'] and not balanced['clickable']
    assert more['disabled'] and 'Could not be made' in more['text'] and not more['clickable']
    assert report['notes'] == ['Your pick is what Show the result opens and what Change it builds on.']
    assert report['picked'] == 'cleaner'
