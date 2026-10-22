import math

import numpy as np
from PIL import Image

from embroiderly.auto_digitize import plan
from embroiderly.auto_claude import settings_from
from embroiderly.photo_lines import rows


def test_zigzag_width_follows_darkness_and_rows_snake():
    h, w, scale = 200, 300, .25          # 50 x 75 mm
    dark = np.tile(np.linspace(0, 1, w, dtype=np.float32), (h, 1))   # light left, dark right
    runs = rows(dark, np.ones((h, w), bool), scale)
    assert len(runs) >= 45                                            # about one row per mm
    first = runs[0]
    ys = [p[1] for p in first]
    left = [y for (x, y) in first if x < 15]; right = [y for (x, y) in first if x > 60]
    assert np.ptp(left) < .2 and np.ptp(right) > .7                    # thin line in light, wide zigzag in dark
    # Serpentine: the next row starts where this one ends.
    assert math.dist(runs[0][-1], runs[1][0]) < 2.5
    assert all(.3 <= math.dist(a, b) <= 7 for run in runs for a, b in zip(run, run[1:]))


def test_photos_now_use_one_colour_lines_and_claude_can_choose_it():
    options = plan('photo', {'thread_colours': 8}, {}, (400, 300), {})
    assert options['photo_style'] == 'one_colour' and options['count'] == 2
    assert 'photo_style' not in plan('photo', {}, {'colours': 5}, (400, 300), {})   # asked for colours
    assert 'photo_style' not in plan('logo', {'thread_colours': 3}, {}, (400, 300), {})
    chosen = settings_from({'mode': 'photo_lines', 'photo': dict(row_mm=.8, angle=45, light_thread=True)}, {})
    assert chosen['photo_style'] == 'one_colour' and chosen['photo_row_mm'] == .8 and chosen['photo_light_thread'] is True
    assert 'photo_style' not in settings_from({'mode': 'colour'}, chosen)


def test_a_photo_sews_as_one_thread_and_passes_the_checks(tmp_path):
    from embroiderly.web import create_app
    from embroiderly.auto_digitize import AutoDigitizer
    app = create_app(tmp_path); auto = AutoDigitizer(app, tmp_path)
    y, x = np.mgrid[0:240, 0:320]
    face = 255 - 200 * np.exp(-((x - 160) ** 2 + (y - 120) ** 2) / 4000.0)     # a soft dark blob
    Image.fromarray(np.dstack([face] * 3).astype(np.uint8)).save(tmp_path / 'work/uploads/photo.png')
    result, _ = auto._attempt(tmp_path / 'work/uploads/photo.png',
                              dict(artwork_type='logo', count=2, smooth=2, height_mm=60, photo_style='one_colour'), 2.0, True)
    assert not result.get('error') and not result.get('gate'), result
    assert result['trims'] <= 1 and result['colours'] == 1 and result['stitches'] > 3000


def test_shaded_black_and_white_art_goes_to_photo_lines_not_black_ink():
    from PIL import ImageDraw
    from embroiderly.auto_digitize import classify
    y, x = np.mgrid[0:300, 0:200]
    shaded = (90 + 110 * np.sin(x / 9.0) * np.cos(y / 13.0) ** 2).clip(0, 255).astype(np.uint8)   # engraving-like greys
    kind, facts = classify(Image.fromarray(np.dstack([shaded] * 3)))
    assert kind == 'photo' and facts['shaded'] is True
    assert plan(kind, facts, {}, (200, 300), {})['photo_style'] == 'one_colour'
    clean = Image.new('RGB', (200, 300), 'white')
    ImageDraw.Draw(clean).line((20, 20, 180, 280), fill='black', width=3)                       # clean ink line
    assert classify(clean)[0] == 'ink'
