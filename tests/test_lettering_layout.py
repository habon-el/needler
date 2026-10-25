"""Lettering layout: spacing, line spacing, arcs, centre-out order, touching joins."""
import math
import re
import tempfile
from pathlib import Path

import pytest

from embroiderly import embroidery_fonts as ef
from embroiderly import lettering_native as ln
from embroiderly import small_lettering as sl


def glyph_labels(svg):
    return [a or b for a, b in re.findall(
        r'letter-group="glyph"[^>]*label="([^"]+)"|label="([^"]+)"[^>]*letter-group="glyph"', svg)]


def coords(svg):
    return [(float(x), float(y)) for x, y in re.findall(r'(-?[\d.]+),(-?[\d.]+)', svg)]


@pytest.mark.parametrize('body', [dict(letter_spacing_mm=20), dict(line_spacing_percent=40),
                                  dict(baseline='zigzag'), dict(sequence='random'),
                                  dict(baseline='arc_over', arc_radius_mm=2)])
def test_layout_options_are_checked(body):
    with pytest.raises(ValueError):
        sl.layout_options(body)


def test_letter_spacing_widens_the_line():
    plain = ef.layout('ABC', 'graduate', 200)
    spaced = ef.layout('ABC', 'graduate', 200, letter_spacing_mm=3)
    width = lambda svg: float(re.search(r'width="([\d.]+)"', svg).group(1))
    assert width(spaced) > width(plain)+2*3/ef.PX_MM-1e-3


def test_line_spacing_reaches_the_height_solver():
    assert ef.text_metrics('A\nB', 'graduate', 1.5)['height'] > ef.text_metrics('A\nB', 'graduate')['height']


@pytest.mark.parametrize('baseline', ['arc_over', 'arc_under'])
def test_arc_letters_turn_and_stay_on_the_page(baseline):
    svg = ef.layout('CHAMPIONS', 'graduate', 250, baseline=baseline, radius_mm=40)
    points = coords(svg)
    assert min(x for x, _ in points) >= 0 and min(y for _, y in points) >= 0
    assert svg != ef.layout('CHAMPIONS', 'graduate', 250)


def test_arcs_need_one_line_and_room():
    with pytest.raises(ValueError):
        ef.layout('A\nB', 'graduate', 200, baseline='arc_over', radius_mm=40)
    with pytest.raises(ValueError):
        ef.layout('CHAMPIONSHIP', 'graduate', 400, baseline='arc_over', radius_mm=5)


def test_centre_out_sews_the_middle_letter_first():
    assert glyph_labels(ef.layout('ABCDE', 'graduate', 200, sequence='centre')) == ['C', 'D', 'E', 'B', 'A']


def test_touching_script_letters_are_joined_instead_of_cut():
    assert 'id="join-' in ef.layout('Hello', 'pacifico', 300)
    # Block letters with fabric between them keep every cut.
    assert 'id="join-' not in ef.layout('HELLO', 'graduate', 300)


def test_arc_lettering_passes_the_release_gate():
    body = dict(text='CHAMPIONS', font='graduate', height_mm=10, available_width_mm=300, colour='#202020',
                baseline='arc_over', arc_radius_mm=50, letter_spacing_mm=.5)
    settings = ln.recipe(body)
    assert settings['baseline'] == 'arc_over' and settings['arc_radius_mm'] == 50
    with tempfile.TemporaryDirectory() as folder:
        assert ln.build(Path(folder), settings)['checks_passed']


def test_plain_recipes_keep_their_old_cache_keys():
    body = dict(text='Hi', font='graduate', height_mm=10, available_width_mm=50, colour='#202020')
    assert set(ln.recipe(body)) == {'text', 'font', 'height_mm', 'align', 'available_width_mm', 'colour'}


def test_curve_in_degrees_follows_the_length_of_the_words():
    """Curve: how far round the circle the words reach; the radius follows the words' length."""
    short, long_ = (ef.layout(text, 'graduate', 250, baseline='arc_over', arc_degrees=120) for text in ('TEAM', 'CHAMPIONS'))
    for svg in (short, long_):
        points = coords(svg)
        assert min(x for x, _ in points) >= 0 and min(y for _, y in points) >= 0
    # More curve bends the same words further: the line gets taller and narrower.
    flat, bent = (coords(ef.layout('CHAMPIONS', 'graduate', 250, baseline='arc_under', arc_degrees=d)) for d in (30, 180))
    span = lambda pts, i: max(p[i] for p in pts)-min(p[i] for p in pts)
    assert span(bent, 1) > span(flat, 1) and span(bent, 0) < span(flat, 0)
    with pytest.raises(ValueError):
        sl.layout_options(dict(baseline='arc_over', arc_degrees=400))
    settings = ln.recipe(dict(text='CHAMPIONS', font='graduate', height_mm=10, available_width_mm=300,
                              colour='#202020', baseline='arc_under', arc_degrees=90))
    assert settings['arc_degrees'] == 90 and 'arc_radius_mm' not in settings
    with tempfile.TemporaryDirectory() as folder:
        assert ln.build(Path(folder), settings)['checks_passed']


