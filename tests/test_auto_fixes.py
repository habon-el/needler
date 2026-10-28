from shapely.geometry import Polygon

from embroiderly.auto_claude import settings_from
from embroiderly.auto_digitize import parse_request
from embroiderly.satin_font import area_columns


def test_keep_the_background_is_understood():
    assert parse_request('YOU CAN KEEP THEY BLACK BACK GROUND THERE')['keep_background'] is True
    assert parse_request('keep the background')['keep_background'] is True
    assert 'keep_background' not in parse_request('6 cm wide, 3 colours')
    assert 'keep_background' not in parse_request('Remove the white background and stitch the rose only.')
    assert 'keep_background' not in parse_request('no background, just sew the flower')


def test_claude_erase_boxes_become_erase_edits():
    user = dict(kind='erase', shape='polygon', radius=1, points=[[1, 1], [5, 1], [5, 5]])
    options = settings_from({'erase': [dict(x0=.9, y0=.4, x1=1, y1=.5)]}, {'edits': [user]}, (400, 800))
    claude = [e for e in options['edits'] if e.get('claude')]
    assert options['edits'][0] == user and len(claude) == 1
    assert claude[0]['points'] == [[360, 320], [399, 320], [399, 400], [360, 400]]
    # A new list replaces Claude's earlier boxes, never the person's own edits.
    again = settings_from({'erase': []}, options, (400, 800))
    assert again['edits'] == [user]


def test_self_touching_outline_still_gets_columns():
    # A bow-tie ring touching itself, as pixel tracing can produce.
    shape = Polygon([(0, 0), (10, 0), (10, 3), (5, 1.5), (0, 3)]).union(
        Polygon([(5, 1.5), (10, 6), (0, 6)]))
    bad = Polygon([(0, 0), (4, 4), (8, 0), (8, 3), (4, 4), (0, 3)])
    assert not bad.is_valid
    assert area_columns(bad)
    assert area_columns(shape)


def test_keep_background_clears_a_saved_subject_cut_out():
    from embroiderly.auto_digitize import plan
    saved = dict(selection='grabcut', rect=[10, 120, 443, 740], count=6)
    options = plan('logo', {'thread_colours': 6}, {'keep_background': True}, (444, 741), saved)
    assert options['selection'] == 'full' and 'rect' not in options
    assert plan('logo', {'thread_colours': 6}, {}, (444, 741), saved)['selection'] == 'grabcut'
    claude = settings_from({'keep_background': True}, saved, (444, 741))
    assert claude['selection'] == 'full' and 'rect' not in claude


def test_erase_on_a_kept_background_paints_the_surrounding_colour():
    import numpy as np
    image = np.zeros((100, 100, 3), np.uint8)
    image[40:50, 80:90] = 200  # a grey button on black
    options = settings_from({'erase': [dict(x0=.78, y0=.38, x1=.92, y1=.52)]}, {'selection': 'full'}, (100, 100), image)
    edit = options['edits'][0]
    assert edit['kind'] == 'paint' and edit['colour'] == '#000000'
    cut = settings_from({'erase': [dict(x0=.78, y0=.38, x1=.92, y1=.52)]}, {'selection': 'grabcut'}, (100, 100), image)
    assert cut['edits'][0]['kind'] == 'erase'


def test_auto_fabric_presets_change_density_pull_and_ties():
    from embroiderly.auto_digitize import plan
    from embroiderly.generation_policy import presets, preset_for
    from embroiderly.knowledge_store import load_knowledge
    load_knowledge()  # the table stays valid
    ids = {r['fabric'] for r in presets()}
    assert {'twill', 'stretch_knit', 'fleece', 'towel', 'cap', 'denim'} <= ids
    assert preset_for({'fabric_preset': 'fleece'})['satin_pull_mm'] > preset_for({})['satin_pull_mm']
    assert parse_request('logo for a polo shirt')['fabric'] == 'pique'
    assert parse_request('6 cm on a cap, 3D puff')['fabric'] == 'cap'
    assert parse_request('my t-shirt')['fabric'] == 'stretch_knit'
    assert plan('logo', {}, {'fabric': 'towel'}, (100, 100), {})['fabric_preset'] == 'towel'
    assert settings_from({'fabric': 'fleece'}, {})['fabric_preset'] == 'fleece'


