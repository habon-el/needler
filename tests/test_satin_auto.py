"""Satin automation: auto split, auto spacing, auto underlay, % pull."""
import math

from embroiderly.stitch_satin import (SPLIT_MM, auto_spacing, auto_underlay, compensate, satin,
                                      split_rows)


def column(width, length=20.0):
    return [([(0.0, 0.0), (length, 0.0)], False), ([(0.0, width), (length, width)], False)]


def legs(points):
    return [math.dist(p, q) for p, q in zip(points, points[1:])]


def test_wide_satin_is_split_below_the_limit_with_staggered_holes():
    points = satin(column(12.0), .4, split=SPLIT_MM)
    assert max(legs(points)) <= SPLIT_MM+1e-6
    # Split points inside the column (not on either rail) must not line up.
    inner = sorted({round(y, 2) for _, y in points if .05 < y < 11.95})
    assert len(inner) >= 3


def test_neighbouring_legs_never_share_a_split_hole():
    # Rails along x: each leg crosses y from 0 to 12 and back; compare where the
    # inner holes sit across the column on consecutive legs.
    points = satin(column(12.0, 4.0), .4, split=SPLIT_MM)
    legs_y, current = [], []
    for x, y in points:
        if y < .01 or y > 11.99:
            if current:
                legs_y.append(sorted(current))
            current = []
        else:
            current.append(round(y, 3))
    assert len(legs_y) > 6
    assert all(a != b for a, b in zip(legs_y, legs_y[1:]))


def test_auto_spacing_is_exact_not_rounded_to_samples():
    from embroiderly.stitch_satin import spaced_by_width, pairs
    a, b = [(0.0, 0.0), (20.0, 0.0)], [(0.0, 1.0), (20.0, 1.0)]
    out = spaced_by_width(lambda step: pairs(a, b, [], step), .4)
    gaps = [q[0][0]-p[0][0] for p, q in zip(out, out[1:-1])]
    assert all(math.isclose(g, auto_spacing(.4, 1.0), abs_tol=1e-6) for g in gaps)
    assert auto_spacing(.2, 6.0) <= .2


def test_split_keeps_rails_and_short_stitches_untouched():
    final = [((0, 0), (0, 3)), ((.4, 3), (.4, 0))]
    assert split_rows(final) == [(0, 0), (0, 3), (.4, 3), (.4, 0)]


def test_without_split_a_wide_column_keeps_full_width_stitches():
    assert max(legs(satin(column(12.0), .4))) > 11.9


def test_auto_spacing_opens_narrow_and_tightens_wide_columns():
    assert auto_spacing(.4, 1.0) > .4
    assert auto_spacing(.4, 3.0) == .4
    assert auto_spacing(.4, 8.0) < .4
    narrow = satin(column(1.0), .4, auto_space=True)
    wide = satin(column(4.0), .4, auto_space=True)
    assert len(narrow) < len(wide)


def test_auto_underlay_follows_column_width():
    assert not any(auto_underlay(1.0).values())
    assert auto_underlay(2.0)['center_walk']
    three = auto_underlay(4.0)
    assert three['contour_underlay'] and not three['zigzag_underlay']
    assert auto_underlay(7.0)['zigzag_underlay']
    # A 1 mm column gets no underlay, so it has no more points than plain satin.
    assert len(satin(column(1.0), .4, underlay='auto')) == len(satin(column(1.0), .4))
    assert len(satin(column(4.0), .4, underlay='auto')) > len(satin(column(4.0), .4))


def test_percent_pull_widens_wide_columns_more():
    narrow = compensate([((0, 0), (0, 2))], 0, 10)[0]
    wide = compensate([((0, 0), (0, 6))], 0, 10)[0]
    assert math.isclose(math.dist(*narrow), 2.2)
    assert math.isclose(math.dist(*wide), 6.6)
