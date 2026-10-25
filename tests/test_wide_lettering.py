"""Wide lettering columns: big letters stay satin, sewn as split satin (2026-10-25)."""
import math

import pyembroidery as emb
import pytest

from embroiderly import embroidery_fonts, lettering_native as ln, small_lettering as sl
from embroiderly.release_gate import MAX_STITCH_MM, checked_bytes
from embroiderly.stitch_satin import SPLIT_MM, satin


WIDE_TEXT, WIDE_FONT, WIDE_HEIGHT = 'HAB', 'small_font', 44


def build(tmp_path, text, font, height):
    result = ln.build(tmp_path, ln.recipe(dict(text=text, font=font, height_mm=height, align='center',
                                               available_width_mm=400, colour='#202020')))
    return result, (tmp_path/'source.svg').read_text()


def longest_stitch(path):
    pattern, longest, previous = emb.read(str(path)), 0.0, None
    for x, y, command in pattern.stitches:
        if command == emb.STITCH and previous is not None:
            longest = max(longest, math.dist(previous, (x, y))/10)
        previous = (x, y) if command in (emb.STITCH, emb.JUMP, emb.TRIM) else previous
    return longest


@pytest.mark.parametrize('text,font,height', [('HABONIMANA', 'small_font', 30), ('Team', 'graduate', 50)])
def test_big_letters_stay_satin_and_pass_the_release_gate(tmp_path, text, font, height):
    # These were tatami fill before: above ~15 mm every font switched to fill.
    result, source = build(tmp_path, text, font, height)
    assert result['checks_passed'], result['issues']
    assert 'letter_fill' not in source and 'satin_column="true"' in source
    assert abs(result['reports']['dst']['height_mm']-height) <= .2
    assert checked_bytes(tmp_path, 'dst') and checked_bytes(tmp_path, 'pes')
    assert longest_stitch(tmp_path/'design.dst') <= MAX_STITCH_MM


def test_widest_strokes_are_split_satin_on_a_double_zigzag(tmp_path):
    # Strokes over 8 mm wide: every satin stitch split, grid rounding included.
    result, source = build(tmp_path, WIDE_TEXT, WIDE_FONT, WIDE_HEIGHT)
    assert result['checks_passed'], result['issues']
    assert 'letter_fill' not in source and 'zigzag_underlay="double"' in source
    assert result['wide_letters'] is None and checked_bytes(tmp_path, 'dst')
    assert 6.0 < longest_stitch(tmp_path/'design.dst') <= MAX_STITCH_MM


def test_split_satin_that_crosses_a_letter_hole_falls_back_to_fill(tmp_path):
    # Anton's O traced columns let enlarged satin cross the hole: same height, as fill.
    result, source = build(tmp_path, 'O', 'anton', 30)
    assert result['checks_passed'], result['issues']
    assert result['wide_letters'] == 'fill' and 'sewn as fill' in result['message']
    assert 'letter_fill' in source and checked_bytes(tmp_path, 'dst')
    assert abs(result['reports']['dst']['height_mm']-30) <= .2


def test_words_too_wide_for_split_satin_are_still_fill():
    font = dict(sl.fonts()['bungee'], layout={})
    m = embroidery_fonts.text_metrics('ABC', 'bungee')
    top = sl.satin_top(m, font)
    assert math.isclose(m['wide']*top, sl.SPLIT_SATIN_MAX_MM)
    satin_scale = top/font['size']*100
    assert not sl.uses_fill('ABC', font, satin_scale-1)
    assert sl.uses_fill('ABC', font, satin_scale+1)
    # Fonts that trace badly larger keep fill right above their own range.
    alfa = dict(sl.fonts()['alfa_slab_one'], layout={})
    assert sl.uses_fill('DOQ', alfa, alfa['max_scale']*100+1)
    assert not sl.uses_fill('DOQ', alfa, alfa['max_scale']*100)


def test_height_range_and_scale_meet_at_the_split_satin_top():
    font = dict(sl.fonts()['small_font'], layout={})
    m = embroidery_fonts.text_metrics('HAB', 'small_font')
    edge = m['height']*sl.satin_top(m, font)+2*font['pull_mm']
    below, above = sl.scale_for('HAB', font, edge-.2), sl.scale_for('HAB', font, edge+.5)
    assert not sl.uses_fill('HAB', font, below) and sl.uses_fill('HAB', font, above)
    low, high = sl.height_range('HAB', font)
    assert high >= m['height']*sl.FILL_MAX_CAP_MM-.1 and low < edge


def test_split_column_underlay_legs_leave_room_for_the_machine_grid():
    # A 11.6 mm column: the zigzag underlay leg was 6.96 mm and rounded past 7 mm.
    column = [([(0.0, 0.0), (20.0, 0.0)], False), ([(0.0, 11.6), (20.0, 11.6)], False)]
    points = satin(column, .38, contour_underlay=True, zigzag_underlay='double', split=SPLIT_MM)
    assert max(math.dist(p, q) for p, q in zip(points, points[1:])) <= SPLIT_MM-.15+1e-9
