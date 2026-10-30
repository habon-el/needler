"""Digitize for me: Start always starts, also over an earlier result.

Found Oct 2026: with a result showing, Start did nothing. After "Show the result" the
page is still preparing that result, and Start refused while it did; a result it could
not show left the panel as if a run were still going; and the studio re-enabled Start
during a run, where a click is ignored. The panel script runs here in Node against a
small stand-in for the page.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'src/embroiderly/static/auto-digitize.js'

HARNESS = r"""
const fs = require('fs');
const elements = {}, listeners = {};
function el(id) {
  const e = {id, hidden: false, disabled: false, checked: false, value: '', textContent: '', dataset: {}, children: [],
    classList: {toggle() {}}, style: {}, title: '', type: '', className: '', innerHTML: '',
    setAttribute() {}, focus() {}, addEventListener() {}, append(...c) { this.children.push(...c) }, prepend(...c) { this.children.unshift(...c) },
    replaceChildren(...c) { this.children = c }, insertBefore(c) { this.children.push(c) },
    querySelector() { return elements[id + ' span'] || (elements[id + ' span'] = el(id + ' span')) }};
  return e;
}
const $ = id => elements[id] || (elements[id] = el(id));
let busy = 2, posts = 0, state = 'done';
global.MutationObserver = class { constructor(f) { this.f = f } observe(target) { (target.observers = target.observers || []).push(this.f) } };
global.localStorage = {getItem() { return null }, setItem() {}};
global.location = {search: '', pathname: '/a'};
global.window = {embroideryStudio: {isBusy: () => busy-- > 0}, preparationConfig: {name: 'rose.png'}};
global.document = {
  getElementById: $, createElement: tag => el(tag),
  querySelector: q => $(q), addEventListener: (k, f) => { listeners[k] = f },
};
global.fetch = async (url, init = {}) => {
  if (url.endsWith('/brief')) return {json: async () => ({brief: 'Flat-colour artwork.'})};
  if (init.method === 'POST') { posts++; state = 'running'; return {ok: false, status: 202, json: async () => ({})} }
  if (url.includes('claude')) return {json: async () => ({available: false})};
  const job = state === 'running' ? {state, steps: [{at: 1, text: 'Looked at the picture.'}]} :
    {state: 'done', steps: [], result: {stitches: 100, plan: 'not a list'}};
  if (state === 'running') state = 'done';
  return {json: async () => job};
};
global.setTimeout = (f, ms) => { Promise.resolve().then(f); return 0 };
global.clearTimeout = () => {};
eval(fs.readFileSync(process.argv[2], 'utf8'));
listeners.DOMContentLoaded();
(async () => {
  const start = $('autoStart'), result = $('autoResult');
  result.children = ['old result'];
  await start.onclick();
  for (let i = 0; i < 50; i++) await Promise.resolve();
  const report = {posts, cleared: !result.children.includes('old result'), runningAfter: start.disabled};
  // A second Start over that result starts again.
  await start.onclick();
  for (let i = 0; i < 50; i++) await Promise.resolve();
  report.posts2 = posts;
  // During a run the studio's "enable every button" does not make Start clickable.
  state = 'running'; busy = 0;
  const pending = start.onclick();
  start.disabled = false; (start.observers || []).forEach(f => f());
  report.keptDisabled = start.disabled;
  console.log(JSON.stringify(report));
  process.exit(0);
})();
"""


@pytest.mark.skipif(not shutil.which('node'), reason='needs Node')
def test_start_waits_for_preparation_and_starts_over_an_old_result(tmp_path):
    harness = tmp_path / 'harness.js'
    harness.write_text(HARNESS)
    out = subprocess.run(['node', str(harness), str(SCRIPT)], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    report = json.loads(out.stdout.strip().splitlines()[-1])
    # Busy twice, then free: it waited and then started (no refusal), and the old result went.
    assert report['posts'] == 1 and report['cleared']
    # The finished job could not be fully shown (plan not a list), yet Start is free again.
    assert report['runningAfter'] is False and report['posts2'] == 2
    assert report['keptDisabled'] is True


CHECKS = r"""
(async () => {
  const box = $('autoRequest'), warn = $('autoRequestLong');
  box.value = 'x'.repeat(1000); box.oninput();
  const report = {limit: module.exports.AUTO_REQUEST_LIMIT, fits: warn.hidden};
  box.value = 'x'.repeat(1200); box.oninput();
  report.long = warn.hidden ? '' : warn.textContent;
  const note = module.exports.autoReviewNote;
  report.passed = note(2, {stitches: 100, ok: true});
  report.blocked = note(1, {stitches: 100, ok: false, problem: 'Export blocked: 5 stitches cross empty areas'});
  report.none = note(0, {stitches: 100, ok: true});
  console.log(JSON.stringify(report));
  process.exit(0);
})();
"""


@pytest.mark.skipif(not shutil.which('node'), reason='needs Node')
def test_a_long_request_is_warned_and_the_3d_note_follows_the_export_result(tmp_path):
    """Session 23: the request box cut at 300 characters with no warning, and the 3D note said
    the marked places passed the file checks even when the download was blocked."""
    from embroiderly.auto_digitize import REQUEST_LIMIT
    harness = tmp_path / 'harness.js'
    harness.write_text(HARNESS.split('(async () => {')[0] + CHECKS)
    out = subprocess.run(['node', str(harness), str(SCRIPT)], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    report = json.loads(out.stdout.strip().splitlines()[-1])
    assert report['limit'] == REQUEST_LIMIT and report['fits'] is True
    assert '1,200 characters' in report['long'] and 'first 1,000' in report['long']
    assert 'maxlength' not in SCRIPT.read_text(encoding='utf-8')
    assert report['passed'].startswith('3D preview ready. Look at the 2 places') and 'file checks passed' in report['passed']
    assert 'download is blocked' in report['blocked'] and 'passed' not in report['blocked']
    assert report['none'] == ''
