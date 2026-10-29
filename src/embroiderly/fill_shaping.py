"""How a professional shapes plain fills before stitching.

Overlap: a colour sewn earlier reaches a little under the colours sewn after
it, so the fabric pulling in never opens a gap of bare fabric between two
colours. It never grows into empty fabric or into colours sewn before it.

Angle: tatami rows run along the long side of a shape (fewer, steadier rows);
round or square shapes use 45 degrees, which hides the rows best against the
fabric weave.
"""
import math

import cv2
import numpy as np

OVERLAP_MM = .35     # under the next colour; professional practice is about 0.3-0.5 mm
ROUND_RATIO = 1.3    # long/short below this counts as round or square


def grown(rings, later, scale):
    """Contours of one area (rings: outer + holes, pixel coordinates) grown by
    OVERLAP_MM under `later` (pixels of colours sewn afterwards)."""
    h, w = later.shape
    area = np.zeros((h, w), np.uint8)
    cv2.drawContours(area, rings[:1], -1, 1, -1)
    for hole in rings[1:]:
        cv2.drawContours(area, [hole], -1, 0, -1)
    # A hole's contour runs on this area's own pixels: put them back after clearing the hole.
    cv2.drawContours(area, rings[1:], -1, 1, 1)
    steps = max(1, int(round(OVERLAP_MM / scale)))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * steps + 1, 2 * steps + 1))
    out = (cv2.dilate(area, kernel).astype(bool) & (area.astype(bool) | later)).astype(np.uint8)
    contours, hierarchy = cv2.findContours(out, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return [rings]
    parts = []
    for i, c in enumerate(contours):
        if hierarchy[0, i, 3] != -1:
            continue
        ring = [c]
        child = hierarchy[0, i, 2]
        while child != -1:
            ring.append(contours[child])
            child = hierarchy[0, child, 0]
        parts.append(ring)
    return parts or [rings]


def angle(rings):
    """Tatami row angle in degrees for the area's outer ring (image axes, y down)."""
    points = rings[0][:, 0, :].astype(np.float32)
    if len(points) < 3:
        return 45.0
    (_, _), (w, h), a = cv2.minAreaRect(points)
    if min(w, h) <= 0 or max(w, h) / min(w, h) < ROUND_RATIO:
        return 45.0
    long_side = a if w >= h else a + 90
    # minAreaRect measures in image axes (y down); the fill angle turns the other way.
    return float(-long_side % 180)


LEAF_RATIO = 1.4     # long/short at least this: a leaf or petal, not a round blob
LEAF_TIP = .6        # 12% in from its tip narrower than this share of its widest: tapered (an ellipse is .65)
LEAF_BASE = .8       # ... and not square at the other end
LEAF_TURN = 40.0     # stitches turn this far from the midrib, opposite ways on its two sides
LEAF_MIN_MM2 = 20.0


def leaf_halves(rings, shape, scale):
    """A leaf-shaped area (longer than wide, tapering to its tip) split along its midrib: [(rings, angle,
    pixels)] for its two sides, rows on each turned LEAF_TURN degrees from the midrib the other
    way, as a digitizer sews a leaf so the light falls differently on its halves. None for any
    other shape. shape: the picture's (height, width)."""
    area = np.zeros(shape, np.uint8)
    cv2.drawContours(area, rings[:1], -1, 1, -1)
    for hole in rings[1:]:
        cv2.drawContours(area, [hole], -1, 0, -1)
    cv2.drawContours(area, rings[1:], -1, 1, 1)
    ys, xs = np.nonzero(area)
    if len(xs)*scale*scale < LEAF_MIN_MM2:
        return None
    # The long axis from the area's spread (a rectangle of least area lies diagonally on a leaf).
    cx, cy = xs.mean(), ys.mean()
    cov = np.cov(np.vstack((xs-cx, ys-cy)))
    values, vectors = np.linalg.eigh(cov)
    if values[0] <= 0 or math.sqrt(values[1]/values[0]) < LEAF_RATIO:
        return None
    theta = math.atan2(vectors[1, 1], vectors[0, 1])
    u, n = (math.cos(theta), math.sin(theta)), (-math.sin(theta), math.cos(theta))
    t = (xs-cx)*u[0]+(ys-cy)*u[1]
    s = (xs-cx)*n[0]+(ys-cy)*n[1]
    lo, hi = t.min(), t.max()
    def width(at):
        band = np.abs(t-at) <= max(1.0, .02*(hi-lo))
        return s[band].max()-s[band].min() if band.any() else 0.0
    widest = max(width(lo+(hi-lo)*k/20) for k in range(1, 20))
    ends = sorted((width(lo+.12*(hi-lo)), width(hi-.12*(hi-lo))))
    if widest <= 0 or ends[0] > LEAF_TIP*widest or ends[1] > LEAF_BASE*widest:
        return None
    # The midrib: the long axis through the middle of the area across it at its widest.
    side = np.zeros(shape, bool)
    side[ys, xs] = s > np.median(s)
    halves = []
    midrib = -math.degrees(theta) % 180   # fill angles turn the other way (angle() above)
    for pixels, turn in ((side & area.astype(bool), LEAF_TURN), (~side & area.astype(bool), -LEAF_TURN)):
        if pixels.sum() < .2*len(xs):
            return None
        contours, hierarchy = cv2.findContours(pixels.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        parts = []
        for i, c in enumerate(contours):
            if hierarchy[0, i, 3] != -1 or cv2.contourArea(c) < 4:
                continue
            ring = [c]
            child = hierarchy[0, i, 2]
            while child != -1:
                ring.append(contours[child])
                child = hierarchy[0, child, 0]
            parts.append(ring)
        if not parts:
            return None
        halves.append((parts, (midrib+turn) % 180, pixels))
    return halves
