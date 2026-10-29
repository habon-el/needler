"""Studio: a new thread colour keeps "I approve"; a merge into another colour does not.

Found Oct 2026: changing a thread colour unticked the subject approval, so every colour
change needed approving again. The approval is of the subject and its shapes; a new thread
colour changes neither (area identities survive colour changes, UX-CONTRACT region styles).
Picking another swatch's exact colour merges two areas into one: new shapes, so the
approval still clears, as every other artwork change does.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / 'src/embroiderly/static/preparation.js'


def _line(source, start):
    return next(line for line in source.splitlines() if line.startswith(start))


@pytest.mark.skipif(not shutil.which('node'), reason='needs Node')
def test_invalidate_keeps_approval_only_when_asked(tmp_path):
    source = SOURCE.read_text(encoding='utf-8')
    code = _line(source, 'function invalidate(') + '\n' + _line(source, 'function schedule(')
    harness = tmp_path / 'h.js'
    harness.write_text(r"""
const els = {};
const $ = id => els[id] || (els[id] = {checked: false, hidden: false, disabled: false, textContent: '', replaceChildren() {}});
let proposalVersion=0, proposalBefore, proposalAfter, currentView='stitched', colourPreviewPlan, colourPreviewMap, colourPreviewImage,
  colourFrame=0, queuedAction, stitchError, latest, selectedBounds, running, cursor, revision=0, playback, timer;
const stitchLayer = {reset() {}}, window = {dispatchEvent() {}};
const cancelAnimationFrame = () => {}, transport = () => {}, draw = () => {}, status = () => {}, requestPreview = () => {};
const setTimeout = () => 0, clearTimeout = () => {};
class Event { constructor(k) { this.k = k } }
""" + code + r"""
const out = {};
$('confirmed').checked = true; schedule(true); out.colour = $('confirmed').checked;
$('confirmed').checked = true; schedule(); out.other = $('confirmed').checked;
console.log(JSON.stringify(out));
""")
    run = subprocess.run(['node', str(harness)], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout) == {'colour': True, 'other': False}


def test_swatch_colour_change_keeps_approval_unless_it_merges():
    source = SOURCE.read_text(encoding='utf-8')
    change = source[source.index('input.onchange=()=>{'):source.index("const text=document.createElement('div')")]
    assert 'schedule(!merged)' in change
    assert "palette.some(c=>c.hex!==p.hex&&c.hex.toLowerCase()===input.value.toLowerCase())" in change
    # Dropping one swatch on another is a merge: it still needs approving again.
    drop = source[source.index('el.ondrop='):source.index('el.onclick=')]
    assert 'schedule()' in drop
