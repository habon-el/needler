"""Rose: no gaps between neighbouring colours, and leaves that are not flat.

Found Oct 2026 on a rose in Digitize for me. Gaps: a petal netted by darker shading is
thin everywhere (no part wider than 4.5 mm), so it was sewn as satin; satin columns cannot
follow a net, and its wedges and tips stayed bare between the colours. Such an area is now
filled when its columns would cover under 90% of it. Flat leaves: every leaf was one fill in
one direction; a leaf (longer than wide, tapering to its tip) is now sewn in two sides, each
angled from the midrib the other way, so the light falls differently on them.
"""
import json
import math
import re

import cv2
import numpy as np
from PIL import Image, ImageDraw

from embroiderly.engine import STROKE_SATIN_MM, digitize, satin_gaps, stroke_like, thickness_mm
from embroiderly.fill_shaping import leaf_halves
from embroiderly.release_gate import checked_bytes


def lens(size=(400, 400), length=300, width=160):
    plane = np.zeros(size, np.uint8)
    top = [[50+x, 200-int(width/2*math.sin(math.pi*x/length))] for x in range(0, length+1, 10)]
    bottom = [[50+x, 200+int(width/2*math.sin(math.pi*x/length))] for x in range(length, -1, -10)]
    cv2.fillPoly(plane, [np.array(top+bottom)], 1)
    return plane


def rings_of(plane):
    contours, hierarchy = cv2.findContours(plane, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    outer = max((i for i in range(len(contours)) if hierarchy[0, i, 3] == -1), key=lambda i: cv2.contourArea(contours[i]))
    rings, child = [contours[outer]], hierarchy[0, outer, 2]
    while child != -1:
        rings.append(contours[child]); child = hierarchy[0, child, 0]
    return rings


def test_a_leaf_is_sewn_in_two_sides_angled_from_its_midrib():
    halves = leaf_halves(rings_of(lens()), (400, 400), .25)
    assert halves is not None
    (_, first, a), (_, second, b) = halves
    # Mirror angles about the midrib (here level): 40 degrees each way.
    assert sorted((round(first), round(second))) == [40, 140]
    assert not (a & b).any() and abs(int(a.sum())-int(b.sum())) < .1*(a.sum()+b.sum())
    for shape in (cv2.ellipse(np.zeros((400, 400), np.uint8), (200, 200), (150, 60), 0, 0, 360, 1, -1),
                  cv2.rectangle(np.zeros((400, 400), np.uint8), (50, 140), (350, 260), 1, -1),
                  cv2.circle(np.zeros((400, 400), np.uint8), (200, 200), 120, 1, -1)):
        assert leaf_halves(rings_of(shape), (400, 400), .25) is None


def petal():
    """A red petal shaded with many small dark pockets, as colour reduction leaves a photo's
    petal: the red between them is a branched net no wider than about 5 mm."""
    rng = np.random.default_rng(0)
    image = Image.new('RGBA', (400, 400), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((60, 80, 340, 320), fill=(200, 20, 30, 255))
    for _ in range(260):
        cx, cy, r, a = rng.uniform(70, 330), rng.uniform(90, 310), rng.uniform(6, 16), rng.uniform(0, 6.3)
        draw.polygon([(cx+r*rng.uniform(.5, 1.6)*math.cos(a+k*2.1), cy+r*rng.uniform(.5, 1.6)*math.sin(a+k*2.1))
                      for k in range(3)], fill=(120, 10, 20, 255))
    # Smoothed like colour reduction does, so no speck is too small to sew.
    rgba = np.asarray(image)
    labels = cv2.medianBlur(np.where(rgba[..., 3] == 0, 0, np.where(rgba[..., 0] == 200, 1, 2)).astype(np.uint8), 5)
    for _ in range(3):
        for label in (1, 2):
            count, parts, stats, _ = cv2.connectedComponentsWithStats((labels == label).astype(np.uint8), 4)
            for i in range(1, count):
                if stats[i, 4] < 40:
                    labels[parts == i] = 3-label
    labels = cv2.medianBlur(labels, 3)
    out = np.zeros_like(rgba)
    out[labels == 1], out[labels == 2] = (200, 20, 30, 255), (120, 10, 20, 255)
    return Image.fromarray(out)


def test_a_netted_petal_is_filled_not_satin_and_passes_the_file_check(tmp_path):
    image = petal()
    source = tmp_path/'petal.png'
    image.save(source)
    source.with_suffix('.prep.json').write_text(json.dumps({'options': {'height_mm': 100}, 'report': {}}))
    rgba = np.asarray(image.convert('RGBA'))
    red = tuple(int(v) for v in rgba[(rgba[..., 0] > 150) & (rgba[..., 3] > 127)][0, :3])
    rings = rings_of((np.all(rgba[..., :3] == red, axis=2) & (rgba[..., 3] > 127)).astype(np.uint8))
    # Thin enough to have been satin; its columns would leave wedges bare.
    assert thickness_mm(rings, .25) <= STROKE_SATIN_MM and stroke_like(rings, .25, thickness_mm(rings, .25))
    assert satin_gaps(rings, .25, thickness_mm(rings, .25))
    digitize(source, tmp_path/'out', 100)
    svg = (tmp_path/'out'/'design.svg').read_text(encoding='utf-8')
    largest = max((p for p in re.findall(r'<path [^>]*>', svg) if 'fill:#%02x%02x%02x' % red in p), key=len)
    assert 'auto_satin' not in largest and 'angle=' in largest
    assert checked_bytes(tmp_path/'out', 'dst')


def test_a_simple_band_stays_satin():
    plane = cv2.rectangle(np.zeros((400, 400), np.uint8), (40, 190), (360, 205), 1, -1)
    assert not satin_gaps(rings_of(plane), .25, 4.0)
