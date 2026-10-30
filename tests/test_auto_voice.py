"""Speak in Digitize for me (Oct 2026): pressed, it went straight back to Speak with no word.
Most stop reasons were silent and Chrome's own end after a pause ended the listening. Now the
microphone is asked for first, listening goes on until Stop, and every stop reason is said.
The panel script runs in Node with a stand-in for the browser's speech service."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'src/embroiderly/static/auto-digitize.js'

HARNESS = r"""
const fs = require('fs');
function el(tag) {
  const e = {tag, hidden: false, value: '', textContent: '', className: '', title: '', innerHTML: '', children: [], attrs: {},
    classList: {set: new Set(), add(c) { this.set.add(c) }, remove(c) { this.set.delete(c) }},
    setAttribute(k, v) { this.attrs[k] = v }, append(...c) { this.children.push(...c) }, prepend(...c) { this.children.unshift(...c) },
    focus() {}, dispatchEvent() {}, parts: {},
    querySelector(q) { return this.parts[q] || (this.parts[q] = el(q)) }};
  return e;
}
global.document = {createElement: el, documentElement: {lang: 'en'}, addEventListener() {}};
let made = [], micResult = 'ok';
class Fake { constructor() { made.push(this) } start() { this.started = true } stop() { this.onend && this.onend() } }
global.window = {SpeechRecognition: Fake};
Object.defineProperty(globalThis, 'isSecureContext', {configurable: true, get: () => window.isSecureContext});
Object.defineProperty(globalThis, 'navigator', {configurable: true, value: {language: 'en-GB', mediaDevices: {getUserMedia: async () => {
  if (micResult !== 'ok') { const e = new Error(micResult); e.name = micResult; throw e }
  return {getTracks: () => [{stop() {}}]};
}}}});
global.Event = class { constructor(t) { this.type = t } };
eval(fs.readFileSync(process.argv[2], 'utf8'));
const tick = () => new Promise(r => setImmediate(r));
(async () => {
  const report = {};
  const make = () => module.exports.autoComposer('f', 'Words', 'Type', '');
  // 1. Chrome ends by itself after a pause: listening goes on, the words stay, Stop ends it.
  let box = make(), mic = box.querySelector('.auto-composer-bar').children[0], field = box.querySelector('textarea');
  const why = box.children.find(c => c.className === 'auto-voice-problem');
  await mic.onclick(); await tick();
  report.lang = made[0].lang;
  made[0].onresult({results: [[{transcript: 'remove the white'}]]});
  await new Promise(r => setTimeout(r, 1600)); made[0].onend();
  report.restarted = made.length === 2 && made[1].started === true;
  made[1].onresult({results: [[{transcript: 'background'}]]});
  report.words = field.value; report.label = mic.querySelector('span').textContent;
  await mic.onclick();
  report.stopped = mic.querySelector('span').textContent === 'Speak' && made.length === 2;
  // 2. The speech service cannot be reached: said in words, not a silent reset.
  made = []; box = make(); mic = box.querySelector('.auto-composer-bar').children[0];
  const why2 = box.children.find(c => c.className === 'auto-voice-problem');
  await mic.onclick(); made[0].onerror({error: 'network'}); made[0].onend();
  report.network = why2.hidden ? '' : why2.textContent; report.networkLabel = mic.querySelector('span').textContent;
  // 3. Ending at once, again and again: stops after three tries and says why.
  made = []; box = make(); mic = box.querySelector('.auto-composer-bar').children[0];
  const why3 = box.children.find(c => c.className === 'auto-voice-problem');
  await mic.onclick(); for (let i = 0; i < 3; i++) made[made.length - 1].onend();
  report.quick = why3.hidden ? '' : why3.textContent; report.quickTries = made.length;
  // 4. No microphone: found before listening starts.
  made = []; micResult = 'NotFoundError'; box = make(); mic = box.querySelector('.auto-composer-bar').children[0];
  const why4 = box.children.find(c => c.className === 'auto-voice-problem');
  await mic.onclick();
  report.nomic = why4.hidden ? '' : why4.textContent; report.nomicStarted = made.length;
  report.firstWhyHidden = why.hidden;
  // 5. A double click starts it and leaves it listening.
  made = []; micResult = 'ok'; box = make(); mic = box.querySelector('.auto-composer-bar').children[0];
  const first = mic.onclick(); mic.onclick(); await first; await mic.onclick();
  report.doubleClick = mic.querySelector('span').textContent; report.doubleClickStarts = made.length;
  // 6. Listening that never reaches the microphone is said after 5 s.
  await new Promise(r => setTimeout(r, 5100));
  const why6 = box.children.find(c => c.className === 'auto-voice-problem');
  report.noAudio = why6.hidden ? '' : why6.textContent; report.noAudioLabel = mic.querySelector('span').textContent;
  // 7. Opened at another computer's address: the browser keeps the microphone off; said, not tried.
  made = []; window.isSecureContext = false; global.location = {port: '5077', host: '192.168.1.20:5077'};
  box = make(); mic = box.querySelector('.auto-composer-bar').children[0];
  const why7 = box.children.find(c => c.className === 'auto-voice-problem');
  await mic.onclick();
  report.insecure = why7.hidden ? '' : why7.textContent; report.insecureStarts = made.length;
  console.log(JSON.stringify(report));
  process.exit(0);
})();
"""


@pytest.mark.skipif(not shutil.which('node'), reason='needs Node')
def test_speak_keeps_listening_until_stop_and_says_why_it_stops(tmp_path):
    harness = tmp_path / 'harness.js'
    harness.write_text(HARNESS)
    out = subprocess.run(['node', str(harness), str(SCRIPT)], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    report = json.loads(out.stdout.strip().splitlines()[-1])
    assert report['lang'] == 'en-GB'
    assert report['restarted'] and report['words'] == 'remove the white background' and report['label'] == 'Stop'
    assert report['stopped'] and report['firstWhyHidden']
    assert 'speech service could not be reached' in report['network'] and report['networkLabel'] == 'Speak'
    assert 'stops as soon as it starts' in report['quick'] and report['quickTries'] == 3
    assert 'No microphone was found' in report['nomic'] and report['nomicStarted'] == 0
    assert report['doubleClick'] == 'Stop' and report['doubleClickStarts'] == 1
    assert 'microphone did not start' in report['noAudio'] and report['noAudioLabel'] == 'Speak'
    assert 'http://127.0.0.1:5077' in report['insecure'] and '192.168.1.20:5077' in report['insecure']
    assert report['insecureStarts'] == 0
