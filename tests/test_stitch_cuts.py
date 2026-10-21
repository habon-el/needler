import math

from PIL import Image, ImageDraw
from shapely.geometry import box

from embroiderly.stitch_cuts import apply


def test_exact_cut_removes_inside_ties_off_and_resumes():
    stitches = [[0, 0, 'JUMP'], [0, 0, 'STITCH']] + [[x, 0, 'STITCH'] for x in range(20, 401, 20)] + [[400, 0, 'END']]
    out, removed = apply(stitches, [box(150, -10, 250, 10)])
    assert removed == 6                                             # segments ending 160..260 touch the area
    kinds = [s[2] for s in out]
    trim, jump = kinds.index('TRIM'), kinds.index('JUMP', 1)
    assert trim < jump and kinds.count('TRIM') == 1
    assert out[trim][0] <= 150 and out[jump][0] >= 250             # cut before the area, resume after it
    sewn = [s for s in out if s[2] == 'STITCH']
    assert not any(150 < s[0] < 250 for s in sewn)                   # nothing sewn inside
    # Tie-off before the cut and tie-in after: a short back-and-forth.
    assert out[trim - 2][0] == out[trim][0] - 6 and out[jump + 2][0] == out[jump][0] + 6
    assert apply(stitches, []) == (stitches, 0)


def test_removal_is_saved_with_the_design_and_passes_the_checks(tmp_path):
    from embroiderly.auto_digitize import AutoDigitizer
    from embroiderly.web import create_app
    app = create_app(tmp_path); auto = AutoDigitizer(app, tmp_path)
    image = Image.new('RGB', (300, 200), 'white')
    ImageDraw.Draw(image).rectangle((40, 40, 260, 160), fill='#1d4f91')
    image.save(tmp_path / 'work/uploads/block.png')
    base = dict(artwork_type='logo', count=2, height_mm=40)
    whole, _ = auto._attempt(tmp_path / 'work/uploads/block.png', base, .8)
    # Areas are drawn on the prepared picture (the frame the editor shows), which may be upscaled.
    k = Image.open(tmp_path / 'work/uploads' / whole['prepared']).width / 300
    area = [[x * k, y * k] for x, y in ((120, 30), (180, 30), (180, 170), (120, 170))]
    cut = dict(base, stitch_cuts=[dict(points=area)])
    exact, _ = auto._attempt(tmp_path / 'work/uploads/block.png', cut, .8)
    assert not exact.get('error') and not exact.get('gate'), exact
    import json
    plan = json.loads((tmp_path / 'work/inkstitch-preview' / exact['prepared'].rsplit('.', 1)[0] / 'engine-plan.json').read_text())
    # About a quarter of the fill is gone; every fill row crossing the area now ends with a tie-off and a cut.
    assert plan['extras']['stitches_removed'] > whole['stitches'] * .12
    assert exact['trims'] > whole['trims'] + 20
    erase = dict(base, edits=[dict(kind='erase', shape='polygon', radius=1, points=area)])
    restitched, _ = auto._attempt(tmp_path / 'work/uploads/block.png', erase, .8, True)
    assert not restitched.get('error') and not restitched.get('gate'), restitched
    # Rebuilt around the hole: almost nothing is sewn inside the removed band any more.
    plan = restitched['playback']; ox = plan['origin_mm'][0]; mm = plan['height_mm'] / Image.open(
        tmp_path / 'work/uploads' / restitched['prepared']).height
    xs = [(st['x'] + ox) / mm for st in plan['steps'] if st['t'] == 'stitch']
    assert sum(125 * k < x < 175 * k for x in xs) < len(xs) * .06


def test_a_click_selects_the_whole_area_with_its_holes(tmp_path):
    from embroiderly.problems import area_at
    from embroiderly.preparation import edit_brush
    image = Image.new('RGBA', (200, 200), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.ellipse((20, 20, 180, 180), fill='#f4ead7'); draw.rectangle((80, 80, 120, 120), fill='#e09a1f')
    image.save(tmp_path / 'prepared_x.png')
    ring = area_at(tmp_path / 'prepared_x.png', 40, 100)        # the cream ring around the square
    assert ring['colour'] == '#f4ead7' and len(ring['holes']) == 1
    brush = edit_brush(dict(kind='erase', shape='polygon', radius=1, **ring), 200, 200)
    assert brush[100, 40] and not brush[100, 100]                 # the ring goes, the square stays
    assert area_at(tmp_path / 'prepared_x.png', 100, 100)['holes'] == []
