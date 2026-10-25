"""Satin here: cut a piece where a thin part starts; that side becomes satin over the rest's fill."""
from pathlib import Path

import numpy as np
from PIL import Image
from shapely.geometry import Polygon

RED = (200, 30, 60)


def setup(tmp_path):
    from embroiderly.web import create_app
    rgba = np.zeros((400, 400, 4), np.uint8)
    rgba[100:260, 100:260] = [*RED, 255]   # a 32 mm square body
    rgba[170:190, 260:360] = [*RED, 255]   # a 4 mm wide, 20 mm long bar on its right
    (tmp_path/'work/uploads').mkdir(parents=True)
    Image.fromarray(rgba).save(tmp_path/'work/uploads/p.png')
    client = create_app(tmp_path).test_client()
    options = {'height_mm': 80, 'floor_mm2': 1, 'smooth': 0, 'mask_holes_mm2': 0, 'count': 2}
    body = client.post('/artwork/p.png', json=dict(options=options)).get_json()
    assert body['report']['piece_layout']['pieces'], body.get('error')
    return client, options, body


def command(client, options, body, field, x_px):
    layout = body['report']['piece_layout']
    x = x_px*layout['scale']-layout['origin_mm'][0]
    return client.post('/artwork/p.png', json=dict(
        options=options, piece_revision=body['piece_revision'], subject_confirmed=True,
        piece_command=dict(ids=[layout['pieces'][0]['id']], field=field, value=[[x, -50], [x, 50]]))).get_json()


def area(piece):
    return Polygon(piece['rings_mm'][0], piece['rings_mm'][1:]).area


def test_the_thin_side_becomes_satin_over_the_fill(tmp_path):
    client, options, body = setup(tmp_path)
    whole = area(body['report']['piece_layout']['pieces'][0])
    done = command(client, options, body, 'split_satin', 262)
    assert done.get('options'), done.get('error')
    pieces = done['report']['piece_layout']['pieces']
    assert [p['style'] for p in pieces] == ['tatami', 'satin']   # the fill is sewn first, the satin on top
    fill, satin = pieces
    assert satin['width_mm'] < 25 and fill['width_mm'] > 30
    # The satin reaches under the fill by about 0.4 mm along the 4 mm cut: no gap at the join.
    overlap = area(fill)+area(satin)-whole
    assert 1 < overlap < 3


def test_satin_here_passes_the_release_gate(tmp_path):
    from embroiderly.release_gate import checked_bytes
    client, options, body = setup(tmp_path)
    done = command(client, options, body, 'split_satin', 262)
    assert done.get('options'), done.get('error')
    stitched = client.post('/artwork/p.png', json=dict(options=done['options'], piece_revision=done['piece_revision'],
                                                        subject_confirmed=True, digitize=True)).get_json()
    assert stitched.get('playback'), stitched.get('error')
    assert len(stitched['playback']['colors']) == 1   # one thread: no extra colour change
    assert checked_bytes(tmp_path/'work'/'inkstitch-preview'/Path(stitched['prepared_name']).stem, 'dst')


def test_a_cut_through_the_wide_body_is_refused(tmp_path):
    client, options, body = setup(tmp_path)
    refused = command(client, options, body, 'split_satin', 180)
    assert 'narrow enough for satin' in (refused.get('error') or '')


def test_the_plain_knife_keeps_one_style(tmp_path):
    client, options, body = setup(tmp_path)
    done = command(client, options, body, 'knife', 262)
    assert [p['style'] for p in done['report']['piece_layout']['pieces']] == ['tatami', 'tatami']
