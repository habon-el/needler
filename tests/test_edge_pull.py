"""Whole picture stitched: satin areas on the picture's edge are pulled past it.

Satin is widened by its pull compensation, and the release gate already treats that
band as sewn. A mask the size of the picture cut the band off at the edge, so every
satin stitch there failed as "a stitch crosses a removed area" (a 56 x 100 mm
portrait, Oct 2026: 104 stitches, with or without a border).
"""
from pathlib import Path

import numpy as np
from PIL import Image

from embroiderly.engine import edge_pull
from embroiderly.release_gate import checked_bytes, read_context
from embroiderly.web import create_app


def test_edge_pull_grows_only_where_a_pulled_band_meets_the_edge():
    inner = np.zeros((20, 20), np.uint8); inner[5:15, 5:15] = 1
    assert edge_pull([(inner, 1)], 0, (20, 20)) == (0, None)
    edge = np.zeros((20, 20), np.uint8); edge[5:15, 17:] = 1
    pad, band = edge_pull([(edge, 1)], 0, (20, 20))
    assert pad == 1 and band.shape == (22, 22)
    assert band[6:16, 21].all() and not band[:, 0].any() and not band[0, :6].any()


def test_satin_on_the_picture_edge_passes_the_release_gate(tmp_path):
    (tmp_path/'work/uploads').mkdir(parents=True)
    # 768 px for 100 mm (0.13 mm a pixel): a 0.1 mm pull is then a whole pixel.
    rgb = np.full((768, 431, 3), [96, 112, 112], np.uint8)
    rgb[200:560, 60:330] = [40, 40, 40]
    rgb[:, 416:] = [200, 60, 60]       # 2 mm band along the right edge: satin
    rgb[:15, 100:300] = [60, 60, 200]  # 2 mm band along the top edge: satin
    Image.fromarray(rgb).save(tmp_path/'work/uploads/p.png')
    client = create_app(tmp_path).test_client()
    options = {'height_mm': 100, 'count': 4, 'smooth': 0, 'selection': 'full'}
    body = client.post('/artwork/p.png', json=dict(options=options, subject_confirmed=True, digitize=True)).get_json()
    assert body.get('playback'), body.get('error')
    directory = tmp_path/'work'/'inkstitch-preview'/Path(body['prepared_name']).stem
    assert checked_bytes(directory, 'dst')
    # Only the pull is allowed: the checked canvas grew by a pixel or two, no more.
    record, mask = read_context(directory)
    assert 0 < mask.shape[1]-431 <= 4 and not mask[:, 0].any()
