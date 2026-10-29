"""Recognize stitches: a machine file's stitches become pieces (fill, satin, line) that edit
and sew like any other piece."""
import json
import math
from pathlib import Path

import numpy as np
import pyembroidery as emb
import pytest

from embroiderly.stitch_recognize import open_file, pieces, read

RED, BLUE, GREEN = '#c81e1e', '#1e5ac8', '#1e9632'


def _sew(pattern, points):
    pattern.add_stitch_absolute(emb.JUMP, *points[0])
    for p in points:
        pattern.add_stitch_absolute(emb.STITCH, *p)
    pattern.add_stitch_absolute(emb.TRIM, *points[-1])


def machine_file(path):
    """A 30 x 20 mm tatami rectangle, a 4 x 25 mm satin column and a 30 mm running line,
    each in its own thread (units: 0.1 mm)."""
    pattern = emb.EmbPattern()
    pattern.add_thread(emb.EmbThread(RED)); pattern.add_thread(emb.EmbThread(BLUE)); pattern.add_thread(emb.EmbThread(GREEN))
    rows = []
    for n, y in enumerate(np.arange(0, 200.1, 4)):
        xs = list(np.arange(0, 300.1, 30))
        rows += [(x, y) for x in (xs if n % 2 == 0 else xs[::-1])]
    _sew(pattern, rows)
    pattern.add_stitch_absolute(emb.COLOR_CHANGE, *rows[-1])
    satin = [(400 + (40 if n % 2 else 0), 0 + n * 4) for n in range(63)]
    _sew(pattern, satin)
    pattern.add_stitch_absolute(emb.COLOR_CHANGE, *satin[-1])
    _sew(pattern, [(x, 300) for x in range(0, 301, 25)])
    pattern.add_stitch_absolute(emb.END, 300, 300)
    # PES version 6 keeps the exact thread colours.
    emb.write(pattern, str(path), {'version': 6} if path.suffix == '.pes' else {})
    return path


@pytest.mark.parametrize('suffix', ['.pes', '.dst'])
def test_a_machine_file_becomes_fill_satin_and_line_pieces(tmp_path, suffix):
    blocks = read(machine_file(tmp_path / ('design' + suffix)))
    assert len(blocks) == 3
    found = pieces(blocks)
    kinds = [p['kind'] for p in found]
    assert kinds == ['fill', 'satin', 'line']
    if suffix == '.pes':   # DST carries no thread colours
        assert [p['colour'] for p in found] == [RED, BLUE, GREEN]
    fill, satin, line = found
    xs = np.concatenate([np.asarray(r)[:, 0] for r in fill['rings']])
    ys = np.concatenate([np.asarray(r)[:, 1] for r in fill['rings']])
    assert np.ptp(xs) == pytest.approx(30.4, abs=.6) and np.ptp(ys) == pytest.approx(20.4, abs=.6)
    assert fill['angle'] == pytest.approx(0, abs=2)               # horizontal rows
    width = np.ptp(np.asarray(satin['rings'][0])[:, 0])
    assert 3.6 < width < 5
    assert line['stitch'] == 'running' and math.dist(line['rings'][0][0], line['rings'][0][-1]) == pytest.approx(30, abs=.2)


def test_triple_runs_and_travel_inside_a_fill_are_recognized(tmp_path):
    pattern = emb.EmbPattern(); pattern.add_thread(emb.EmbThread(RED))
    bean = [(0, 0)]
    for x in range(25, 301, 25):
        bean += [(x, 0), (x - 25, 0), (x, 0)]
    _sew(pattern, bean)
    pattern.add_stitch_absolute(emb.END, 300, 0)
    emb.write(pattern, str(tmp_path / 'bean.pes'))
    (line,) = pieces(read(tmp_path / 'bean.pes'))
    assert line['kind'] == 'line' and line['stitch'] == 'triple' and len(line['rings'][0]) == 2
    with pytest.raises(ValueError, match='machine file'):
        read(tmp_path / 'picture.png')


