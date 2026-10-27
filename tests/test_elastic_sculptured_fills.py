"""Elastic fill (motif repeats stretched over the shape) and sculptured fill (diamond needle holes)."""
import math

import numpy as np
import pytest
from shapely.geometry import LineString, Point, Polygon

from embroiderly.region_stitches import CATALOG, VARIANTS, elastic_parts
from embroiderly.stitch_fills import SCULPTURED_PITCH_MM, sculptured, stretch_map, tatami

SQUARE = Polygon([(0, 0), (30, 0), (30, 25), (0, 25)])
DISC = Point(20, 20).buffer(15)
RING = DISC.difference(Point(20, 20).buffer(5))
# A band 12 mm high at the ends and 22 mm in the middle, arching up 8 mm.
ARCH = [(x, 8*math.sin(math.pi*x/60)) for x in range(0, 61, 2)]
BAND = Polygon([(x, 20-y) for x, y in ARCH]+[(x, 32-y+10*math.sin(math.pi*x/60)) for x, y in ARCH[::-1]])


def legs(run):
    return [math.dist(p, q) for p, q in zip(run, run[1:])]


def points(parts):
    return [[tuple(map(float, c.split(','))) for c in part[2:].split(' L ')] for part in parts]


def test_both_are_listed_and_elastic_offers_the_motif_patterns():
    ids = [key for key, _, _ in CATALOG]
    assert 'elastic' in ids and 'sculptured' in ids
    assert VARIANTS['elastic'] == VARIANTS['motif']


def test_sculptured_needle_holes_lie_on_both_diagonals():
    runs = sculptured(SQUARE, underlay=False)
    holes = [p for run in runs for p in run[1:-1] if 1 < p[0] < 29]
    assert holes
    pitch = SCULPTURED_PITCH_MM
    for x, y in holes:
        # Every inside hole sits on a line x-y or x+y that repeats every pitch (rows sit half a row down).
        on = [((x-y+s) % pitch) for s in (.2, -.2)]+[((x+y+s) % pitch) for s in (.2, -.2)]
        assert min(min(d, pitch-d) for d in on) < 1e-6


def test_sculptured_differs_from_tatami_and_keeps_stitches_in_range():
    runs = sculptured(SQUARE, underlay=False)
    assert runs != tatami(SQUARE, underlay=False)
    lengths = [d for run in runs for d in legs(run)]
    assert max(lengths) <= SCULPTURED_PITCH_MM+1e-6
    sewn = LineString([p for run in runs for p in run]).buffer(.25)
    assert sewn.intersection(SQUARE).area > .97*SQUARE.area


@pytest.mark.parametrize('shape', (SQUARE, DISC, RING))
def test_sculptured_stays_inside(shape):
    runs = sculptured(shape)
    assert runs and all(shape.buffer(.1).contains(Point(p)) for run in runs for p in run)


def test_stretch_map_spans_top_to_bottom_edge():
    left, right, place = stretch_map(BAND, 0)
    assert left == pytest.approx(0, abs=.3) and right == pytest.approx(60, abs=.3)
    top, bottom = place(30, 0), place(30, 1)
    assert top[1] == pytest.approx(12, abs=.6) and bottom[1] == pytest.approx(34, abs=.6)


@pytest.mark.parametrize('pattern', [key for key, _ in VARIANTS['elastic']])
def test_elastic_repeats_stay_inside(pattern):
    lines = points(elastic_parts(BAND, 0, pattern, 1.0))
    assert lines
    assert all(BAND.buffer(.05).contains(Point(p)) for line in lines for p in line)


def test_elastic_repeats_grow_with_the_shape():
    # The same number of rows from top to bottom: repeats are taller where the band is taller.
    lines = points(elastic_parts(BAND, 0, 'circle', 1.0))
    def height_near(x):
        rings = [l for l in lines if abs(np.mean([p[0] for p in l])-x) < 2 and len(l) > 8]
        return max(max(p[1] for p in l)-min(p[1] for p in l) for l in rings)
    # The band is 22 mm high in the middle and about 15 mm near x=6.
    assert height_near(30) > 1.25*height_near(6)


@pytest.mark.parametrize('kind', ('elastic', 'sculptured'))
def test_generate_and_pass_the_release_gate(tmp_path, kind):
    from test_stitch_types_engine import design
    from embroiderly.release_gate import checked_bytes
    _, svg = design(tmp_path, {'region_styles': kind})
    assert ('fill_method="sculptured_fill"' if kind == 'sculptured' else 'travel_area') in svg
    assert checked_bytes(tmp_path/'out', 'dst')
