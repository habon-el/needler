import math

import cv2
import numpy as np

from embroiderly.fill_shaping import OVERLAP_MM, angle, grown


def _rings(mask):
    contours, hierarchy = cv2.findContours(mask.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    outer = next(i for i in range(len(contours)) if hierarchy[0, i, 3] == -1)
    rings, child = [contours[outer]], hierarchy[0, outer, 2]
    while child != -1:
        rings.append(contours[child]); child = hierarchy[0, child, 0]
    return rings


def test_earlier_fill_reaches_under_the_next_colour_only():
    scale = .1  # mm per pixel
    frame = np.ones((100, 100), bool); frame[30:70, 30:70] = False   # background with a hole
    inner = ~frame                                                    # sewn after it
    parts = grown(_rings(frame), inner, scale)
    assert len(parts) == 1 and len(parts[0]) == 2                     # still one area with one hole
    out = np.zeros((100, 100), np.uint8)
    cv2.drawContours(out, parts[0][:1], -1, 1, -1); cv2.drawContours(out, parts[0][1:], -1, 0, -1)
    cv2.drawContours(out, parts[0][1:], -1, 1, 1)  # hole outlines are area pixels
    reach = round(OVERLAP_MM / scale)
    assert out[50, 30 + reach - 1] and not out[50, 30 + reach + 2]   # about 0.35 mm under the inner colour
    # Nothing to reach under: unchanged.
    alone = grown(_rings(inner), np.zeros((100, 100), bool), scale)
    assert cv2.contourArea(alone[0][0]) == cv2.contourArea(_rings(inner)[0])


def test_rows_follow_the_long_side_and_round_shapes_use_45():
    bar = np.zeros((300, 400), np.uint8)
    box = cv2.boxPoints(((200, 150), (300, 60), 30)).astype(np.int32)
    cv2.fillPoly(bar, [box], 1)
    # Image y points down: a bar tilted +30 degrees on screen is -30 (150) in fill terms.
    assert abs(angle(_rings(bar)) - 150) < 2
    disc = np.zeros((300, 300), np.uint8); cv2.circle(disc, (150, 150), 80, 1, -1)
    assert angle(_rings(disc)) == 45.0
