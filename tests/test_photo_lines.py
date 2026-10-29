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


def _sunset(h=240, w=320):
    """Orange sky over a blue sea, a dark sun-shadow band and a white highlight."""
    y, x = np.mgrid[0:h, 0:w]
    rgb = np.zeros((h, w, 3), np.float64)
    rgb[:] = (240, 140, 40)
    rgb[y > h // 2] = (30, 70, 160)
    rgb[(y > h // 2 - 15) & (y < h // 2 + 15)] = (40, 30, 30)
    rgb[(x - 60) ** 2 + (y - 50) ** 2 < 600] = (255, 255, 255)
    return rgb


def test_several_threads_are_picked_and_each_pixel_is_a_mix_of_them():
    from embroiderly.photo_lines import threads
    rgb = _sunset()
    alpha = np.ones(rgb.shape[:2], bool)
    colours, shares = threads(rgb, alpha, 4)
    assert len(colours) == len(shares) == 4 and len(set(colours)) == 4
    total = sum(shares)
    assert np.allclose(total, 1, atol=1e-4)                              # every pixel fully sewn
    # The sea is sewn mostly by the bluest thread.
    blue = max(range(4), key=lambda i: int(colours[i][5:7], 16) - int(colours[i][1:3], 16))
    assert shares[blue][200, 200] > .8 and shares[blue][20, 300] < .2
    # Open: the white highlight is left to the fabric, no thread is spent on it.
    colours, shares = threads(rgb, alpha, 3, fabric=(255, 255, 255))
    assert sum(s[50, 60] for s in shares) < .2 and '#ffffff' not in colours


def test_open_rows_leave_light_areas_bare():
    h, w, scale = 200, 300, .25
    dark = np.tile(np.linspace(0, 1, w, dtype=np.float32), (h, 1))
    import cv2
    from embroiderly.photo_lines import OPEN_LIGHT, OPEN_WIDTH
    mask = cv2.GaussianBlur(dark, (0, 0), 2) > OPEN_LIGHT
    runs = rows(dark, mask, scale, 1.0, 0, OPEN_WIDTH)
    xs = [p[0] for run in runs for p in run]
    assert min(xs) > OPEN_LIGHT * w * scale * .9                         # the light side stays empty
    first = max(runs, key=len)
    assert np.ptp([p[1] for p in first]) <= OPEN_WIDTH + .05              # narrow zigzag: fabric between rows


def test_multi_colour_and_open_photos_sew_and_pass_the_checks(tmp_path):
    from embroiderly.web import create_app
    from embroiderly.auto_digitize import AutoDigitizer
    app = create_app(tmp_path); auto = AutoDigitizer(app, tmp_path)
    Image.fromarray(_sunset().astype(np.uint8)).save(tmp_path / 'work/uploads/sunset.png')
    base = dict(artwork_type='logo', count=2, smooth=2, height_mm=60)
    several, _ = auto._attempt(tmp_path / 'work/uploads/sunset.png',
                               dict(base, photo_style='multi_colour', photo_colours=3), 2.0, True)
    assert not several.get('error') and not several.get('gate'), several
    assert several['colours'] == 3
    opened, _ = auto._attempt(tmp_path / 'work/uploads/sunset.png',
                              dict(base, photo_style='multi_colour', photo_colours=3, photo_open=True), 2.0, True)
    assert not opened.get('error') and not opened.get('gate'), opened
    assert opened['stitches'] < several['stitches']                       # fabric shows: fewer stitches
    one_open, _ = auto._attempt(tmp_path / 'work/uploads/sunset.png',
                                dict(base, photo_style='one_colour', photo_open=True), 2.0, True)
    assert not one_open.get('error') and not one_open.get('gate'), one_open
    assert one_open['colours'] == 1


def test_claude_can_choose_a_multi_colour_open_photo():
    chosen = settings_from({'mode': 'photo_colour', 'photo': dict(colours=5, open=True)}, {})
    assert chosen['photo_style'] == 'multi_colour' and chosen['photo_colours'] == 5 and chosen['photo_open'] is True
