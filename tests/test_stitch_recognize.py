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
