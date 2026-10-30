"""Round 29: block letters' satin follows the outline at corners and ends. The tracer's rails cut
square corners at an angle, stopped short of square terminals and pivoted inner corners inside
the letter, so the coverage check found bare triangles and strips (Anton E, F, Z at 20 mm;
Bungee H, L, U; 26 and 45 letters before)."""
import math

from shapely.geometry import LineString
from shapely.ops import unary_union

from embroiderly import embroidery_fonts as ef, lettering_native as ln, small_lettering
from embroiderly.lettering_coverage import bare_patches
from embroiderly.satin_font import RESOLUTION, _ribbon


def bare_letters(text, font, height):
    settings = ln.recipe(dict(text=text, font=font, height_mm=height, available_width_mm=400))
    return {i['letter'] for i in bare_patches(small_lettering.generate(settings, native=True)['svg'])}


def test_square_corners_ends_and_inner_corners_are_sewn():
    assert bare_letters('EFZ', 'anton', 20) == set()
    assert bare_letters('HLU', 'bungee', 20) == set()
    assert bare_letters('dfhwFJW', 'bowlby_one', 8) == set()


def test_the_e_is_covered_and_no_new_stitch_line_leaves_it():
    path = ef.font_path('anton')
    columns, _, shape = ef.glyph_columns(path, 'E')
    hugged = ef._hug(columns, shape, 1.5/RESOLUTION)
    before = shape.difference(unary_union([_ribbon(a, b, c) for a, b, c, _ in columns])).area
    after = shape.difference(unary_union([_ribbon(a, b, c) for a, b, c, _ in hugged])).area
    assert after < .02*before
    zone = shape.buffer(.25/RESOLUTION)
    for (a, b, *_), (a0, b0, *_) in zip(hugged, columns):
        lines = lambda a, b: list(zip(a, b)) + list(zip(a, a[1:])) + list(zip(b, b[1:]))
        old = {l for l in lines(a0, b0) if math.dist(*l) > 1e-9 and not zone.contains(LineString(l))}
        new = {l for l in lines(a, b) if math.dist(*l) > 1e-9 and not zone.contains(LineString(l))}
        assert new <= old


def test_outline_corners_between_two_points_the_short_way():
    from shapely.geometry import Polygon
    ring = Polygon([(0, 0), (10, 0), (10, 4), (0, 4)]).exterior
    assert ef._outline_between(ring, (8, 0), (10, 2), 10) == [(10.0, 0.0)]
    assert ef._outline_between(ring, (10, 2), (8, 0), 10) == [(10.0, 0.0)]
    assert ef._outline_between(ring, (2, 0), (2, 4), 5) is None  # neighbours only the long way round
