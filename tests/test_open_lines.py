"""Open stitched lines: clicked or freehand, sewn as running or triple stitch."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_piece_editing import AREA, layout, route_setup  # noqa: E402
from embroiderly.piece_layout import change  # noqa: E402


def draw(options, points, shape='line', stitch='running'):
    return change(options, layout(options), dict(ids=[], field='draw', value=dict(
        shape=shape, points=points, colour='#2050c0', stitch=stitch)))


def lines(options):
    return [p for p in layout(options)['pieces'] if p.get('line')]


def test_a_line_is_a_piece_with_its_length_and_no_area():
    options = draw({}, [[0, 0], [30, 0], [30, 40]])
    (line,) = lines(options)
    assert line['line'] == 'running' and line['area_mm2'] == 0 and line['name'] == 'Line 1'
    assert '70.0 mm long' in ' '.join(line['audit']['messages'])
    assert len(line['rings_mm'][0]) == 3   # open: not closed back to the start


def test_lines_move_copy_and_delete_but_cannot_be_cut():
    options = draw({}, [[0, 0], [30, 0]], stitch='triple')
    (line,) = lines(options)
    moved = change(options, layout(options), dict(ids=[line['id']], field='x_mm', value=20))
    assert lines(moved)[0]['x_mm'] == pytest.approx(20)
    copied = change(options, layout(options), dict(ids=[line['id']], field='duplicate', value=[0, 10]))
    assert len(lines(copied)) == 2 and all(p['line'] == 'triple' for p in lines(copied))
    with pytest.raises(ValueError, match='cannot be cut'):
        change(options, layout(options), dict(ids=[line['id']], field='knife', value=[[15, -5], [15, 5]]))
    gone = change(copied, layout(copied), dict(ids=[line['id']], field='delete', value=True))
    assert not lines(gone)


def test_bad_lines_are_refused():
    with pytest.raises(ValueError, match='too short'):
        draw({}, [[0, 0], [1, 0]])
    with pytest.raises(ValueError, match='running or triple'):
        draw({}, [[0, 0], [30, 0]], stitch='zigzag')


@pytest.mark.parametrize('stitch', ['running', 'triple'])
def test_lines_pass_the_release_gate(tmp_path, stitch):
    from embroiderly.release_gate import checked_bytes
    client, options, r = route_setup(tmp_path)
    p = r['report']['piece_layout']['pieces'][0]
    x, y = p['x_mm']+p['width_mm']/2+4, p['y_mm']
    value = dict(shape='freehand_line', points=[[x, y-10], [x+3, y-5], [x+5, y], [x+3, y+5], [x, y+10]],
                 colour='#2050c0', stitch=stitch)
    body = client.post('/artwork/p.png', json=dict(options=options, piece_revision=r['piece_revision'],
                                                    subject_confirmed=True, digitize=True,
                                                    piece_command=dict(ids=[], field='draw', value=value))).get_json()
    assert body.get('playback'), body.get('error')
    assert '#2050c0' in body['playback']['colors']
    assert checked_bytes(tmp_path/'work'/'inkstitch-preview'/Path(body['prepared_name']).stem, 'dst')
