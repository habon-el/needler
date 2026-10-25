"""Printable worksheet: sequence, threads, stops, backing, hoop and the design at actual size."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from embroiderly.worksheet import blocks, hoop_for, summary  # noqa: E402


def test_blocks_follow_thread_changes_and_count_stitches_and_cuts():
    steps = [dict(t='stitch', x=0, y=0), dict(t='stitch', x=1, y=0), dict(t='trim', x=1, y=0),
             dict(t='color_change', x=1, y=0), dict(t='stitch', x=2, y=0), dict(t='end', x=2, y=0)]
    assert blocks(steps, ['#ff0000', '#00ff00']) == [dict(colour='#ff0000', stitches=2, trims=1),
                                                     dict(colour='#00ff00', stitches=1, trims=0)]


def test_hoop_is_the_smallest_that_fits_either_way_round():
    assert hoop_for(80, 80) == (100, 100)
    assert hoop_for(170, 110) == (130, 180)
    assert hoop_for(500, 500) is None


def test_puff_stop_is_noted():
    steps = [dict(t='stitch', x=0, y=0), dict(t='stitch', x=5, y=5), dict(t='color_change', x=5, y=5),
             dict(t='stitch', x=0, y=0), dict(t='stitch', x=5, y=5)]
    info = summary(dict(steps=steps, colors=['#202020', '#202020'], puff=dict(threads=[1], foam_mm=3)))
    assert 'foam' in info['sequence'][1]['notes'][0] and info['changes'] == 1


def test_design_worksheet_page(tmp_path):
    from test_piece_editing import route_setup
    client, options, r = route_setup(tmp_path)
    body = client.post('/artwork/p.png', json=dict(options=options, subject_confirmed=True, digitize=True)).get_json()
    assert body.get('playback'), body.get('error')
    page = client.get('/worksheet/'+body['prepared_name'])
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert 'Sewing sequence' in html and 'Backing' in html and 'Hoop' in html
    assert len(re.findall(r'<tr><td>\d+</td>', html)) == len(body['playback']['colors'])
    # The picture is at actual size: millimetre units.
    assert re.search(r'<svg[^>]+width="[\d.]+mm"', html)
    assert client.get('/worksheet/nothing.png').status_code == 404


def test_lettering_worksheet_page(tmp_path):
    from embroiderly.web import create_app
    client = create_app(tmp_path).test_client()
    result = client.post('/lettering/native/check', json=dict(text='Hello', font='graduate', height_mm=10,
                                                               available_width_mm=100, colour='#1e3a6e')).get_json()
    assert result.get('id'), result
    html = client.get(f"/lettering/native/{result['id']}/worksheet").get_data(as_text=True)
    assert '<h1>Hello</h1>' in html and '#1e3a6e' in html
