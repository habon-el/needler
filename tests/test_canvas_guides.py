"""Guides, grid and snap on the design canvas: guides are checked, saved with the design and given
back, and never change the stitches; the snapping math lines points and pieces up."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from test_sew_order import picture  # noqa: E402
from embroiderly import canvas_guides  # noqa: E402

SCRIPT = Path(__file__).parents[1]/'src'/'embroiderly'/'static'/'canvas-guides.js'
GUIDES = [dict(axis='x', mm=12.34), dict(axis='y', mm=-20)]


def test_good_guides_are_kept_and_rounded():
    assert canvas_guides.checked(GUIDES) == [dict(axis='x', mm=12.3), dict(axis='y', mm=-20.0)]
    assert canvas_guides.checked([]) == []
    assert len(canvas_guides.checked([dict(axis='y', mm=n) for n in range(canvas_guides.MAX_GUIDES)])) == 20


@pytest.mark.parametrize('value', [
    None, {}, 'x', [dict(axis='x', mm=0)]*21, [dict(axis='z', mm=0)], [dict(axis='x')], [dict(axis='x', mm='5')],
    [dict(axis='x', mm=float('nan'))], [dict(axis='y', mm=float('inf'))], [dict(axis='x', mm=500.1)],
    [dict(axis='x', mm=True)], [dict(axis='x', mm=1, colour='red')], ['x']])
def test_bad_guides_are_refused(value):
    with pytest.raises(ValueError):
        canvas_guides.checked(value)


def test_guides_are_not_part_of_the_preparation_key_or_the_saved_plan_match():
    from embroiderly.preparation_identity import preparation_key
    from embroiderly.saved_plans import equivalent
    options = dict(height_mm=80, count=2)
    assert preparation_key(b'png', options) == preparation_key(b'png', {**options, 'canvas_guides': GUIDES})
    assert equivalent(options, {**options, 'canvas_guides': GUIDES})


def test_the_lock_guard_allows_guides():
    from embroiderly.piece_layout import guard
    previous = {'piece_edits': {'a'*20: {'locked': True}}}
    guard(previous, {**previous, 'canvas_guides': GUIDES})


def setup(root):
    from embroiderly.web import create_app
    (root/'work/uploads').mkdir(parents=True)
    Image.fromarray(picture()).save(root/'work/uploads/p.png')
    client = create_app(root).test_client()
    return client, {'height_mm': 80, 'floor_mm2': 1, 'smooth': 0, 'mask_holes_mm2': 0, 'count': 2}


def test_guides_are_saved_given_back_and_cleared(tmp_path):
    client, options = setup(tmp_path)
    saved = tmp_path/'work/decisions/p.png.preparation.json'
    saved.parent.mkdir(parents=True, exist_ok=True)
    saved.write_text(json.dumps({**options, 'piece_hoop_mm': [130, 180]}))
    body = client.post('/api/guides/p.png', json=dict(guides=GUIDES)).get_json()
    assert body['guides'] == [dict(axis='x', mm=12.3), dict(axis='y', mm=-20.0)]
    kept = json.loads(saved.read_text())
    # Only the guides changed in the saved settings.
    assert kept == {**options, 'piece_hoop_mm': [130, 180], 'canvas_guides': body['guides']}
    import hashlib
    assert body['piece_revision'] == hashlib.sha256(saved.read_bytes()).hexdigest()
    # They come back after reload: the page is given the saved options.
    assert '"canvas_guides": [{"axis": "x", "mm": 12.3}' in client.get('/artwork/p.png').get_data(as_text=True)
    assert client.post('/api/guides/p.png', json=dict(guides=[])).get_json()['guides'] == []
    assert 'canvas_guides' not in json.loads(saved.read_text())


def test_bad_guides_are_refused_by_the_routes(tmp_path):
    client, options = setup(tmp_path)
    assert client.post('/api/guides/p.png', json=dict(guides=[dict(axis='x', mm=900)])).status_code == 400
    assert client.post('/api/guides/p.png', json=[1]).status_code == 400
    assert client.post('/api/guides/missing.png', json=dict(guides=[])).status_code == 404
    body = client.post('/artwork/p.png', json=dict(options={**options, 'canvas_guides': [dict(axis='q', mm=0)]})).get_json()
    assert 'guide' in (body.get('error') or '')


def test_guides_never_change_the_stitches(tmp_path):
    from embroiderly.release_gate import checked_bytes
    from embroiderly.saved_plans import matching_plan
    made = {}
    for name, extra in (('plain', {}), ('guided', {'canvas_guides': GUIDES})):
        root = tmp_path/name
        client, options = setup(root)
        body = client.post('/artwork/p.png', json=dict(options={**options, **extra}, subject_confirmed=True, digitize=True)).get_json()
        assert body.get('playback'), body.get('error')
        folder = root/'work'/'inkstitch-preview'/Path(body['prepared_name']).stem
        made[name] = body['prepared_name'], checked_bytes(folder, 'dst'), checked_bytes(folder, 'pes')
    assert made['plain'] == made['guided']
    # Adding or moving guides later keeps the stitch plan that was made.
    root = tmp_path/'plain'
    from embroiderly.web import create_app
    client = create_app(root).test_client()
    assert client.post('/api/guides/p.png', json=dict(guides=[dict(axis='y', mm=7)])).status_code == 200
    saved = json.loads((root/'work/decisions/p.png.preparation.json').read_text())
    assert saved['canvas_guides'] == [dict(axis='y', mm=7.0)]
    assert matching_plan(root, root/'work/uploads/p.png', saved).get('playback')


def snap(expression):
    node = shutil.which('node')
    if not node:
        pytest.skip('node is not installed')
    code = f"const Snap=require({json.dumps(str(SCRIPT))});console.log(JSON.stringify({expression}))"
    return json.loads(subprocess.run([node, '-e', code], capture_output=True, text=True, check=True).stdout)


def test_snapping_math():
    settings = "{guides:[{axis:'x',mm:10},{axis:'y',mm:-5}],grid:0,tolerance:1}"
    # A point near a guide or the hoop centre lines locks on; one further away stays.
    assert snap(f"Snap.point([10.6,-4.2],{settings})") == [10, -5]
    assert snap(f"Snap.point([0.4,12],{settings})") == [0, 12]
    assert snap(f"Snap.point([13,3],{settings})") == [13, 3]
    # The grid: the nearest grid line within the tolerance.
    assert snap("Snap.point([4.3,7.4],{guides:[],grid:5,tolerance:1})") == [5, 7.4]
    assert snap("Snap.point([4.3,7.4],{guides:[],grid:0,tolerance:1})") == [4.3, 7.4]
    # A moved piece: its nearest edge or centre locks on (right edge 9.4 to the guide at 10).
    assert snap(f"Snap.move({{x_mm:0,y_mm:0,width_mm:10,height_mm:4}},4.4,0.3,{settings})") == [5, 0]
    assert snap("Snap.offset([1,2],[2.5,7],1)") == 0.5
