"""Globe fill (tatami crowding towards the edges) and hand stitch fill (uneven open rows)."""
import math

import pytest
from shapely.geometry import Point, Polygon

from embroiderly.region_stitches import CATALOG
from embroiderly.stitch_fills import GLOBE_SQUEEZE, HAND_PITCH_MM, globe, hand, tatami

SQUARE = Polygon([(0, 0), (30, 0), (30, 25), (0, 25)])
DISC = Point(20, 20).buffer(15)
RING = DISC.difference(Point(20, 20).buffer(5))


def legs(runs):
    return [math.dist(p, q) for run in runs for p, q in zip(run, run[1:])]


def gaps(values):
    values = sorted(values)
    return [b-a for a, b in zip(values, values[1:])]


def test_both_are_listed():
    ids = [key for key, _, _ in CATALOG]
    assert 'globe' in ids and 'hand' in ids


def test_globe_rows_crowd_towards_the_edges():
    runs = globe(SQUARE, underlay=False)
    rows = gaps({round(p[1], 3) for run in runs for p in run if 5 < p[0] < 25})
    middle = rows[len(rows)//2-2:len(rows)//2+2]
    assert max(rows[:3]) < .8*min(middle)
    assert min(rows) > .4*(1-GLOBE_SQUEEZE)                    # never denser than the rim spacing


def test_globe_stitches_shorten_towards_the_sides():
    runs = globe(SQUARE, underlay=False)
    stitches = [(abs((p[0]+q[0])/2-15), math.dist(p, q)) for run in runs for p, q in zip(run, run[1:])
                if abs(p[1]-q[1]) < .05 and math.dist(p, q) > 1]
    side = [d for x, d in stitches if x > 11]
    centre = [d for x, d in stitches if x < 4]
    assert max(side) < .85*max(centre)


def test_globe_thread_close_to_tatami():
    ratio = sum(legs(globe(SQUARE, underlay=False)))/sum(legs(tatami(SQUARE, underlay=False)))
    assert .85 < ratio < 1.25


def test_hand_stitches_vary_in_length():
    lengths = [d for d in legs(hand(SQUARE)) if d > .5]
    assert min(lengths) < 1.5 and max(lengths) > 3
    assert max(lengths) <= HAND_PITCH_MM*.85+1e-6


@pytest.mark.parametrize('fill', (globe, hand))
@pytest.mark.parametrize('shape', (SQUARE, DISC, RING))
def test_stay_inside_with_stitches_in_range(shape, fill):
    runs = fill(shape, 30)
    assert runs and all(shape.buffer(.1).contains(Point(p)) for run in runs for p in run)
    # Short travel steps are merged later by the engine (enforce_min), as for tatami.
    assert max(legs(runs)) <= HAND_PITCH_MM


def test_same_area_sews_the_same_way():
    assert hand(DISC) == hand(DISC) and globe(DISC) == globe(DISC)


@pytest.mark.parametrize('style', ('globe', 'hand'))
def test_generate_and_pass_the_release_gate(tmp_path, style):
    from test_stitch_types_engine import design
    from embroiderly.release_gate import checked_bytes
    _, svg = design(tmp_path, {'region_styles': style})
    assert f'fill_method="{style}_fill"' in svg
    assert checked_bytes(tmp_path/'out', 'dst')
