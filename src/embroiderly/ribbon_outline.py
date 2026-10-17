"""Interpret overlapping authored ribbon boundaries without changing their paths.

Use the nonzero winding interior of the original directed boundary, not a
convex hull, buffer(0), output-stitch envelope or an area-expanding repair.
This preserves counter faces with zero winding and overlaps sewn twice.
"""
from shapely.geometry import LineString
from shapely.ops import polygonize, unary_union


def winding_interior(points):
    ring = list(points)
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    faces = polygonize(unary_union(LineString(ring)))
    kept = []
    for face in faces:
        p = face.representative_point()
        winding = 0
        for (x, y), (xx, yy) in zip(ring, ring[1:]):
            side = (xx-x)*(p.y-y)-(p.x-x)*(yy-y)
            if y <= p.y < yy and side > 0:
                winding += 1
            elif yy <= p.y < y and side < 0:
                winding -= 1
        if winding:
            kept.append(face)
    return unary_union(kept)