@pytest.mark.parametrize('frame', ['circle', 'oval', 'square', 'diamond', 'hexagon', 'shield', 'heart'])
def test_monogram_frames_pass_the_release_gate(frame):
    body = dict(text='JAM', font='graduate', height_mm=14, available_width_mm=300, colour='#202020',
                frame=frame, frame_mm=2.5, classic=True)
    settings = ln.recipe(body)
    assert settings['frame'] == frame and settings['classic'] is True
    svg = ef.layout('JAM', 'graduate', 250, frame=frame, classic=True)
    assert 'label="frame"' in svg or "label='frame'" in svg or 'frame' in svg
    with tempfile.TemporaryDirectory() as folder:
        result = ln.build(Path(folder), settings)
    assert result['checks_passed'], result.get('issues')
    # The frame surrounds the letters: the design is wider than the letters alone.
    with tempfile.TemporaryDirectory() as folder:
        plain = ln.build(Path(folder), ln.recipe(dict(body, frame='none')))
    assert result['reports']['dst']['width_mm'] > plain['reports']['dst']['width_mm']+4


def test_classic_monogram_makes_the_middle_initial_bigger():
    heights = {}
    for classic in (False, True):
        svg = ef.layout('JAM', 'graduate', 250, classic=classic)
        heights[classic] = max(y for _, y in coords(svg))-min(y for _, y in coords(svg))
    assert heights[True] > heights[False]*1.2
    for bad in ('JAMES', 'J\nM'):
        with pytest.raises(ValueError, match='classic monogram'):
            ef.layout(bad, 'graduate', 250, classic=True)
    with pytest.raises(ValueError, match='3D puff'):
        ef.layout('JAM', 'graduate', 250, frame='circle', puff=True)


def ornament_bounds(svg):
    """Bounds of the ornament's satin rails (px) in a layout SVG."""
    group = svg[svg.index('label="ornament"'):]
    points = coords(' '.join(re.findall(r' d="([^"]+)"', group)))
    xs, ys = [x for x, _ in points], [y for _, y in points]
    return min(xs), min(ys), max(xs), max(ys)


@pytest.mark.parametrize('ornament', ['crown', 'laurel', 'swirls', 'divider'])
def test_monogram_ornaments_pass_the_release_gate(ornament):
    body = dict(text='JAM', font='graduate', height_mm=14, available_width_mm=300, colour='#202020',
                classic=True, ornament=ornament)
    settings = ln.recipe(body)
    assert settings['ornament'] == ornament
    with tempfile.TemporaryDirectory() as folder:
        result = ln.build(Path(folder), settings)
    assert result['checks_passed'], result.get('issues')
    # Every letter is still there, and the ornament makes the design bigger than the letters.
    assert result['source_glyphs'] == 3
    plain = ef.layout('JAM', 'graduate', 250, classic=True)
    svg = ef.layout('JAM', 'graduate', 250, classic=True, ornament=ornament)
    size = lambda s: [float(v) for v in re.search(r'width="([\d.]+)" height="([\d.]+)"', s).groups()]
    assert sum(size(svg)) > sum(size(plain))+3/ef.PX_MM


def test_ornament_with_a_frame_and_small_words_pass_the_release_gate():
    for body in (dict(text='JAM', height_mm=14, classic=True, frame='circle', ornament='laurel'),
                 dict(text='Smith', height_mm=5, ornament='swirls')):
        settings = ln.recipe(dict(body, font='graduate', available_width_mm=300, colour='#202020'))
        with tempfile.TemporaryDirectory() as folder:
            result = ln.build(Path(folder), settings)
        assert result['checks_passed'], (body, result.get('issues'))


def test_ornament_is_sewn_last_in_satin_with_a_cut_after_each_piece():
    svg = ef.layout('JAM', 'graduate', 250, classic=True, frame='circle', ornament='laurel')
    assert svg.index('label="frame"') < svg.index('label="ornament"')
    assert svg.rindex('letter-group="glyph"') < svg.index('label="ornament"')
    group = svg[svg.index('label="ornament"'):]
    paths = re.findall(r'<path [^>]*>', group)
    satins = [p for p in paths if 'satin_column="true"' in p]
    assert satins and all('satin_pairs="indexed"' in p for p in satins)
    # Everything else is travel inside the piece; two branches, so two cuts at most.
    assert all('running_stitch' in p for p in paths if p not in satins)
    assert 1 <= sum('trim_after="true"' in p for p in paths) <= 2
    # Satin widths stay sewable: no rung wider than 3.5 mm plus rounding.
    for path in satins:
        a, b = [coords(part) for part in re.search(r' d="([^"]+)"', path).group(1).split('M ')[1:]]
        widths = [math.dist(p, q)*ef.PX_MM for p, q in zip(a, b)]
        assert .79 <= min(widths) and max(widths) <= 3.51


