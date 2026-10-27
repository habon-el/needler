"""Florentine fill: tatami rows that copy the curve of the area's top edge."""
import math

import pytest
from shapely.geometry import LineString, Point, Polygon

from embroiderly.region_stitches import CATALOG
from embroiderly.stitch_fills import FLORENTINE_SLOPE, _top_profile, florentine, wave

# A band whose top and bottom edges are the same arch, 8 mm high in the middle.
ARCH = [(x, 8*math.sin(math.pi*x/60)) for x in range(0, 61, 2)]
BAND = Polygon([(x, 20-y) for x, y in ARCH]+[(x, 32-y) for x, y in ARCH[::-1]])
DISC = Point(20, 20).buffer(15)
RING = DISC.difference(Point(20, 20).buffer(5))


def legs(run):
    return [math.dist(p, q) for p, q in zip(run, run[1:])]


def test_florentine_is_a_listed_area_style():
    assert 'florentine' in [key for key, _, _ in CATALOG]


def test_profile_follows_the_top_edge_and_keeps_its_slope_gentle():
    xs, offsets = _top_profile(BAND, 0)
    assert offsets.min() == 0
    # Highest in the middle (offset 0), dipping ~8 mm at both ends, as the arch does.
    assert offsets[len(xs)//2] < .5 and offsets[0] > 7 and offsets[-1] > 7
    step = xs[1]-xs[0]
    assert max(abs(b-a) for a, b in zip(offsets, offsets[1:])) <= FLORENTINE_SLOPE*step+1e-9


def test_rows_in_an_arched_band_follow_the_arch():
    runs = florentine(BAND, underlay=False)
    points = [p for run in runs for p in run]
    # Cut the stitches with a vertical line near each end and in the middle: a straight
    # tatami would cross at the same heights, an arched one 8 mm higher in the middle.
    middle = [p for p in points if abs(p[0]-30) < .3]
    end = [p for p in points if abs(p[0]-6) < .3]
    assert middle and end
    top_mid, top_end = min(p[1] for p in middle), min(p[1] for p in end)
    assert top_end-top_mid > 4


@pytest.mark.parametrize('shape', (BAND, DISC, RING))
def test_stitches_stay_inside_and_within_length(shape):
    runs = florentine(shape)
    inside = shape.buffer(.1)
    assert runs
    assert all(inside.contains(Point(p)) for run in runs for p in run)
    assert max(max(legs(run)) for run in runs if len(run) > 1) <= 3.0+1e-6


def test_florentine_covers_the_area():
    runs = florentine(BAND, underlay=False)
    sewn = LineString([p for run in runs for p in run]).buffer(.4)
    assert sewn.intersection(BAND).area > .95*BAND.area


def test_wave_unchanged_by_shared_bending():
    runs = wave(DISC, underlay=False)
    assert runs and all(DISC.buffer(.1).contains(Point(p)) for run in runs for p in run)


def test_florentine_generates_and_passes_the_release_gate(tmp_path):
    from test_stitch_types_engine import design
    from embroiderly.release_gate import checked_bytes
    _, svg = design(tmp_path, {'region_styles': 'florentine'})
    assert 'fill_method="florentine_fill"' in svg
    assert checked_bytes(tmp_path/'out', 'dst')
