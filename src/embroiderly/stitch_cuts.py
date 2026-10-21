"""Exact stitch removal: take out the stitches inside areas the person drew,
keep every other stitch as it was.

Like stitch editing in professional software, but kept as a recipe: the areas
are saved with the design and applied again whenever stitches are rebuilt.
Where the thread is cut, the last stitch before the gap gets a tie-off and a
thread cut, and sewing resumes with a jump and a tie-in, so nothing unravels.
"""
import math

LOCK = 6.0   # tie-off stitch length, 0.1 mm units (0.6 mm)


def _toward(a, b, length):
    d = math.dist(a, b)
    if d < 1e-9:
        return list(a)
    k = min(1.0, length / d)
    return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k]


def apply(stitches, areas):
    """stitches: [[x, y, command]] (0.1 mm). areas: shapely polygons in the same units.
    Returns (new stitches, removed stitch count)."""
    if not areas:
        return stitches, 0
    from shapely.geometry import Point
    from shapely.ops import unary_union
    from shapely.prepared import prep
    zone = prep(unary_union(areas))
    inside = lambda a, b: zone.contains(Point((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)) \
        or zone.contains(Point(*a)) or zone.contains(Point(*b))
    out, removed, cutting, needle = [], 0, False, None
    for x, y, command in stitches:
        point = [x, y]
        if command == 'STITCH' and needle is not None and inside(needle, point):
            if not cutting and out:
                # Tie off on the last kept stitch, then cut the thread.
                back = next((s for s in reversed(out[:-1]) if s[2] == 'STITCH' and math.dist(s[:2], needle) >= 4.5), None)
                if back is not None:
                    a = _toward(needle, back[:2], LOCK)
                    out += [[*a, 'STITCH'], [*needle, 'STITCH']]
                out.append([*needle, 'TRIM'])
            cutting = True
            removed += 1
            needle = point
            continue
        if cutting and command == 'STITCH':
            # Resume at the start of this kept stitch, tie in, then sew it.
            out.append([*needle, 'JUMP'])
            if math.dist(needle, point) >= LOCK:
                a = _toward(needle, point, LOCK)
                out += [[*needle, 'STITCH'], [*a, 'STITCH'], [*needle, 'STITCH']]
            else:
                out.append([*needle, 'STITCH'])
            cutting = False
        elif cutting and command in ('COLOR_CHANGE', 'END'):
            cutting = False
        out.append([x, y, command])
        if command in ('STITCH', 'JUMP'):
            needle = point
    return out, removed
