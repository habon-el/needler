"""Where satin columns meet (junctions, bends, a branch joining an outline) they overlap
inside the outline instead of leaving bare wedges; counters stay open; the lettering
coverage check finds a letter part no column covers."""
import math
import xml.etree.ElementTree as ET
import cv2
import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from embroiderly import embroidery_fonts, satin_font
from embroiderly.lettering_coverage import bare_patches
from embroiderly.lettering_geometry import INK, SVG
from embroiderly.satin_font import _ribbon, area_columns, bare_patches as bare_parts, columns_for, glyph_outline

DAMION = embroidery_fonts.font_path('damion')


def covered(columns):
    return unary_union([_ribbon(a, b, closed) for a, b, closed, _ in columns])


def layers(shape, columns, k=400):
    """Most columns over one point (each column in short runs of sections, so a column
    that overlaps itself counts twice; shrunk a pixel so shared edges do not count)."""
    left, top, right, bottom = shape.bounds
    total = np.zeros((int((bottom-top)*k)+4, int((right-left)*k)+4), int)
    for a, b, closed, _ in columns:
        runs = [_ribbon(a, b, True)] if closed else [
            unary_union([Polygon([a[i], a[i+1], b[i+1], b[i]]).buffer(0) for i in range(j, min(j+4, len(a)-1))])
            for j in range(0, len(a)-1, 4)]
        for run in runs:
            image = Image.new('L', total.shape[::-1]); draw = ImageDraw.Draw(image)
            for part in getattr(run.buffer(-1.5/k), 'geoms', [run.buffer(-1.5/k)]):
                if part.geom_type == 'Polygon' and not part.is_empty:
                    draw.polygon([((x-left)*k+2, (y-top)*k+2) for x, y in part.exterior.coords], fill=1)
                    for hole in part.interiors:
                        draw.polygon([((x-left)*k+2, (y-top)*k+2) for x, y in hole.coords], fill=0)
            total += np.asarray(image, int)
    return int(total.max())


def test_script_joins_leave_no_bare_wedges():
    # Damion "a", "n", "m": the bowl meeting the stem, the shoulders of n and m.
    # Before: 4.6 %, 2.3 %, 3.9 % bare, the largest bare patch 2.2 % of the "a".
    for char in 'anm':
        shape, _ = glyph_outline(DAMION, char)
        columns = columns_for(shape)
        bare = shape.difference(covered(columns))
        assert bare.area < .01*shape.area, char
        assert max(g.area for g in getattr(bare, 'geoms', [bare])) < .003*shape.area, char
        # Overlap where they meet, not piles of thread.
        assert layers(shape, columns) <= 3, char


def test_counters_stay_open_and_the_dot_is_sewn():
    for char in 'abo':
        shape, _ = glyph_outline(DAMION, char)
        sewn = covered(columns_for(shape))
        for part in getattr(shape, 'geoms', [shape]):
            for ring in part.interiors:
                counter = Polygon(ring)
                assert sewn.intersection(counter).area < .01*counter.area, char
    shape, _ = glyph_outline(DAMION, 'i')
    dot = min(shape.geoms, key=lambda g: g.centroid.y)
    assert covered(columns_for(shape)).intersection(dot).area > .9*dot.area


def rings_mm():
    """A thin outline (1.2 mm) with a second ring meeting it: the ball outline
    meeting the flame outline in a picture."""
    ring = Point(20, 20).buffer(15).difference(Point(20, 20).buffer(13.8))
    ball = Point(36, 36).buffer(8).difference(Point(36, 36).buffer(6.8))
    return unary_union([ring, ball])


def test_picture_outlines_get_their_joins_covered():
    shape = rings_mm()
    # The traced columns alone leave the wedges where the rings meet bare...
    assert bare_parts(shape, area_columns(shape, gaps=False), .4)
    columns = area_columns(shape)
    # ...the picture path now closes them, inside the outline and never in a ring's hole.
    assert not bare_parts(shape, columns, .4)
    for a, b, closed, _ in columns:
        assert _ribbon(a, b, closed).difference(shape.buffer(.05)).area < .01
    holes = unary_union([Polygon(h) for part in getattr(shape, 'geoms', [shape]) for h in part.interiors])
    assert covered(columns).intersection(holes).area < .1


def test_thin_outline_that_stays_bare_is_caught(monkeypatch):
    from embroiderly import engine
    plane = np.zeros((240, 240), np.uint8)
    scale = .25
    for part in getattr(rings_mm(), 'geoms', [rings_mm()]):
        cv2.fillPoly(plane, [np.int32(np.array(part.exterior.coords)/scale)], 1)
        for hole in part.interiors:
            cv2.fillPoly(plane, [np.int32(np.array(hole.coords)/scale)], 0)
    contours, hierarchy = cv2.findContours(plane, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    outer = max(range(len(contours)), key=lambda i: cv2.contourArea(contours[i]))
    rings = [contours[outer]]+[c for i, c in enumerate(contours) if hierarchy[0, i, 3] == outer]
    thick = engine.thickness_mm(rings, scale)
    assert thick < engine.FILL_FROM_MM
    assert not engine.satin_gaps(rings, scale, thick)
    # Columns that would leave a wedge wider than a thread: the outline is filled instead
    # (thin outlines were never checked before).
    real = satin_font.area_columns
    monkeypatch.setattr(satin_font, 'area_columns', lambda shape, gaps=True: real(shape, gaps=False))
    assert engine.satin_gaps(rings, scale, thick)


def test_coverage_check_finds_a_letter_part_without_a_column():
    svg = embroidery_fonts.layout('a', 'damion', 300.0)
    assert bare_patches(svg) == []
    root = ET.fromstring(svg)
    group = next(g for g in root.iter(SVG+'g') if g.get(INK+'letter-group') == 'glyph')
    columns = [p for p in group.iter(SVG+'path') if p.get(INK+'satin_column') == 'true']
    assert len(columns) > 1
    group.remove(max(columns, key=lambda p: len(p.get('d'))))
    issues = bare_patches(ET.tostring(root, encoding='unicode'))
    assert issues and {i['code'] for i in issues} == {'bare_patch'} and {i['letter'] for i in issues} == {'a'}
    assert all(math.isfinite(i['location']['x_mm']+i['location']['y_mm']) for i in issues)


def test_a_pixel_line_beside_a_wide_area_gets_no_specks_of_satin():
    # A 6 mm band and a one-pixel (0.13 mm) stepped line running off its edge, as a traced
    # picture gives. The line's columns make the typical stroke a hair; gap columns relative
    # to it covered every pixel step with a speck of satin (172 here), and the moves between
    # them crossed the removed background of a cut-out subject.
    from shapely.geometry import box
    px = .13
    shape = unary_union([box(40, 0, 46, 40)]+[box(i*px*3, 40-i*px*1.8, (i+1)*px*3+px, 40-i*px*1.8+px)
                                               for i in range(100)])
    gaps = [(a, b) for a, b, closed, _ in area_columns(shape) if closed is None]
    assert len(gaps) <= 4
    assert all(max(math.dist(p, q) for p, q in zip(a, b)) >= .4 for a, b in gaps)