@pytest.mark.parametrize('ornament', ['crown', 'laurel', 'swirls', 'divider'])
def test_ornaments_scale_with_the_text(ornament):
    small = ornament_bounds(ef.layout('JAM', 'graduate', 250, classic=True, ornament=ornament))
    big = ornament_bounds(ef.layout('JAM', 'graduate', 500, classic=True, ornament=ornament))
    for i in (0, 1):
        ratio = (big[i+2]-big[i])/(small[i+2]-small[i])
        assert 1.6 < ratio < 2.4, (ornament, i, ratio)


def test_ornament_follows_curved_words():
    svg = ef.layout('MILLER', 'graduate', 250, baseline='arc_over', arc_degrees=90, ornament='crown')
    assert 'label="ornament"' in svg


def test_ornament_values_are_checked():
    for bad in ('star', '', None, 3):
        with pytest.raises(ValueError, match='ornament'):
            sl.layout_options(dict(ornament=bad))
        with pytest.raises(ValueError, match='ornament'):
            ln.recipe(dict(text='JAM', font='graduate', height_mm=14, ornament=bad))
    with pytest.raises(ValueError, match='ornament'):
        ef.layout('JAM', 'graduate', 250, ornament='star')
    with pytest.raises(ValueError, match='3D puff'):
        ef.layout('JAM', 'graduate', 250, ornament='crown', puff=True)
    # No ornament adds nothing to the recipe, so earlier saved lettering keeps its cache key.
    assert 'ornament' not in ln.recipe(dict(text='JAM', font='graduate', height_mm=14))
    problems = sl.advice(dict(text='JAM', font='graduate', height_mm=30, ornament='crown', puff=True,
                              available_width_mm=300))['problems']
    assert any(p.get('fix', {}).get('set') == {'ornament': 'none'} for p in problems)


def glyph_centres(svg):
    """Centre of each letter's points, by label, in sewing order."""
    centres = []
    for label, body in re.findall(r'letter-group="glyph"[^>]*label="([^"]+)"[^>]*>(.*?)</g>', svg, re.S):
        points = coords(' '.join(re.findall(r' d="([^"]+)"', body)))
        centres.append((label, sum(x for x, _ in points)/len(points), sum(y for _, y in points)/len(points)))
    return centres


@pytest.mark.parametrize('body', [dict(baseline='circle', circle_mm=5), dict(baseline='circle', circle_mm='big'),
                                  dict(baseline='wave', wave_percent=40), dict(baseline='wave', wave_percent=1),
                                  dict(fit_length_mm=2), dict(fit_length_mm='long'), dict(fit_length_mm=5000)])
def test_new_baseline_values_are_checked(body):
    with pytest.raises(ValueError):
        sl.layout_options(body)


def test_full_circle_puts_the_top_line_over_the_top_and_the_bottom_line_along_the_bottom():
    svg = ef.layout('TEAM SPIRIT\nSINCE 99', 'graduate', 250, baseline='circle', circle_mm=60)
    centres = glyph_centres(svg)
    top, bottom = centres[:10], centres[10:]
    # Top words read clockwise over the top; bottom words left to right along the bottom.
    assert max(y for *_, y in top) < min(y for *_, y in bottom)
    assert [x for _, x, _ in top] == sorted(x for _, x, _ in top)
    assert [x for _, x, _ in bottom] == sorted(x for _, x, _ in bottom)
    width, height = (float(v)*ef.PX_MM for v in re.search(r'width="([\d.]+)" height="([\d.]+)"', svg).groups())
    cap = ef.FONTS['graduate']['size']*2.5
    # The ring: the circle plus a capital each side (and half an em of margin).
    assert 60+2*cap-1 < height < 60+2*cap+cap*2
    # One line round a full circle is allowed; three lines, a circle too small or lines that meet are not.
    ef.layout('CHAMPIONS', 'graduate', 250, baseline='circle', circle_mm=40)
    for text, size in (('A\nB\nC', 60), ('CHAMPIONS', 10), ('CHAMPIONSHIP FINAL\nWINNERS OF THE YEAR', 40)):
        with pytest.raises(ValueError):
            ef.layout(text, 'graduate', 250, baseline='circle', circle_mm=size)


