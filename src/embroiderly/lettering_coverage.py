"""Check that every independently authored font column receives needle points.

This is a missing-piece check, not a density or visual-legibility assessment.
"""
import math
import pyembroidery as emb
from shapely.affinity import translate
from shapely.geometry import Point
from shapely.strtree import STRtree
from .lettering_geometry import outline


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
