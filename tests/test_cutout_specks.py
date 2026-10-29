"""Cut-out subject: tiny parts on the edge of the removed background stay inside it.

A real AI run on a rose (Oct 2026): the background left out, a colour merged into
another to save cuts, and the file check failed with "stitches cross empty areas". The
merge itself was not the cause: any change that leaves a sliver thinner than one fill row
on the subject's edge (a one-pixel line of darker red along a petal) did it. Such a part
was sewn as a 0.5 mm tack always pointing right, and a lock on a path shorter than the
lock ran straight on past its end; next to the removed background both left the subject.
"""
import math
from pathlib import Path

import numpy as np
from PIL import Image
from shapely.geometry import Point, Polygon

from embroiderly.stitch_engine import _with_locks
from embroiderly.stitch_fills import tatami
from embroiderly.release_gate import checked_bytes
from embroiderly.web import create_app


def test_a_part_thinner_than_one_row_is_tacked_along_itself():
    # 0.1 mm wide, 0.3 mm tall: no fill row crosses it, so it is a tack.
    sliver = Polygon([(0, .25), (.1, .25), (.1, .55), (0, .55)])
    runs = tatami(sliver, 0, .4, 3.0, 4, .45, underlay=False)
    points = [p for run in runs for p in run]
    assert points and math.dist(*points[:2]) >= .45
    # Centred on the part along its long side: it overhangs by (0.5 - 0.3) / 2 at most.
    assert max(sliver.distance(Point(p)) for p in points) <= .1 + 1e-6


def test_a_lock_on_a_path_shorter_than_the_lock_stays_on_the_path():
    path = [(0.0, 0.0), (.45, 0.0)]
    sewn = _with_locks(path, [.6, 0, .6, 0], [.6, 0, .6, 0])
    assert all(-1e-9 <= x <= .45 + 1e-9 and abs(y) < 1e-9 for x, y in sewn)
    assert all(math.dist(a, b) >= .3 for a, b in zip(sewn, sewn[1:]) if math.dist(a, b) > 1e-9)


def test_slivers_on_the_edge_of_a_cut_out_subject_pass_the_file_check(tmp_path):
    (tmp_path/'work/uploads').mkdir(parents=True)
    # 768 px for 100 mm: 0.13 mm a pixel. A red petal on a removed (transparent) background,
    # its edge lined with a one-pixel line of darker red that joins a darker part on the right.
    # The line's fill shape breaks into slivers thinner than one row along the edge.
    rgba = np.zeros((768, 600, 4), np.uint8)
    yy, xx = np.mgrid[:768, :600]
    petal = (xx-300)**2/220**2+(yy-384)**2/300**2 <= 1
    rgba[petal] = [200, 20, 30, 255]
    edge = petal & ~((xx-300)**2/219**2+(yy-384)**2/299**2 <= 1)
    rgba[edge | petal & (xx > 470)] = [150, 12, 24, 255]
    Image.fromarray(rgba).save(tmp_path/'work/uploads/p.png')
    client = create_app(tmp_path).test_client()
    options = {'height_mm': 100, 'count': 2, 'smooth': 0, 'floor_mm2': 0, 'protect_selection': True}
    body = client.post('/artwork/p.png', json=dict(options=options, subject_confirmed=True, digitize=True)).get_json()
    assert body.get('playback'), body.get('error')
    assert checked_bytes(tmp_path/'work'/'inkstitch-preview'/Path(body['prepared_name']).stem, 'dst')