def test_full_circle_with_two_lines_passes_the_release_gate():
    body = dict(text='TEAM SPIRIT\nSINCE 1999', font='graduate', height_mm=8, available_width_mm=300,
                colour='#202020', baseline='circle', circle_mm=70)
    settings = ln.recipe(body)
    assert settings['baseline'] == 'circle' and settings['circle_mm'] == 70
    # The height is the letters' height, as on one line (the two lines share one ring).
    assert sl.validate(body)[2] == pytest.approx(sl.validate(dict(body, text='TEAM SPIRIT SINCE 1999', baseline='straight'))[2])
    with tempfile.TemporaryDirectory() as folder:
        result = ln.build(Path(folder), settings)
    assert result['checks_passed'], result.get('issues')
    assert sl.laid_out_width(body) == pytest.approx(result['reports']['dst']['width_mm'], abs=.6)
    assert result['reports']['dst']['height_mm'] == pytest.approx(70+2*8, abs=2)


def test_fixed_length_measures_the_requested_length_and_passes_the_release_gate():
    body = dict(text='CHAMPIONS', font='graduate', height_mm=8, available_width_mm=300, colour='#202020',
                fit_length_mm=80, letter_spacing_mm=3)
    settings = ln.recipe(body)
    # The spacing follows from the length; a spacing typed earlier is not used.
    assert settings['fit_length_mm'] == 80 and 'letter_spacing_mm' not in settings
    with tempfile.TemporaryDirectory() as folder:
        result = ln.build(Path(folder), settings)
    assert result['checks_passed'], result.get('issues')
    assert result['reports']['dst']['width_mm'] == pytest.approx(80, abs=.3)
    plain = sl.laid_out_width(dict(body, fit_length_mm=None, letter_spacing_mm=0))
    for length in (plain-4, plain+15):   # squeezed and spread
        assert sl.laid_out_width(dict(body, fit_length_mm=length)) == pytest.approx(length, abs=.4)


def test_fixed_length_refuses_overlapping_or_scattered_letters():
    with pytest.raises(ef.LengthError) as squeezed:
        ef.layout('CHAMPIONS', 'graduate', 250, fit_length_mm=30)
    assert 'overlap' in str(squeezed.value) and 30 < squeezed.value.nearest < 80
    # The length it offers is one the words can have.
    ef.layout('CHAMPIONS', 'graduate', 250, fit_length_mm=squeezed.value.nearest+.1)
    with pytest.raises(ef.LengthError) as spread:
        ef.layout('CHAMPIONS', 'graduate', 250, fit_length_mm=400)
    assert 'letter' in str(spread.value) and spread.value.nearest < 400
    ef.layout('CHAMPIONS', 'graduate', 250, fit_length_mm=spread.value.nearest-.1)
    # Script letters that already touch cannot be pushed into each other.
    with pytest.raises(ef.LengthError):
        ef.layout('Hello', 'pacifico', 300, fit_length_mm=10)
    for text, extra in (('A\nB', {}), ('A', {}), ('JAM', dict(classic=True))):
        with pytest.raises(ValueError):
            ef.layout(text, 'graduate', 250, fit_length_mm=40, **extra)


def test_fixed_length_along_a_curve_and_a_wave_pass_the_release_gate():
    """Along a smile the length is measured along the curve, so the line is narrower across."""
    smile = ef.layout('CHAMPIONS', 'graduate', 250, baseline='arc_under', arc_degrees=120, fit_length_mm=90)
    wide = lambda svg: (lambda xs: max(xs)-min(xs))([x for x, _ in coords(svg)])*ef.PX_MM
    assert wide(smile) < 90-5
    body = dict(text='CHAMPIONS', font='graduate', height_mm=8, available_width_mm=300, colour='#202020',
                baseline='wave', wave_percent=6, fit_length_mm=90)
    settings = ln.recipe(body)
    assert settings['wave_percent'] == 6 and settings['fit_length_mm'] == 90
    with tempfile.TemporaryDirectory() as folder:
        result = ln.build(Path(folder), settings)
    assert result['checks_passed'], result.get('issues')
    assert sl.laid_out_width(body) == pytest.approx(result['reports']['dst']['width_mm'], abs=.6)
    assert result['reports']['dst']['width_mm'] < 90


def test_wave_rises_and_falls_and_refuses_bends_that_make_letters_touch():
    centres = glyph_centres(ef.layout('CHAMPIONS', 'graduate', 250, baseline='wave', wave_percent=6))
    ys = [y for *_, y in centres]
    # Up first (smaller y), then down below the line, then back.
    assert ys.index(min(ys)) < ys.index(max(ys))
    assert max(ys)-min(ys) > 4/ef.PX_MM
    with pytest.raises(ValueError, match='gentler wave'):
        ef.layout('Waves', 'graduate', 250, baseline='wave', wave_percent=25)
    with pytest.raises(ValueError):
        ef.layout('A\nB', 'graduate', 250, baseline='wave')
