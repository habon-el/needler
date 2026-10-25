"""Motif patterns and stipple as backstitch or stemstitch: geometry, saved designs, release gate."""
import math
import xml.etree.ElementTree as ET

import numpy as np
import pytest
from shapely.geometry import Point, Polygon

from embroiderly.region_stitches import (NS, VARIANTS, apply_style, assignments, decorative_paths, regions,
                                         split_style)
from embroiderly.stitch_fills import meander
from embroiderly.stitch_paths import enforce_min
from embroiderly.release_gate import checked_bytes
from test_stitch_types_engine import design

NEW_MOTIFS = ['heart', 'star', 'scale', 'circle']


def area_with_hole():
    # 26 × 24 mm at 0.1 mm per pixel, with an 8 mm square hole.
    rgb = np.zeros((300, 300, 3), np.uint8); alpha = np.zeros((300, 300), bool)
    alpha[20:280, 20:260] = True; alpha[100:180, 90:170] = False
    _, _, rings = next(regions(rgb, alpha))
    return rings


def styled(kind, rings, scale=.1):
    root = ET.Element('svg')
    node = ET.SubElement(root, 'path', id='t', d='original', style='fill:#123456;fill-rule:evenodd;stroke:none')
    apply_style(root, node, rings, scale, kind)
    return node


def subpaths(d, scale=.1):
    return [[tuple(float(v)*scale for v in xy.split(',')) for xy in part.replace('M', '').split(' L ')]
            for part in d.split('M ') if part.strip()]


def test_variants_are_validated_and_the_default_is_the_plain_style():
    key = 'a'*20
    for style in ('motif:heart', 'motif:star', 'motif:scale', 'motif:circle', 'stipple:backstitch', 'stipple:stemstitch'):
        assert assignments({'region_styles': {key: style}})
    for style in ('motif:diamond', 'motif:bogus', 'stipple:run', 'tatami:heart', 'stipple:', 'motif:heart:x'):
        with pytest.raises(ValueError):
            assignments({'region_styles': {key: style}})
    assert split_style('motif') == ('motif', 'diamond') and split_style('stipple') == ('stipple', 'run')
    assert split_style('motif:heart') == ('motif', 'heart') and split_style('tatami') == ('tatami', '')
    assert [v for v, _ in VARIANTS['motif']][0] == 'diamond' and [v for v, _ in VARIANTS['stipple']][0] == 'run'


def test_saved_motif_keeps_its_diamonds():
    rings = area_with_hole()
    node = styled('motif', rings)
    assert node.get('d') == decorative_paths(rings, .1, 'motif')
    assert node.get(NS+'running_stitch_length_mm') == '2' and node.get(NS+'running_stitch_tolerance_mm') is None
    # Whole repeats are the original diamonds: 2 mm steps, closed.
    whole = [p for p in subpaths(node.get('d')) if len(p) == 5]
    assert len(whole) > 12
    for p in whole:
        assert p[0] == pytest.approx(p[-1]) and all(math.dist(a, b) == pytest.approx(2*math.sqrt(2)) for a, b in zip(p, p[1:]))


@pytest.mark.parametrize('pattern', NEW_MOTIFS)
def test_motif_patterns_repeat_inside_the_area_and_keep_the_hole_empty(pattern):
    rings = area_with_hole()
    area = Polygon(np.asarray(rings[0]).reshape(-1, 2)*.1, [np.asarray(rings[1]).reshape(-1, 2)*.1])
    hole = Polygon(np.asarray(rings[1]).reshape(-1, 2)*.1)
    node = styled('motif:'+pattern, rings)
    assert node.get(NS+'stroke_method') == 'running_stitch' and node.get(NS+'travel_area')
    assert node.get(NS+'running_stitch_length_mm') == '1.2'
    paths = subpaths(node.get('d'))
    points = [p for path in paths for p in path]
    assert all(area.buffer(.01).contains(Point(p)) for p in points)
    assert not any(hole.buffer(-.01).contains(Point(p)) for p in points)
    assert node.get('d') != decorative_paths(rings, .1, 'motif')
    if pattern == 'scale':
        # Rows of half circles, each ending where the next begins (sewn as one line per row).
        starts = {(round(p[0][0], 3), round(p[0][1], 3)) for p in paths}
        joined = sum((round(p[-1][0], 3), round(p[-1][1], 3)) in starts for p in paths)
        assert len(paths) > 20 and joined > 12
        assert len({round(p[0][1], 3) for p in paths if len(p) == 9}) >= 5   # whole arcs on 5+ rows
    else:
        closed = [p for p in paths if math.dist(p[0], p[-1]) < 1e-6]
        assert len(closed) > 12   # whole repeats every 4 mm
        sizes = {round(Polygon(p).area, 3) for p in closed}
        assert len(sizes) == 1    # identical repeats


def stitches(runs):
    return [enforce_min(r, .45) for r in runs]


def test_stipple_default_is_unchanged_single_run():
    shape = Polygon([(0, 0), (30, 0), (30, 20), (0, 20)])
    assert meander(shape, 2, 1, .45, 3, tolerance=.15) == meander(shape, 2, 1, .45, 3, tolerance=.15, stitch='run')
    node = styled('stipple', area_with_hole())
    assert node.get(NS+'fill_method') == 'meander_fill' and node.get(NS+'stipple_stitch') is None


@pytest.mark.parametrize('stitch', ['backstitch', 'stemstitch'])
def test_stipple_variants_stay_inside_and_sew_back(stitch):
    node = styled('stipple:'+stitch, area_with_hole())
    assert node.get(NS+'stipple_stitch') == stitch
    shape = Polygon([(0, 0), (30, 0), (30, 20), (0, 20)], [[(10, 5), (18, 5), (18, 13), (10, 13)]])
    hole = Polygon([(10, 5), (18, 5), (18, 13), (10, 13)])
    single = stitches(meander(shape, 2, 1, .45, 7, tolerance=.15))
    runs = stitches(meander(shape, 2, 1, .45, 7, tolerance=.15, stitch=stitch))
    points = [p for r in runs for p in r]
    assert all(shape.buffer(1e-6).contains(Point(p)) for p in points)
    assert not any(hole.buffer(-.01).contains(Point(p)) for p in points)
    legs = [(a, b) for r in runs for a, b in zip(r, r[1:])]
    assert all(.45-1e-9 <= math.dist(a, b) <= 7 for a, b in legs)
    # Turning back: consecutive stitches pointing against each other.
    back = sum(1 for r in runs for a, b, c in zip(r, r[1:], r[2:])
               if (b[0]-a[0])*(c[0]-b[0])+(b[1]-a[1])*(c[1]-b[1]) < 0)
    assert back > .3*len(legs)
    assert len(points) > 1.5*sum(len(r) for r in single)


@pytest.mark.parametrize('style', ['motif:'+p for p in NEW_MOTIFS]+['stipple:backstitch', 'stipple:stemstitch'])
def test_variants_generate_and_pass_the_release_gate(tmp_path, style):
    payload, svg = design(tmp_path, {'region_styles': style})
    if style.startswith('stipple'):
        assert f'stipple_stitch="{style.split(":")[1]}"' in svg
    else:
        assert 'running_stitch_length_mm="1.2"' in svg
    assert payload['stitch_count'] > 300
    assert checked_bytes(tmp_path/'out', 'dst')