def test_fabric_changes_the_stitches(tmp_path):
    from PIL import Image, ImageDraw
    from embroiderly.web import create_app
    client = create_app(tmp_path).test_client()
    image = Image.new('RGB', (300, 200), 'white')
    ImageDraw.Draw(image).rectangle((40, 40, 260, 160), fill='#1d4f91')
    image.save(tmp_path / 'work/uploads/block.png')
    counts = {}
    for fabric in ('twill', 'cap', 'denim'):
        options = dict(artwork_type='logo', count=2, height_mm=40, fabric_preset=fabric)
        body = client.post('/artwork/block.png', json=dict(options=options, digitize=True, subject_confirmed=True)).get_json()
        counts[fabric] = body['playback']['stitch_count']
    # Cap is denser than twill, denim looser.
    assert counts['cap'] > counts['twill'] > counts['denim']


def test_claude_tools_merge_border_and_cut_report(tmp_path):
    from embroiderly.auto_claude import per_colour, recent_sewouts
    options = settings_from({'merge_colours': [dict(colour='#7D2728', into='#da4545')],
                             'border': dict(style='satin', width_mm=3, colour='#202020')}, {})
    assert options['merges'] == {'#7d2728': '#da4545'}
    assert options['border_style'] == 'satin' and options['border_width'] == 3 and options['border_colour'] == '#202020'
    assert settings_from({'border': dict(style='off')}, options)['border_style'] == 'off'
    steps = [dict(t='stitch'), dict(t='trim'), dict(t='trim'), dict(t='color_change'), dict(t='trim')]
    assert per_colour(dict(colors=['#000000', '#ff0000'], steps=steps)) == [
        dict(colour='#000000', cuts=2), dict(colour='#ff0000', cuts=1)]
    assert recent_sewouts(tmp_path) == []


def test_branching_travels_inside_instead_of_cutting():
    from embroiderly.stitch_engine import generate
    # One colour in two parts joined by a later-sewn bridge of another colour.
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkstitch="http://inkstitch.org/namespace" '
           'width="60mm" height="20mm" viewBox="0 0 60 20"><metadata><inkstitch:branching>{}</inkstitch:branching></metadata>'
           '<path d="M 2 2 L 22 2 L 22 18 L 2 18 Z" style="fill:#0000ff" inkstitch:trim_after="true"/>'
           '<path d="M 38 2 L 58 2 L 58 18 L 38 18 Z" style="fill:#0000ff" inkstitch:trim_after="true"/>'
           '<path d="M 21 2 L 39 2 L 39 18 L 21 18 Z" style="fill:#ff0000"/></svg>')
    cuts = lambda text: sum(1 for s in generate(text)['stitches'] if s[2] == 'TRIM')
    assert cuts(svg.format('true')) < cuts(svg.format('false'))


def test_colour_merge_still_applies_when_the_palette_shifts_slightly(tmp_path):
    import numpy as np
    from PIL import Image, ImageDraw
    from embroiderly.preparation import prepare
    image = Image.new('RGB', (200, 100), 'white')
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 10, 90, 90), fill='#c43e3e'); draw.rectangle((110, 10, 190, 90), fill='#7d2728')
    path = tmp_path / 'm.png'; image.save(path)
    options = dict(artwork_type='logo', count=3, height_mm=30, merges={'#7a2526': '#c43e3e'})  # 3-6 units off
    out, _, _ = prepare(path, options)
    colours = {tuple(c) for c in np.asarray(out.convert('RGB')).reshape(-1, 3)}
    assert (0x7d, 0x27, 0x28) not in colours and (0xc4, 0x3e, 0x3e) in colours
