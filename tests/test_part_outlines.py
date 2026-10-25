"""Outlines per part: running, triple or satin around one chosen part, on its edge or offset."""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_piece_editing import AREA, apply, layout, piece, route_setup  # noqa: E402
from embroiderly.part_outlines import add, choices  # noqa: E402

SPEC = dict(stitch='triple', offset_mm=1.5, width_mm=2, colour='#202020')


def test_outline_choice_is_stored_shown_and_removed():
    options = apply({}, 'outline', SPEC)
    assert options['area_outlines'] == {AREA['id']: SPEC} and piece(options)['outline'] == SPEC
    assert 'area_outlines' in options and not apply(options, 'outline', None)['area_outlines']


@pytest.mark.parametrize('bad', [dict(SPEC, stitch='wavy'), dict(SPEC, offset_mm=9), dict(SPEC, width_mm=.5),
                                 dict(SPEC, colour='black'), {'stitch': 'running'}])
def test_bad_outlines_are_refused(bad):
    with pytest.raises(ValueError):
        apply({}, 'outline', bad)


def test_offset_moves_the_outline_outward_and_marks_its_band():
    square = [np.array([[0, 0], [100, 0], [100, 100], [0, 100]], float)+50]
    for offset in (0, 2):
        document, mask = ET.Element('svg'), np.zeros((300, 300), bool)
        assert add(document, square, dict(SPEC, stitch='running', offset_mm=offset), .2, mask, 0) == 1
        xs = [float(v.split(',')[0]) for v in document[0].get('d').replace('M ', '').split(' L ')]
        assert min(xs) == pytest.approx(50-offset/.2, abs=.6)
        assert mask[150, int(round(50-offset/.2))]   # the band along the outline is sewn area


def test_satin_outline_has_two_halves():
    document, mask = ET.Element('svg'), np.zeros((300, 300), np.uint8)
    square = [np.array([[0, 0], [100, 0], [100, 100], [0, 100]], float)+50]
    assert add(document, square, dict(SPEC, stitch='satin', width_mm=2.5), .2, mask, 0) == 2
    assert all(n.get('{http://inkstitch.org/namespace}satin_column') == 'true' for n in document)


@pytest.mark.parametrize('stitch', ['running', 'triple', 'satin'])
def test_part_outline_passes_the_release_gate(tmp_path, stitch):
    from embroiderly.release_gate import checked_bytes
    client, options, r = route_setup(tmp_path)
    p = r['report']['piece_layout']['pieces'][0]
    body = client.post('/artwork/p.png', json=dict(
        options=options, piece_revision=r['piece_revision'], subject_confirmed=True, digitize=True,
        piece_command=dict(ids=[p['id']], field='outline', value=dict(SPEC, stitch=stitch, colour='#c03020')))).get_json()
    assert body.get('playback'), body.get('error')
    assert body['playback']['colors'][-1] == '#c03020'   # sewn last, on top
    assert checked_bytes(tmp_path/'work'/'inkstitch-preview'/Path(body['prepared_name']).stem, 'dst')


def test_outline_on_an_edited_piece_passes_the_release_gate(tmp_path):
    from embroiderly.release_gate import checked_bytes
    client, options, r = route_setup(tmp_path)
    p = r['report']['piece_layout']['pieces'][0]
    for field, value in (('rotate_by', 15), ('outline', dict(SPEC, stitch='satin', offset_mm=2))):
        body = client.post('/artwork/p.png', json=dict(
            options=options, piece_revision=r['piece_revision'], subject_confirmed=True, digitize=True,
            piece_command=dict(ids=[p['id']], field=field, value=value))).get_json()
        assert body.get('playback'), body.get('error')
        options, r = body['options'], body
    assert checked_bytes(tmp_path/'work'/'inkstitch-preview'/Path(body['prepared_name']).stem, 'dst')
