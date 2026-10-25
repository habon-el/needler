"""Lettering layout: spacing, line spacing, arcs, centre-out order, touching joins."""
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
