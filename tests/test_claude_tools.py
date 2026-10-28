"""Claude's tool choices come from Needler's own lists: a fabric, border or hoop that reaches
the app must reach Claude too, and each choice must turn into settings the engine accepts."""
import json
from types import SimpleNamespace

import numpy as np
from PIL import Image

from embroiderly import custom_fabrics, hoops
from embroiderly.auto_claude import catalog, handbook, run, settings_from, tools
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


def _handbook_rows():
    from embroiderly.knowledge_store import load_knowledge
    return {r['id']: r for r in load_knowledge()['handbook.json']['rows']}


def test_the_handbook_covers_every_tool_claude_can_meet():
    rows = _handbook_rows()
    offered = _settings()
    for mode in offered['mode']['enum']:
        assert f'mode:{mode}' in rows
    for style, _, _ in CATALOG:
        assert f'area:{style}' in rows, style
    for style, choices in VARIANTS.items():
        assert rows[f'area:{style}']['choices'] == [n for _, n in choices], style
    for style in catalog()['borders'][1:]:
        assert f'border:{style}' in rows, style
    # Every make_stitches setting is explained by at least one row.
    controls = {r.get('control') for r in rows.values()}
    assert set(offered) - {'note'} <= controls, set(offered) - {'note'} - controls
    for row in rows.values():
        assert all(isinstance(row[k], str) and row[k].strip() for k in ('tool', 'does', 'use', 'avoid', 'limits'))
    text = handbook()
    for fabric in presets():
        assert f"- {fabric['fabric']} ({fabric['label']})" in text


class _FakeClaude:
    """Finishes at once and records what was sent."""

    def __init__(self):
        self.sent = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.sent.append(kwargs)
        return SimpleNamespace(stop_reason='tool_use', usage=SimpleNamespace(
            input_tokens=10, output_tokens=10, cache_creation_input_tokens=0, cache_read_input_tokens=0),
            content=[SimpleNamespace(type='tool_use', name='finish', id='t1', input=dict(attempt=1, summary='x'))])


def test_the_handbook_is_sent_and_cached_with_the_instructions(tmp_path):
    picture = tmp_path / 'work' / 'uploads' / 'p.png'
    picture.parent.mkdir(parents=True)
    (tmp_path / 'work' / 'decisions').mkdir()
    Image.new('RGB', (64, 64), 'white').save(picture)
    claude = _FakeClaude()
    attempts, finish = run(dict(request=''), picture, 'logo', {}, {}, {}, lambda o: None, lambda m: None, client=claude)
    assert attempts == [] and finish['attempt'] == 1
    instructions, book = claude.sent[0]['system']
    assert 'expert machine-embroidery digitizer' in instructions['text'] and 'cache_control' not in instructions
    assert book['text'] == handbook() and book['cache_control'] == dict(type='ephemeral')
