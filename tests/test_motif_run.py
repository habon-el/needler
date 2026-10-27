"""Motif run: small diamonds, triangles or scallops along a line, as a subject border."""
import math

import numpy as np
import pytest
from shapely.geometry import Point, Polygon

from embroiderly.borders import border_plan
from embroiderly.stitch_paths import MOTIFS, inward_side, motif_run

LINE = [(0.0, 0.0), (30.0, 0.0)]
SQUARE = [(0.0, 0.0), (20.0, 0.0), (20.0, 20.0), (0.0, 20.0), (0.0, 0.0)]


def legs(points):
    return [math.dist(p, q) for p, q in zip(points, points[1:])]


@pytest.mark.parametrize('motif', MOTIFS)
def test_motif_run_follows_the_line_end_to_end_with_safe_stitches(motif):
    points = motif_run(LINE, 2.0, 2.5, 2.0, motif)
    assert points[0] == LINE[0] and math.isclose(points[-1][0], 30.0)
    assert .45 <= min(legs(points)) and max(legs(points)) <= 2.0+1e-6
    ys = [y for _, y in points]
    # Motifs stand off the line; never more than the chosen width.
    assert max(abs(y) for y in ys) == pytest.approx(2.5 if motif != 'diamond' else 1.25, abs=.05)


def test_diamonds_sit_across_the_line_and_one_sided_motifs_follow_the_side():
    diamond = [y for _, y in motif_run(LINE, 2.0, 2.0, 2.0, 'diamond')]
    assert max(diamond) > .9 and min(diamond) < -.9
    left = [y for _, y in motif_run(LINE, 2.0, 2.0, 2.0, 'triangle', 1)]
    right = [y for _, y in motif_run(LINE, 2.0, 2.0, 2.0, 'triangle', -1)]
    assert min(left) > -1e-6 and max(left) > 1.9
    assert max(right) < 1e-6 and min(right) < -1.9


def test_motifs_are_spread_evenly_and_count_with_the_spacing():
    def peaks(spacing):
        pts = motif_run(LINE, 2.0, 2.0, spacing, 'triangle')
        return [x for x, y in pts if y > 1.9]
    tight, loose = peaks(1.0), peaks(4.0)
    assert len(tight) > len(loose) >= 2
    gaps = [b-a for a, b in zip(tight, tight[1:])]
    assert max(gaps)-min(gaps) < .05


def test_on_a_closed_ring_one_sided_motifs_point_out_of_the_shape():
    side = -inward_side(SQUARE[:-1])
    points = motif_run(SQUARE, 2.0, 2.0, 2.0, 'scallop', side)
    shape = Polygon(SQUARE)
    outside = [p for p in points if not shape.buffer(1e-6).contains(Point(p))]
    assert outside and all(shape.exterior.distance(Point(p)) <= 2.0+1e-6 for p in points)
    assert math.dist(points[0], points[-1]) < 1e-6


def test_short_lines_are_plain_running_stitch():
    points = motif_run([(0.0, 0.0), (3.0, 0.0)], 2.0, 2.5, 2.0)
    assert all(y == 0 for _, y in points)


def test_border_plan_keeps_the_motif_and_refuses_unknown_ones():
    mask = np.zeros((200, 200), bool); mask[40:160, 40:160] = True
    plan = border_plan(mask, 50, dict(border_style='motif', border_width=2, border_motif='scallop'))
    assert plan['style'] == 'motif' and plan['motif'] == 'scallop'
    assert border_plan(mask, 50, dict(border_style='motif', border_width=2))['motif'] == 'diamond'
    with pytest.raises(ValueError):
        border_plan(mask, 50, dict(border_style='motif', border_width=2, border_motif='heart'))


@pytest.mark.parametrize('motif', MOTIFS)
def test_motif_run_border_generates_and_passes_the_release_gate(tmp_path, motif):
    from test_stitch_types_engine import design
    from embroiderly.release_gate import checked_bytes
    _, svg = design(tmp_path, {'border_style': 'motif', 'border_motif': motif, 'border_width': 2,
                               'border_colour': '#202020'})
    assert 'outline_style="motif"' in svg and f'outline_motif="{motif}"' in svg
    assert checked_bytes(tmp_path/'out', 'dst')
