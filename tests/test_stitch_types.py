"""Stitch types: decorative outlines, step/gradient/radial fills, shortening."""
import math

from shapely.geometry import Point, Polygon, box

from embroiderly.stitch_fills import STEP_PATTERN, gradient, radial, step_fill
from embroiderly.stitch_paths import (backstitch, blanket, inward_side, path_length, stemstitch,
                                      zigzag_outline)
from embroiderly.stitch_satin import shorten_inner

LINE = [(0.0, 0.0), (20.0, 0.0)]
SQUARE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]


def legs(points):
    return [math.dist(p, q) for p, q in zip(points, points[1:])]


def test_backstitch_steps_forward_and_back_and_reaches_both_ends():
    points = backstitch(LINE, 2.5, .3)
    assert points[0] == LINE[0] and math.isclose(points[-1][0], 20.0)
    xs = [x for x, _ in points]
    assert any(b < a for a, b in zip(xs, xs[1:]))          # some stitches go back
    assert max(legs(points)) <= 2.5+1e-6
    assert min(legs(points)) >= .45


def test_stemstitch_overlaps_across_its_band():
    points = stemstitch(LINE, 3.0, 1.2)
    ys = {round(y, 6) for _, y in points}
    assert ys == {-.6, .6}
    assert path_length(points) > 2*path_length(LINE)       # overlapping slants


def tips(points, ring):
    edge = Polygon(ring).exterior
    return [p for p in points if edge.distance(Point(p)) > 1e-6]


def test_blanket_spikes_point_into_a_closed_shape_either_way_round():
    inside = Polygon(SQUARE)
    for ring in (SQUARE, SQUARE[::-1]):
        found = tips(blanket(ring, 2.0, 2.0, inward_side(ring[:-1])), ring)
        assert found and all(inside.contains(Point(p)) for p in found)


def test_zigzag_outline_alternates_sides():
    points = zigzag_outline(LINE, 1.0, 2.0)
    signs = [y > 0 for _, y in points]
    assert all(a != b for a, b in zip(signs, signs[1:]))
    assert all(math.isclose(abs(y), 1.0) for _, y in points)


def test_step_fill_covers_the_area_with_a_stepped_pattern():
    shape = box(0, 0, 20, 10)
    runs = step_fill(shape, 0, .4, 3.5, underlay=False)
    assert runs and all(shape.buffer(.01).contains(Point(p)) for r in runs for p in r)
    assert len(set(STEP_PATTERN)) > 2
    inner = {round(p[0] % 3.5, 1) for r in runs for p in r if .5 < p[0] < 19.5}
    assert len(inner) >= 4


def test_gradient_rows_open_up_across_the_area():
    shape = box(0, 0, 20, 20)
    runs = gradient(shape, 0, .4, 1.6)
    ys = sorted({round(y, 2) for r in runs for x, y in r if 2 < x < 18})
    gaps = [b-a for a, b in zip(ys, ys[1:]) if b-a > .05]
    assert gaps[0] < .6 and gaps[-1] > 1.2
    assert all(shape.buffer(.05).contains(Point(p)) for r in runs for p in r)


def test_radial_rays_meet_at_the_centre_without_piling_up():
    shape = Point(0, 0).buffer(10, 64)
    runs = radial(shape, .4, 3.0)
    assert runs and all(shape.buffer(.05).contains(Point(p)) for r in runs for p in r)
    near_centre = sum(1 for r in runs for p in r if math.dist(p, (0, 0)) < 1.0)
    rim = sum(1 for r in runs for p in r if math.dist(p, (0, 0)) > 9.5)
    assert near_centre < rim/4
    # A ring cannot be reached from its centre: the caller falls back to tatami.
    assert radial(shape.difference(Point(0, 0).buffer(8)), .4, 3.0) is None


def test_shortening_pulls_back_inner_stitches_on_tight_curves():
    # Inner rail barely moves (a tight turn) while the outer rail sweeps round.
    final = [((0.0, 0.0), (math.cos(t)*4, math.sin(t)*4)) for t in [i*.2 for i in range(8)]]
    short = shorten_inner(final)
    changed = [i for i, (a, b) in enumerate(zip(final, short)) if a != b]
    assert changed and all(i % 2 for i in changed)
    straight = [((float(x), 0.0), (float(x), 3.0)) for x in range(8)]
    assert shorten_inner(straight) == straight


def test_double_zigzag_underlay_on_very_wide_columns():
    from embroiderly.stitch_satin import auto_underlay, satin
    assert auto_underlay(9.0)['zigzag_underlay'] == 'double' and auto_underlay(6.5)['zigzag_underlay'] is True
    column = [([(0.0, 0.0), (30.0, 0.0)], False), ([(0.0, 9.0), (30.0, 9.0)], False)]
    single = satin(column, .4, zigzag_underlay=True)
    double = satin(column, .4, zigzag_underlay='double')
    assert len(double) > len(single)


def test_sharp_satin_corners_are_capped_not_refused():
    import numpy as np
    from embroiderly.borders import satin_rails
    # A long thin triangle: its sharp tip used to be refused for satin.
    tip = [(0.0, 0.0), (40.0, 4.0), (40.0, -4.0), (0.0, 0.0)]
    rails = satin_rails(tip, .8)
    reach = max(float(np.min(np.linalg.norm(np.asarray(r)-np.asarray(tip[:-1])[:, None], axis=2), axis=0).max())
                for pair in rails for r in pair)
    assert reach <= 2*.8+1e-6
