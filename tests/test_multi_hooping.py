"""Multi-hooping: a design bigger than the hoop is split into hoopings that each fit, cut cleanly
on the seams, share alignment marks, and download as checked machine files."""
import math

import pyembroidery as emb
import pytest

from embroiderly import multi_hooping as mh


def test_plan_counts_hoopings():
    assert mh.plan(0, 0, 90, 90, [100, 100]) == (1, 1)
    assert mh.plan(0, 0, 180, 60, [100, 100]) == (2, 1)
    assert mh.plan(0, 0, 180, 100.5, [100, 100]) == (2, 2)
    with pytest.raises(ValueError):
        mh.plan(0, 0, 200, 50, [25, 100])
    with pytest.raises(ValueError):
        mh.plan(0, 0, 900, 900, [100, 100])


def fill(left, right, top, bottom, spacing=4, step=30):
    """Tatami-like rows (tenths of mm) from left to right and back, one run."""
    points, y, forward = [], top, True
    while y <= bottom:
        xs = list(range(left, right+1, step))
        points += [(x, y) for x in (xs if forward else xs[::-1])]
        y, forward = y+spacing, not forward
    return points


def pattern(*runs):
    out = emb.EmbPattern()
    for n, points in enumerate(runs):
        if n:
            out.add_stitch_absolute(emb.TRIM, *points[0])
        out.add_stitch_absolute(emb.JUMP, *points[0])
        for p in points:
            out.add_stitch_absolute(emb.STITCH, *p)
    out.add_thread(emb.EmbThread())
    out.add_stitch_absolute(emb.END, 0, 0)
    return out


def test_fill_across_the_seam_is_cut_cleanly_and_fits_each_hoop():
    hoopings = mh.split(pattern(fill(-900, 900, -300, 300)), [100, 100])
    assert [h['n'] for h in hoopings] == [1, 2]
    for h in hoopings:
        cx, cy = h['centre']
        stitches = [p for _, run in h['runs'] for p in run]
        assert all(abs(x-cx) <= 500-mh.EDGE_MM*10 and abs(y-cy) <= 500 for x, y in stitches)
        lengths = [math.dist(a, b) for _, run in h['runs'] for a, b in zip(run, run[1:]) if math.dist(a, b) > 1e-6]
        assert min(lengths) >= 3 and max(lengths) <= 70
        # Rows turning on the seam keep sewing along it: one part per hooping, not one per row.
        assert len(h['runs']) == 1
    seam = hoopings[0]['cell'][2]
    assert hoopings[0]['marks_last'] == hoopings[1]['marks_first'] and all(x == seam for x, _ in hoopings[1]['marks_first'])
    rebuilt = mh._pattern(hoopings[1], [emb.EmbThread()])
    assert [t.description for t in rebuilt.threadlist] == ['Alignment marks', None]


def test_every_sewn_stitch_is_long_enough_after_rounding():
    # The file stores whole tenths of a mm. These two points are 0.311 mm apart but land on
    # grid points 0.283 mm apart, which the machine-file check refuses.
    chain = mh._tidy([(.55, .55), (2.75, 2.75), (30, 30), (60, 60)], True, True)
    assert all(isinstance(v, int) for p in chain for v in p)
    assert min(math.dist(a, b) for a, b in zip(chain, chain[1:]) if a != b) >= 3


def test_seam_falls_in_the_gap_between_objects():
    left, right = fill(-900, -100, -200, 200), fill(150, 900, -200, 200)
    hoopings = mh.split(pattern(left, right), [100, 100])
    assert -100 <= hoopings[0]['cell'][2] <= 150
    assert [len(h['runs']) for h in hoopings] == [1, 1]
    # Nothing was cut, so no tie-offs were added.
    assert len(hoopings[0]['runs'][0][1]) == len(left)


def test_hoopings_download_as_checked_files(tmp_path):
    from PIL import Image, ImageDraw
    from embroiderly.web import create_app
    client = create_app(tmp_path).test_client()
    image = Image.new('RGB', (600, 200), 'white')
    ImageDraw.Draw(image).rectangle((20, 40, 580, 160), fill='#1d4f91')
    image.save(tmp_path/'work/uploads/wide.png')
    options = dict(artwork_type='logo', count=2, height_mm=60)
    for _ in range(3):
        body = client.post('/artwork/wide.png', json=dict(options=options, digitize=True, subject_confirmed=True)).get_json()
        if body.get('code') != 'cleanup_review_required':
            break
        options['cleanup_decisions'] = {item['id']: 'drop' for item in body['report']['cleanup_review']}
    name = body['prepared_name']
    assert client.get(f'/api/hoopings/{name}/200x200').get_json()['hoopings'] == []
    plan = client.get(f'/api/hoopings/{name}/100x100').get_json()
    assert len(plan['hoopings']) == 2 and plan['field_mm'] == [100, 100] and plan['origin_mm']
    for h in plan['hoopings']:
        for fmt in ('dst', 'pes', 'jef'):
            response = client.get(f'/hooping/{name}/100x100/{h["n"]}/{fmt}')
            assert response.status_code == 200, response.get_data(as_text=True)
            assert f'hooping-{h["n"]}-of-2.{fmt}' in response.headers['Content-Disposition']
        (tmp_path/'part.pes').write_bytes(client.get(f'/hooping/{name}/100x100/{h["n"]}/pes').data)
        left, top, right, bottom = emb.EmbPattern(str(tmp_path/'part.pes')).extents()
        assert max(abs(left), abs(right), abs(top), abs(bottom)) <= 500
    assert client.get(f'/hooping/{name}/100x100/3/dst').status_code == 404
    assert client.get(f'/api/hoopings/{name}/5x100').status_code == 404
    assert client.get(f'/api/hoopings/{name}/25x100').status_code == 422
