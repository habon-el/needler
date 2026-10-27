"""Open hand-look fills: blackwork lattice, candlewicking knots and lacework net."""
import math
import re

import cv2
import numpy as np
import pytest
from shapely.geometry import Point, Polygon

from embroiderly.region_stitches import CATALOG, OPEN_FILLS, decorative_paths, open_fill_shapes

SCALE = .1   # mm per pixel


def disc(radius_px=160):
    mask = np.zeros((400, 400), np.uint8)
    cv2.circle(mask, (200, 200), radius_px, 1, -1)
    return list(cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0])


def fragments(d):
    return [np.array([[float(v) for v in xy.split(',')] for xy in re.findall(r'[-\d.]+,[-\d.]+', part)])*SCALE
            for part in d.split('M ')[1:]]


def test_open_fills_are_listed_area_styles():
    ids = [key for key, _, _ in CATALOG]
    assert all(kind in ids for kind in OPEN_FILLS)


@pytest.mark.parametrize('kind', OPEN_FILLS)
def test_open_fills_stay_inside_the_area(kind):
    area = Polygon(disc()[0].reshape(-1, 2)*SCALE).buffer(.05)
    parts = fragments(decorative_paths(disc(), SCALE, kind))
    assert parts and all(area.contains(Point(p)) for part in parts for p in part)


def test_blackwork_is_a_few_long_lines_with_a_diamond_in_every_cell():
    parts = fragments(decorative_paths(disc(), SCALE, 'blackwork_fill'))
    # Long lines, not one piece per cell: a 32 mm disc takes under 50 pieces.
    assert len(parts) < 50
    slopes = {round(math.degrees(math.atan2(*(part[-1]-part[0])[::-1])) % 180) for part in parts}
    assert slopes == {0, 45, 90, 135}


def test_lacework_rows_share_their_flat_sides():
    rows = open_fill_shapes((0, 0, 20, 10), 'lacework')
    flats = [{(round(a[0], 6), round(a[1], 6)) for a, b in zip(row, row[1:]) if a[1] == b[1]} for row in rows]
    assert all(flats[i] & flats[i+1] for i in range(len(flats)-1))


def test_candlewicking_keeps_only_whole_knots_spread_on_staggered_rows():
    parts = fragments(decorative_paths(disc(), SCALE, 'candlewick_fill'))
    centres = [tuple(np.round(part[0], 3)) for part in parts]
    assert len(parts) > 30 and all(len(part) == 25 for part in parts)
    assert all(np.allclose(part[0], part[-1]) for part in parts)
    rows = sorted({y for _, y in centres})
    starts = [min(x for x, y in centres if y == row) % 4 for row in rows[1:3]]
    assert abs(starts[0]-starts[1]) == pytest.approx(2, abs=.01)


@pytest.mark.parametrize('kind', OPEN_FILLS)
def test_open_fills_generate_and_pass_the_release_gate(tmp_path, kind):
    from test_stitch_types_engine import design
    from embroiderly.release_gate import checked_bytes
    _, svg = design(tmp_path, {'region_styles': kind})
    assert 'travel_area' in svg
    assert checked_bytes(tmp_path/'out', 'dst')
