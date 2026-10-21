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