def test_the_pieces_open_as_a_design_that_edits_and_sews(tmp_path):
    from embroiderly.release_gate import checked_bytes
    from embroiderly.web import create_app
    client = create_app(tmp_path).test_client()
    with open(machine_file(tmp_path / 'design.pes'), 'rb') as handle:
        response = client.post('/upload', data=dict(image=(handle, 'design.pes')), content_type='multipart/form-data')
    assert response.status_code == 302, response.data
    name = response.headers['Location'].rsplit('/', 1)[-1]
    options = json.loads((tmp_path / 'work/decisions' / (name + '.preparation.json')).read_text())
    r = client.post('/artwork/' + name, json=dict(options=options)).get_json()
    assert not r.get('error'), r.get('error')
    pieces_ = r['report']['piece_layout']['pieces']
    # Only the recognized parts are pieces: the silhouette picture's own areas are not listed (or sewn).
    assert all(p['visible'] for p in pieces_) and not any(p['name'] == 'File outline' for p in pieces_)
    shown = sorted(pieces_, key=lambda p: int(p['name'].split()[-1]))
    assert [p['name'] for p in shown] == ['Fill 1', 'Satin 2', 'Line 3']
    assert [p['style'] for p in shown] == ['tatami', 'satin', 'line'] and [p['colour'] for p in shown] == [RED, BLUE, GREEN]
    assert all(p['audit']['level'] != 'red' for p in shown)
    fill = shown[0]
    assert fill['width_mm'] == pytest.approx(30.4, abs=.8) and fill['height_mm'] == pytest.approx(20.4, abs=.8)
    # Edit like any piece: move the fill, then sew; the release gate checks every stitch.
    body = client.post('/artwork/' + name, json=dict(
        options=options, piece_revision=r['piece_revision'], subject_confirmed=True, digitize=True,
        piece_command=dict(ids=[fill['id']], field='x_mm', value=fill['x_mm'] - 5))).get_json()
    assert body.get('playback'), body.get('error')
    moved = next(p for p in body['report']['piece_layout']['pieces'] if p['id'] == fill['id'])
    assert moved['x_mm'] == pytest.approx(fill['x_mm'] - 5, abs=.1)
    assert body['playback']['colors'] == [RED, BLUE, GREEN]   # the file's sewing order
    assert checked_bytes(tmp_path/'work'/'inkstitch-preview'/Path(body['prepared_name']).stem, 'dst')


# Files built the way commercial machine files are often structured (our own synthetic stitches, mm):
# objects of one thread joined by travel runs without trims, underlay under the top stitching,
# tie-in and tie-off stitches, jumps without trims, long moves as many short jumps, a thread used twice.

def _run(a, b, step=2.0):
    n = max(1, math.ceil(math.dist(a, b) / step))
    return [tuple(np.add(a, np.subtract(b, a) * i / n)) for i in range(1, n + 1)]


def _tie(p, toward):
    d = np.subtract(toward, p)
    q = tuple(np.add(p, d / np.linalg.norm(d) * .7))
    return [p, q, p, q, p]


def _rows(shape, angle, spacing, stitch):
    """Back-and-forth rows across shape at angle (rising to the right is positive; y down)."""
    from shapely import affinity
    from shapely.geometry import LineString
    turned = affinity.rotate(shape, angle, origin=shape.centroid)
    x0, y0, x1, y1 = turned.bounds
    out = []
    for n, y in enumerate(np.arange(y0 + spacing / 2, y1, spacing)):
        cut = turned.intersection(LineString([(x0 - 1, y), (x1 + 1, y)]))
        cut = max(getattr(cut, 'geoms', [cut]), key=lambda g: g.length)
        a, b = sorted((cut.coords[0][0], cut.coords[-1][0]))
        xs = [*np.arange(a, b, stitch), b]
        out += [(x, y) for x in (xs[::-1] if n % 2 else xs)]
    out = list(affinity.rotate(LineString(out), -angle, origin=shape.centroid).coords)
    short = [out[0]]
    for p in out[1:]:   # row ends joined by short stitches, as along an edge
        short += _run(short[-1], p, 3.5) if math.dist(short[-1], p) > 3.5 else [p]
    return short


