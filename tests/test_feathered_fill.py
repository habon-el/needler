"""Feathered fill: tatami rows whose ends stop short at random (feather and textured edges)."""
import math

import pytest
from shapely.geometry import LineString, Point, Polygon

from embroiderly.region_stitches import CATALOG, VARIANTS
from embroiderly.stitch_fills import FEATHER_DEPTH_MM, feathered, tatami

SQUARE = Polygon([(0, 0), (30, 0), (30, 25), (0, 25)])
DISC = Point(20, 20).buffer(15)
RING = DISC.difference(Point(20, 20).buffer(5))


def row_ends(runs):
    """Row ends of horizontal tatami rows: the stitch points where the run turns."""
    left, right = [], []
    for run in runs:
        for p, q, r in zip(run, run[1:], run[2:]):
            if (q[0]-p[0])*(r[0]-q[0]) < 0:
                (right if q[0] > p[0] else left).append(q[0])
    return left, right


def test_listed_with_three_edge_choices():
    assert 'feather' in [key for key, _, _ in CATALOG]
    assert [key for key, _ in VARIANTS['feather']] == ['end', 'both', 'texture']


def test_one_edge_is_ragged_and_the_other_straight():
    left, right = row_ends(feathered(SQUARE, underlay=False, edge='end'))
    assert max(left)-min(left) < .1                       # start side follows the edge
    assert 30-min(right) > 2 and max(right) > 29.5        # tips end anywhere in the 4 mm band
    assert min(right) >= 30-FEATHER_DEPTH_MM['end']-1e-6


def test_both_edges_and_texture_depths():
    left, right = row_ends(feathered(SQUARE, underlay=False, edge='both'))
    assert max(left) > 1.5 and 30-min(right) > 1.5
    left, right = row_ends(feathered(SQUARE, underlay=False, edge='texture'))
    assert 0 < max(left) <= FEATHER_DEPTH_MM['texture']+1e-6
    assert 0 < 30-min(right) <= FEATHER_DEPTH_MM['texture']+1e-6


def test_same_area_sews_the_same_way():
    assert feathered(DISC, edge='both') == feathered(DISC, edge='both')


def test_differs_from_tatami_and_covers_most_of_the_area():
    runs = feathered(SQUARE, underlay=False)
    assert runs != tatami(SQUARE, underlay=False)
    sewn = LineString([p for run in runs for p in run]).buffer(.25)
    assert sewn.intersection(SQUARE).area > .85*SQUARE.area


@pytest.mark.parametrize('edge', ('end', 'both', 'texture'))
@pytest.mark.parametrize('shape', (SQUARE, DISC, RING))
def test_stays_inside_with_stitches_in_range(shape, edge):
    runs = feathered(shape, 30, edge=edge)
    assert runs and all(shape.buffer(.1).contains(Point(p)) for run in runs for p in run)
    assert max(math.dist(p, q) for run in runs for p, q in zip(run, run[1:])) <= 3.0+1e-6


@pytest.mark.parametrize('style', ('feather', 'feather:texture'))
def test_generate_and_pass_the_release_gate(tmp_path, style):
    from test_stitch_types_engine import design
    from embroiderly.release_gate import checked_bytes
    _, svg = design(tmp_path, {'region_styles': style})
    assert 'fill_method="feathered_fill"' in svg
    assert checked_bytes(tmp_path/'out', 'dst')
