"""Smart satin: thin limbs of thick areas, and long bands, are sewn as satin that follows the shape."""
import cv2
import numpy as np
import pytest

from embroiderly.engine import thin_limbs, stroke_like, thickness_mm, area_mm2
from embroiderly.region_stitches import satin_reason


def rings_of(mask):
    contours, hierarchy = cv2.findContours(mask.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    i = max(range(len(contours)), key=lambda k: cv2.contourArea(contours[k]))
    return [contours[i]]


def creature():
    m = np.zeros((500, 500), np.uint8)
    cv2.circle(m, (200, 220), 90, 1, -1)
    cv2.line(m, (200, 300), (200, 420), 1, 14)
    for dx in (-30, 0, 30):
        cv2.line(m, (200, 420), (200+dx, 470), 1, 8)
    return m


def test_thin_limbs_split_off_with_overlap_and_nothing_lost():
    scale = .18
    rings = rings_of(creature())
    body, limbs = thin_limbs(rings, scale)
    assert len(limbs) == 1   # stem and claws: one connected limb
    whole = area_mm2(rings, scale)
    parts = area_mm2(body, scale)+sum(area_mm2(l, scale) for l in limbs)
    assert whole < parts < whole*1.1   # every bit is sewn; body and limb overlap a little
    assert thickness_mm(limbs[0], scale) < 4.5


def test_round_areas_and_small_bumps_stay_whole():
    m = np.zeros((300, 300), np.uint8)
    cv2.circle(m, (150, 150), 100, 1, -1)
    cv2.circle(m, (240, 150), 20, 1, -1)   # a bump on the edge, not a limb
    rings = rings_of(m)
    body, limbs = thin_limbs(rings, .18)
    assert limbs == [] and body is rings


def test_long_bands_are_stroke_like():
    m = np.zeros((400, 400), np.uint8)
    cv2.ellipse(m, (200, 200), (120, 160), 0, -60, 200, 1, 30)
    rings = rings_of(m)
    thick = thickness_mm(rings, .18)
    assert 4.5 < thick <= 6.5 and stroke_like(rings, .18, thick)
    blob = rings_of(cv2.circle(np.zeros((400, 400), np.uint8), (200, 200), 18, 1, -1))
    assert not stroke_like(blob, .18, thickness_mm(blob, .18))


def test_satin_choice_accepts_curved_bands_but_not_wide_areas():
    m = np.zeros((400, 400), np.uint8)
    cv2.ellipse(m, (200, 200), (120, 160), 0, -60, 200, 1, 30)
    assert satin_reason(rings_of(m), .18) == ''
    wide = rings_of(cv2.circle(np.zeros((400, 400), np.uint8), (200, 200), 150, 1, -1))
    assert '8 mm' in satin_reason(wide, .18)


@pytest.mark.parametrize('smart', [False, True])
def test_creature_passes_the_release_gate(tmp_path, smart):
    from PIL import Image
    from embroiderly.web import create_app
    from embroiderly.release_gate import checked_bytes
    (tmp_path/'work/uploads').mkdir(parents=True)
    rgba = np.zeros((500, 500, 4), np.uint8)
    rgba[creature() > 0] = [200, 30, 60, 255]
    Image.fromarray(rgba).save(tmp_path/'work/uploads/p.png')
    client = create_app(tmp_path).test_client()
    options = {'height_mm': 90, 'floor_mm2': 1, 'smooth': 0, 'mask_holes_mm2': 0, 'count': 2, 'smart_satin': smart}
    body = client.post('/artwork/p.png', json=dict(options=options, subject_confirmed=True, digitize=True)).get_json()
    assert body.get('playback'), body.get('error')
    assert checked_bytes(tmp_path/'work'/'inkstitch-preview'/__import__('pathlib').Path(body['prepared_name']).stem, 'dst')
