"""An old prepared preview cannot certify today's preparation code."""
import hashlib
import json

from PIL import Image
from embroiderly.saved_plans import matching_plan


def test_legacy_preview_does_not_appear_current_after_a_pipeline_update(tmp_path):
    source = tmp_path / 'art.png'
    Image.new('RGB', (20, 20), 'red').save(source)
    options = {'height_mm': 50}
    old_key = hashlib.sha256(source.read_bytes() + json.dumps(options, sort_keys=True).encode() + b'prep-v2').hexdigest()[:24]
    folder = tmp_path / 'work/inkstitch-preview' / ('prepared_' + old_key)
    folder.mkdir(parents=True)
    (folder / 'playback.json').write_text(json.dumps(dict(colors=['#ff0000'],
        steps=[dict(x=0, y=0, t='stitch', color='#ff0000')], origin_mm=[0, 0])))
    before = (folder / 'playback.json').read_bytes()
    assert matching_plan(tmp_path, source, options) == {}
    assert (folder / 'playback.json').read_bytes() == before
