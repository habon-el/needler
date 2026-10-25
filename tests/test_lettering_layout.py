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
                                  dict(baseline='wave'), dict(sequence='random'),
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