def _tatami(shape, angle):
    """Edge run and crossing rows as underlay, then the top rows; tie-in and tie-off."""
    inner = shape.buffer(-.5)
    ring = list(inner.exterior.coords)
    stitches = [ring[0]]
    for a, b in zip(ring, ring[1:]):
        stitches += _run(a, b, 2.5)
    under = _rows(inner, angle + 90, 2.0, 3.0)
    stitches += _run(stitches[-1], under[0], 2.5) + under
    top = _rows(shape, angle, .4, 3.5)
    stitches += _run(stitches[-1], top[0], 2.5) + top
    return _tie(stitches[0], stitches[1]) + stitches + _tie(stitches[-1], stitches[-2])[1:]


def _satin(x, y0, y1, width, step=2.0, edge=False):
    """A column: centre walk down and back (and an edge walk), zigzag underlay, then the top satin."""
    cx = x + width / 2
    stitches = [(cx, y0 + .5)] + _run((cx, y0 + .5), (cx, y1 - .5), step) + _run((cx, y1 - .5), (cx, y0 + .5), step)
    if edge:
        ring = [(x + .4, y0 + .4), (x + .4, y1 - .4), (x + width - .4, y1 - .4), (x + width - .4, y0 + .4), (x + .4, y0 + .4)]
        for a, b in zip(ring, ring[1:]):
            stitches += _run(a, b, step)
    stitches += [(x + .5 if i % 2 else x + width - .5, y) for i, y in enumerate(np.arange(y0 + .5, y1 - .5, 1.0))]
    stitches += [(x if i % 2 else x + width, y) for i, y in enumerate(np.arange(y1, y0, -.4))]
    return _tie(stitches[0], stitches[1])[:-1] + stitches + _tie(stitches[-1], stitches[-2])[1:]


def _commercial(path):
    from shapely.geometry import Polygon, box
    pattern = emb.EmbPattern()
    for colour in (RED, BLUE, RED):
        pattern.add_thread(emb.EmbThread(colour))
    sew = lambda stitches: [pattern.add_stitch_absolute(emb.STITCH, x * 10, y * 10) for x, y in stitches]
    jump = lambda p: pattern.add_stitch_absolute(emb.JUMP, p[0] * 10, p[1] * 10)
    # Red, no trims: a tatami rectangle, a travel run to a satin column, a travel run to a running line.
    fill = _tatami(box(0, 0, 20, 15), 0)
    column = _satin(30, 15, 40, 4)
    line = [(40, 10)] + _run((40, 10), (64, 10), 2.5)
    line += _tie(line[-1], line[-2])[1:]
    jump(fill[0])
    sew(fill + _run(fill[-1], column[0]) + column + _run(column[-1], line[0]) + line)
    pattern.add_stitch_absolute(emb.COLOR_CHANGE, *np.multiply(line[-1], 10))
    # Blue: one long jump to a disc at 45°, then a 50 mm move in 1.5 mm jumps (no trim) to a rectangle at -30°.
    disc = _tatami(Polygon([(70 + 8 * math.cos(t), 8 + 8 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 60, endpoint=False)]), 45)
    jump(disc[0])
    sew(disc)
    turned = _tatami(box(60, 55, 85, 70), -30)
    for p in _run(disc[-1], turned[0], 1.5):
        jump(p)
    sew(turned)
    pattern.add_stitch_absolute(emb.TRIM, *np.multiply(turned[-1], 10))
    pattern.add_stitch_absolute(emb.COLOR_CHANGE, *np.multiply(turned[-1], 10))
    # Red again: a rectangle with upright rows.
    upright = _tatami(box(0, 50, 15, 80), 90)
    jump(upright[0])
    sew(upright)
    pattern.add_stitch_absolute(emb.END, *np.multiply(upright[-1], 10))
    emb.write(pattern, str(path), {'version': 6} if path.suffix == '.pes' else {})
    return path


