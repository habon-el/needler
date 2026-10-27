"""Couching: a triple-stitch cord with ties across it, as a subject border."""
import math

import pytest

from embroiderly.stitch_paths import couching

LINE = [(0.0, 0.0), (30.0, 0.0)]


def legs(points):
    return [math.dist(p, q) for p, q in zip(points, points[1:])]


def test_cord_is_sewn_three_times_then_tied_on_the_way_back():
    points = couching(LINE, 3.0, 1.6, 3.0)
    # The way back starts at the far end, just before its first tie leaves the line.
    turn = next(i for i, (_, y) in enumerate(points) if y != 0)-1
    cord, back = points[:turn+1], points[turn:]
    # The cord stays on the line and covers every stitch three times.
    assert all(y == 0 for _, y in cord)
    assert sum(legs(cord)) == pytest.approx(3*30.0, abs=.01)
    # Ties cross the cord, half the width either side, about every 3 mm.
    tops = [x for x, y in back if y == pytest.approx(.8)]
    bottoms = [x for x, y in back if y == pytest.approx(-.8)]
    assert len(tops) == len(bottoms) == 11
    assert max(b-a for a, b in zip(sorted(tops), sorted(tops)[1:])) <= 3.0+1e-6
    assert points[-1] == pytest.approx(LINE[0])


def test_couching_stitches_stay_in_the_safe_range():
    ring = [(10+8*math.cos(i*math.pi/60), 10+8*math.sin(i*math.pi/60)) for i in range(120)]
    points = couching(ring+[ring[0]], 3.0, 1.6, 3.0)
    assert min(legs(points)) >= .45 and max(legs(points)) <= 3.0+1e-6


def test_wider_spacing_means_fewer_ties():
    def ties(spacing):
        return sum(1 for _, y in couching(LINE, 3.0, 1.6, spacing) if y > .7)
    assert ties(2.0) > ties(3.0) > ties(5.0)


def test_couching_border_generates_and_passes_the_release_gate(tmp_path):
    from test_stitch_types_engine import design
    from embroiderly.release_gate import checked_bytes
    _, svg = design(tmp_path, {'border_style': 'couching', 'border_width': 1.6, 'border_colour': '#202020'})
    assert 'outline_style="couching"' in svg
    assert checked_bytes(tmp_path/'out', 'dst')
