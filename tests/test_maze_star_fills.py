"""Maze fill (one winding line with square corners) and star fill (a star-shaped spiral)."""
import math

import pytest
from shapely.geometry import Point, Polygon

from embroiderly.region_stitches import CATALOG
from embroiderly.stitch_fills import STAR_INNER, STAR_POINTS, maze, star

DISC = Point(20, 20).buffer(15)
RING = DISC.difference(Point(20, 20).buffer(5))
BAND = Polygon([(0, 0), (40, 0), (40, 12), (0, 12)])


def legs(run):
    return [math.dist(p, q) for p, q in zip(run, run[1:])]


def test_maze_and_star_are_listed_area_styles():
    ids = [key for key, _, _ in CATALOG]
    assert 'maze' in ids and 'star' in ids


@pytest.mark.parametrize('fill', (maze, star))
@pytest.mark.parametrize('shape', (DISC, RING, BAND))
def test_fills_are_one_line_inside_the_area(fill, shape):
    runs = fill(shape)
    assert len(runs) == 1
    inside = shape.buffer(.05)
    assert all(inside.contains(Point(p)) for p in runs[0])
    assert max(legs(runs[0])) <= 2.5


def test_maze_turns_only_square_corners_on_a_lane_grid():
    run = maze(DISC)[0]
    assert min(legs(run)) >= 1.0-1e-6
    # Every stitch runs straight across or straight down: no rounded or slanted turns.
    assert all(abs(p[0]-q[0]) < 1e-6 or abs(p[1]-q[1]) < 1e-6 for p, q in zip(run, run[1:]))


def test_maze_has_long_corridors():
    def longest(straight):
        from embroiderly.stitch_fills import meander
        run = meander(BAND, 2.0, 1.5, .45, smooth=0, tolerance=.05, straight=straight)[0]
        best = cur = 0.0
        for a, b, c in zip(run, run[1:], run[2:]):
            same = abs((b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0])) < 1e-6
            cur = cur+math.dist(a, b) if same else 0.0
            best = max(best, cur)
        return best
    assert longest(.7) > longest(0)


def test_star_points_up_and_spirals_out_evenly():
    run = star(Point(0, 0).buffer(30), 1.6, 50)[0]
    far = [p for p in run if math.dist(p, (0, 0)) > 5]
    # The points of a turn sit on a five-point star with one straight up (y grows downward).
    tip = min(far[:40], key=lambda p: p[1])
    assert abs(math.degrees(math.atan2(tip[0], -tip[1]))) % (360/STAR_POINTS) == pytest.approx(0, abs=4)
    # Turns at the points are 1.6 mm apart; the inner corners half as far.
    tips = sorted(math.dist(p, (0, 0)) for p in run if abs(math.atan2(p[0], -p[1])) < 1e-6 and -25 < p[1] < 0)
    assert len(tips) == 15
    assert all(b-a == pytest.approx(1.6, abs=.01) for a, b in zip(tips, tips[1:]))
    assert STAR_INNER == .5


@pytest.mark.parametrize('kind', ('maze', 'star'))
def test_maze_and_star_generate_and_pass_the_release_gate(tmp_path, kind):
    from test_stitch_types_engine import design
    from embroiderly.release_gate import checked_bytes
    _, svg = design(tmp_path, {'region_styles': kind})
    assert f'fill_method="{kind}_fill"' in svg
    assert checked_bytes(tmp_path/'out', 'dst')