def _box_of(piece):
    every = np.concatenate([np.asarray(r) for r in piece['rings']])
    return [*every.min(axis=0), *every.max(axis=0)]


@pytest.mark.parametrize('suffix', ['.pes', '.dst'])
def test_files_structured_like_commercial_ones_are_split_into_their_objects(tmp_path, suffix):
    blocks = read(_commercial(tmp_path / ('design' + suffix)))
    # The many short jumps are one move: the two blue objects are separate blocks.
    assert len(blocks) == 4
    found = pieces(blocks)
    assert [p['kind'] for p in found] == ['fill', 'satin', 'line', 'fill', 'fill', 'fill']
    if suffix == '.pes':
        assert [p['colour'] for p in found] == [RED, RED, RED, BLUE, BLUE, RED]
    fill, column, line, disc, turned, upright = found
    # Each outline is its own object only: travel runs and the other objects are left out.
    assert _box_of(fill) == pytest.approx([0, 0, 20, 15], abs=.6)
    assert _box_of(column) == pytest.approx([30, 15, 34, 40], abs=.6)
    assert line['stitch'] == 'running' and line['rings'][0] == [pytest.approx([40, 10], abs=.2), pytest.approx([64, 10], abs=.2)]
    # The top rows' direction, not the underlay's.
    assert [fill['angle'], disc['angle'], turned['angle'], abs(upright['angle'])] == pytest.approx([0, 45, -30, 90], abs=2)


def test_a_satin_with_heavy_underlay_is_still_satin():
    # Centre walk, edge walk and zigzag underlay in short stitches: most needle holes do not turn back,
    # but the top stitching (sewn last, covering it all) does.
    (column,) = pieces([dict(colour=RED, points=_satin(0, 0, 40, 3, step=1.0, edge=True))])
    assert column['kind'] == 'satin' and _box_of(column) == pytest.approx([0, 0, 3, 40], abs=.6)


def test_tie_stitches_do_not_make_a_line_triple_or_add_spurs():
    stitches = [(0, 0)] + _run((0, 0), (30, 0), 2.5)
    stitches = _tie(stitches[0], (0, 1))[:-1] + stitches + _tie(stitches[-1], (30, 1))[1:]
    (line,) = pieces([dict(colour=RED, points=stitches)])
    assert line['stitch'] == 'running' and line['rings'][0] == [pytest.approx([0, 0], abs=.2), pytest.approx([30, 0], abs=.2)]


def test_a_commercial_style_file_opens_and_sews(tmp_path):
    from embroiderly.release_gate import checked_bytes
    from embroiderly.web import create_app
    client = create_app(tmp_path).test_client()
    with open(_commercial(tmp_path / 'design.pes'), 'rb') as handle:
        response = client.post('/upload', data=dict(image=(handle, 'design.pes')), content_type='multipart/form-data')
    assert response.status_code == 302, response.data
    name = response.headers['Location'].rsplit('/', 1)[-1]
    options = json.loads((tmp_path / 'work/decisions' / (name + '.preparation.json')).read_text())
    r = client.post('/artwork/' + name, json=dict(options=options)).get_json()
    shown = sorted(r['report']['piece_layout']['pieces'], key=lambda p: int(p['name'].split()[-1]))
    assert [p['style'] for p in shown] == ['tatami', 'satin', 'line', 'tatami', 'tatami', 'tatami']
    body = client.post('/artwork/' + name, json=dict(options=options, subject_confirmed=True, digitize=True)).get_json()
    assert body.get('playback'), body.get('error')
    assert body['playback']['colors'] == [RED, BLUE, RED]
    assert checked_bytes(tmp_path/'work'/'inkstitch-preview'/Path(body['prepared_name']).stem, 'dst')
