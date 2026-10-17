"""Read satin rail/rung geometry regardless of SVG subpath order."""
from itertools import combinations
import math
from shapely.geometry import LineString, Polygon


def rail_polygon(a, b, *, resolve_overlap=True):
    if min(len(a), len(b)) < 2:
        return None
    if math.dist(a[0], a[-1]) < 1e-6 and math.dist(b[0], b[-1]) < 1e-6:
        outer, inner = (a, b) if Polygon(a).area > Polygon(b).area else (b, a)
        return Polygon(outer, [inner])
    if math.dist(a[0], b[0])+math.dist(a[-1], b[-1]) > math.dist(a[0], b[-1])+math.dist(a[-1], b[0]):
        b = b[::-1]
    shape = Polygon(a+b[::-1])
    if resolve_overlap and not shape.is_valid:
        from .ribbon_outline import winding_interior
        shape = winding_interior(a+b[::-1])
    return shape


def column_shape(parts):
    if not 2 <= len(parts) <= 100 or any(len(p) < 2 for p in parts):
        raise ValueError('This font column has incomplete rails or too many rungs to verify.')
    lines = [LineString(p) for p in parts]
    candidates, established = [], []
    for a, b in combinations(range(len(parts)), 2):
        # Every other subpath is a rung: it must touch both rails. This also
        # handles a short crossbar whose rung is longer than the two rails.
        # A font-authored rung may bend (for example in an ampersand). Its
        # vertex count does not define its role; connectivity and unique rails do.
        if any(not lines[r].is_simple or lines[r].distance(lines[a]) > .01 or lines[r].distance(lines[b]) > .01
               for r in range(len(parts)) if r not in (a, b)):
            continue
        original = rail_polygon(parts[a], parts[b], resolve_overlap=False)
        shape = original if original is not None and original.is_valid else rail_polygon(parts[a], parts[b])
        if shape is not None and shape.is_valid and shape.area > 0:
            # A bent rung must cross this ribbon once, not loop around it.
            # Otherwise two real rungs could be mistaken for rails and the
            # curved letter rails mistaken for rungs (notably lowercase e).
            if any(lines[r].intersection(shape).geom_type != 'LineString'
                   or lines[r].intersection(lines[a]).geom_type != 'Point'
                   or lines[r].intersection(lines[b]).geom_type != 'Point'
                   for r in range(len(parts)) if r not in (a, b) and len(parts[r]) > 2):
                continue
            candidates.append(shape)
            if original is not None and original.is_valid and all(len(parts[r]) == 2 for r in range(len(parts)) if r not in (a, b)):
                established.append(shape)
    # Keep an already unambiguous straight-rung interpretation. Curved-rung
    # and overlap handling is a fallback, never a reason to reinterpret an
    # existing verified column as the narrow region between two guide rungs.
    if established:
        candidates = established
    if not candidates or any(c.symmetric_difference(candidates[0]).area > .0001 for c in candidates[1:]):
        raise ValueError('A font column has an ambiguous outline. Choose another font or size; nothing was simplified.')
    return candidates[0]
