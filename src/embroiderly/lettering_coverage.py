"""Check that every independently authored font column receives needle points, and
that the columns together cover the letters as drawn.

These are missing-piece and bare-fabric checks, not a density or visual-legibility assessment.
"""
import math
import pyembroidery as emb
from shapely.affinity import translate
from shapely.geometry import Point
from shapely.strtree import STRtree
from .lettering_geometry import INK, MM, SVG, outline

BARE_MM = .4   # a bare part wider than about one thread shows as fabric once sewn


def missing_columns(svg, pattern):
    raw, _, _ = outline(svg)
    x, y, right, bottom = raw.bounds
    cx, cy = (x+right)/2, (y+bottom)/2
    # Distinct points: repeated locking at one point must not count as a column.
    locations = sorted({(x/10, y/10) for x,y,kind in pattern.stitches
                        if kind & emb.COMMAND_MASK == emb.STITCH and math.isfinite(x+y)})
    tree = STRtree([Point(p) for p in locations])
    issues = []
    for index, shape in enumerate(outline(svg, with_paths=True).values()):
        shape = translate(shape, xoff=-cx, yoff=-cy).buffer(math.sqrt(2)*.05)
        if len(tree.query(shape, predicate='intersects')) < 2:
            center = shape.centroid
            issues.append(dict(code='missing_piece', reason='a font stroke or mark has no usable needle path',
                               location=dict(x_mm=round(center.x,3), y_mm=round(center.y,3), command=None),
                               column=index))
    return issues


def bare_patches(svg, across=BARE_MM):
    """Parts of each letter (its font outline, kept on its glyph group) that no satin
    column covers and that are wider than `across` mm: bare fabric where strokes join or
    turn. Counters (the openings of a, b, o) lie outside the outline and never count.
    Letters without a kept outline (fills, older vectors) are not judged."""
    from . import svg_geometry
    from .stitch_fills import fill_shape
    from .stitch_paths import polygons
    from shapely.ops import unary_union
    raw, _, _ = outline(svg)
    x, y, right, bottom = raw.bounds
    cx, cy = (x+right)/2, (y+bottom)/2
    columns = outline(svg, with_paths=True, raw=True)
    issues = []
    for group in svg_geometry.load(svg).iter(SVG+'g'):
        drawn = group.get(INK+'letter_outline')
        if not drawn:
            continue
        letter = fill_shape([([(px*MM, py*MM) for px, py in points], True)
                             for points, _ in svg_geometry.parse_path(drawn, .01/MM) if len(points) >= 3], 'evenodd')
        sewn = unary_union([columns[node.get('id')] for node in group.iter(SVG+'path') if node.get('id') in columns])
        for piece in polygons(letter.difference(sewn) if not sewn.is_empty else letter):
            core = piece.buffer(-across/2)
            if core.is_empty:
                continue
            center = core.representative_point()
            issues.append(dict(code='bare_patch', reason='part of a letter has no satin over it (bare fabric)',
                               location=dict(x_mm=round(center.x-cx, 3), y_mm=round(center.y-cy, 3), command=None),
                               letter=group.get('{http://www.inkscape.org/namespaces/inkscape}label'),
                               area_mm2=round(piece.area, 3)))
    return issues
