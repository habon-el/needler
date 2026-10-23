import json
import time

from PIL import ImageDraw

from embroiderly.web import create_app
from test_auto_digitize import badge


def _auto(client, name, request):
    client.post('/api/auto-digitize/' + name, json={'request': request})
    for _ in range(240):
        job = client.get('/api/auto-digitize/' + name).get_json()
        if job['state'] != 'running':
            return job
        time.sleep(.5)
    return job


def test_puff_logo_stops_for_foam_sews_puff_last_and_passes_checks(tmp_path):
    app = create_app(tmp_path)
    badge().save(tmp_path / 'work/uploads/badge.png')
    job = _auto(app.test_client(), 'badge.png', '60 mm wide, 3D puff')
    assert job['state'] == 'done', job
    puff = job['result']['puff']
    assert puff['foam_mm'] == 3 and puff['threads']
    preview = max((tmp_path / 'work/inkstitch-preview').iterdir(), key=lambda d: d.stat().st_mtime)
    playback = json.loads((preview / 'playback.json').read_text())
    assert playback['puff'] == puff
    # Every puff thread comes after every flat thread: one stop, then foam work.
    threads = list(range(len(playback['colors'])))
    assert puff['threads'] == threads[-len(puff['threads']):] and puff['threads'][0] > 0
    # Puff satin is dense: consecutive needle points on a rail are close together.
    thread, sewn = 0, []
    for step in playback['steps']:
        thread += step['t'] == 'color_change'
        if step['t'] == 'stitch' and thread in puff['threads']:
            sewn.append(step)
    assert len(sewn) > 300


def test_flat_parts_stay_flat_when_too_wide(tmp_path):
    app = create_app(tmp_path)
    image = badge()
    ImageDraw.Draw(image).rectangle((0, 0, 399, 299), fill='#1d4f91')  # one big solid area
    image.save(tmp_path / 'work/uploads/block.png')
    job = _auto(app.test_client(), 'block.png', '80 mm wide, puff')
    assert job['state'] == 'done'
    assert 'puff' not in job['result'] and any('sewn flat' in i for i in job['result']['issues'])


def test_puff_letters_pass_and_thin_letters_are_refused(tmp_path):
    client = create_app(tmp_path).test_client()
    body = dict(text='PUFF', font='lato_black', align='center', available_width_mm=200, colour='#c0392b', puff=True)
    # Lato Black strokes reach 3 mm (the foam thickness) at about 21 mm; puff letters may go above the flat limit.
    data = client.post('/lettering/native/check', json={**body, 'height_mm': 22}).get_json()
    assert data['checks_passed'] and data['recipe']['puff'] is True, data
    flat = client.post('/lettering/native/check', json={**body, 'height_mm': 15, 'puff': False}).get_json()
    assert flat['checks_passed']
    workspace = client.get(f"/lettering/native/{data['id']}/workspace-data").get_json()
    # Placement lines, a stop, then the letters over foam.
    assert workspace['playback']['puff'] == {'threads': [1], 'foam_mm': 3.0}
    assert sum(s['t'] == 'color_change' for s in workspace['playback']['steps']) == 1
    thin = client.post('/lettering/native/check', json={**body, 'height_mm': 12})
    # Refused before stitching, with the heights that do work for these words.
    assert thin.status_code in (400, 422) and 'with 3D puff on 3 mm foam' in json.dumps(thin.get_json(), ensure_ascii=False)
    # 2 mm foam holds on thinner strokes.
    two = client.post('/lettering/native/check', json={**body, 'height_mm': 15, 'puff_foam_mm': 2}).get_json()
    assert two['checks_passed'] and two['recipe']['puff_foam_mm'] == 2
    # Flat letters above the satin range are sewn as tatami fill instead of refused.
    big = client.post('/lettering/native/check', json={**body, 'height_mm': 22, 'puff': False}).get_json()
    assert big['checks_passed'] and 'puff' not in big['recipe']


def test_puff_column_is_tacked_capped_underlaid_then_covered():
    from embroiderly.stitch_satin import PUFF_LONGEST_MM, satin
    a = [(0, 0), (20, 0)]; b = [(0, 4), (20, 4)]
    points = satin([(a, False), (b, False)], .22, .45, puff=True)
    plain = satin([(a, False), (b, False)], .22, .4)
    # Tack-down walk along the middle first, at most 1.7 mm per stitch.
    assert points[0][1] == 2 and all(abs(p[1]-2) < 1e-6 for p in points[:5])
    # Caps: short stitches along the column inside each open end, before the satin.
    satin_start = len(points) - len(plain)
    caps = [p for p in points[:satin_start] if p[0] in (0, 20) and 0 <= p[1] <= 4]
    assert len(caps) > 10
    # Zigzag underlay, then dense satin with pull compensation, never longer than the limit.
    assert points[satin_start:] == plain
    widths = [abs(points[i][1]-points[i+1][1]) for i in range(satin_start, len(points)-1)]
    assert max(widths) <= PUFF_LONGEST_MM and max(widths) > 4.7
    wide = satin([([(0, 0), (20, 0)], False), ([(0, 6.5), (20, 6.5)], False)], .22, .4, puff=True)
    assert max(abs(wide[i][1]-wide[i+1][1]) for i in range(len(wide)-1)) <= PUFF_LONGEST_MM + 1e-9


def test_puff_area_places_foam_before_the_stop_and_locks_firmly():
    from embroiderly.stitch_engine import generate
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkstitch="http://inkstitch.org/namespace" '
           'width="40mm" height="20mm" viewBox="0 0 40 20">'
           '<path d="M 2 10 L 30 10 L 30 18 L 2 18 Z" style="fill:#0000ff"/>'
           '<path d="M 2 2 L 30 2 L 30 6 L 2 6 Z" style="fill:#ff0000" inkstitch:fill_method="puff_satin"/></svg>')
    plan = generate(svg)
    assert [t['color'] for t in plan['threadlist']] == ['#0000ff', '#ff0000', '#ff0000']
    assert plan['extras'] == {'puff_threads': [2]}
    commands = [s[2] for s in plan['stitches']]
    stop = [i for i, c in enumerate(commands) if c == 'COLOR_CHANGE'][-1]
    over_foam = [s for s in plan['stitches'][stop:] if s[2] == 'STITCH']
    # The first stitches over foam tack it down along the outline, 1 mm apart, after a six-stitch lock.
    first = over_foam[7:20]
    steps = [((p[0]-q[0])**2+(p[1]-q[1])**2)**.5/10 for p, q in zip(first, first[1:])]
    assert max(steps) <= 1.05
    # Too narrow for 3 mm foam: sewn flat.
    narrow = svg.replace('M 2 2 L 30 2 L 30 6 L 2 6 Z', 'M 2 2 L 30 2 L 30 4.5 L 2 4.5 Z')
    assert generate(narrow)['extras'] == {}
    assert generate(narrow.replace('fill_method="puff_satin"', 'fill_method="puff_satin" inkstitch:puff_foam_mm="2"'))['extras']
