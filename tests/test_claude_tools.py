"""Claude's tool choices come from Needler's own lists: a fabric, border or hoop that reaches
the app must reach Claude too, and each choice must turn into settings the engine accepts."""
import json

import numpy as np

from embroiderly import custom_fabrics, hoops
from embroiderly.auto_claude import catalog, settings_from, tools
from embroiderly.borders import OUTLINES, border_plan
from embroiderly.generation_policy import preset_for, presets
from embroiderly.region_stitches import CATALOG, VARIANTS
from embroiderly.stitch_paths import MOTIFS, PATTERNS


def _settings(root=None):
    return tools(root)[0]['input_schema']['properties']


def test_every_listed_fabric_border_and_hoop_is_offered():
    offered = _settings()
    assert offered['fabric']['enum'] == [r['fabric'] for r in presets()]
    assert offered['border']['properties']['style']['enum'] == ['off', 'running', 'satin', *OUTLINES]
    assert offered['border']['properties']['motif']['enum'] == list(MOTIFS)
    assert offered['border']['properties']['pattern']['enum'] == list(PATTERNS)
    assert offered['hoop']['enum'] == [h['id'] for g in hoops.listed() for h in g['hoops']]
    # Claude reads the names too, not just the ids.
    assert 'leather: Leather' in offered['fabric']['description']
    assert 'brother-130x180: Brother 5 × 7 in 130x180 mm' in offered['hoop']['description']


def test_every_area_style_and_its_choices_are_in_the_catalog():
    listed = {s['id'] for s in catalog()['area_styles']}
    assert {k for k, _, _ in CATALOG} <= listed
    assert {f'{k}:{v}' for k, choices in VARIANTS.items() for v, _ in choices[1:]} <= listed


def test_the_persons_own_fabrics_and_hoops_are_offered(tmp_path):
    fabric, _ = custom_fabrics.save(tmp_path, dict(name='Thick hoodie', base='fleece', row_spacing_mm=.4,
                                                   satin_spacing_mm=.4, satin_pull_mm=.2, fill_underlay=True,
                                                   max_stitch_length_mm=5))
    hoop = hoops.save(tmp_path, dict(name='Big frame', width_mm=300, height_mm=200))[0]
    offered = _settings(tmp_path)
    assert fabric['id'] in offered['fabric']['enum'] and 'Thick hoodie (their own)' in offered['fabric']['description']
    assert hoop['id'] in offered['hoop']['enum']
    chosen = settings_from(dict(note='x', fabric=fabric['id'], hoop=hoop['id']), {}, root=tmp_path)
    assert chosen['fabric_preset'] == 'fleece' and chosen['fabric_custom']['id'] == fabric['id']
    assert preset_for(chosen)['label'] == 'Thick hoodie'
    assert chosen['hoop_id'] == hoop['id'] and chosen['piece_hoop_mm'] == [300, 200]
    # A listed fabric replaces the person's own one.
    assert 'fabric_custom' not in settings_from(dict(note='x', fabric='denim'), chosen, root=tmp_path)


def test_every_offered_choice_becomes_settings_the_engine_accepts(tmp_path):
    offered = _settings(tmp_path)
    for fabric in offered['fabric']['enum']:
        assert preset_for(settings_from(dict(note='x', fabric=fabric), {}, root=tmp_path))['fabric'] == fabric
    for hoop in offered['hoop']['enum']:
        chosen = settings_from(dict(note='x', hoop=hoop), {}, root=tmp_path)
        assert hoops.find(tmp_path, chosen['hoop_id'])['width_mm'] == chosen['piece_hoop_mm'][0]
    mask = np.zeros((200, 200), bool)
    mask[40:160, 40:160] = True
    border = offered['border']['properties']
    for style in border['style']['enum'][1:]:
        extras = [{}] + ([{'motif': m} for m in border['motif']['enum']] if style == 'motif' else []) + \
            ([{'pattern': p} for p in border['pattern']['enum']] if style == 'pattern' else [])
        for extra in extras:
            chosen = settings_from(dict(note='x', border=dict(style=style, **extra)), {}, root=tmp_path)
            assert border_plan(mask, 40, chosen) is not None, (style, extra)
    assert settings_from(dict(note='x', border=dict(style='off')), {}, root=tmp_path)['border_style'] == 'off'


def test_unlisted_choices_are_ignored(tmp_path):
    before = dict(fabric_preset='twill', border_style='off')
    after = settings_from(dict(note='x', fabric='paper', hoop='no-such-hoop', border=dict(style='lace')), before,
                          root=tmp_path)
    assert after == before
    json.dumps(tools(tmp_path))
