"""Basting sewn first in its own thread; buttonholes sewn last; both pass the release gate."""
import math
import sys
from pathlib import Path

import pyembroidery as emb
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_stitch_types_engine import design  # noqa: E402

from embroiderly.basting_buttonholes import BASTE_COLOUR, buttonhole_points, choices
from embroiderly.release_gate import checked_bytes

HOLE = dict(x=0, y=0, length_mm=15, width_mm=4, angle=0, colour='#202020')


def _blocks(folder):
    """[(thread colour, [sewn points in mm])] per thread, as written to the PES file."""
    pattern = emb.read(str(folder/'design.pes'))
    colours = [t.hex_color() for t in pattern.threadlist]
    blocks, index = [[colours[0], []]], 0
    for x, y, command in pattern.stitches:
        command &= emb.COMMAND_MASK
        if command in (emb.COLOR_CHANGE, emb.STOP):
            index += 1
            blocks.append([colours[min(index, len(colours)-1)], []])
        elif command == emb.STITCH:
            blocks[-1][1].append((x/10, y/10))
    return blocks


def test_basting_around_the_design_is_sewn_first_in_its_own_thread(tmp_path):
    payload, _ = design(tmp_path, {'basting': 'design'})
    assert payload['colors'][0] == BASTE_COLOUR
    blocks = _blocks(tmp_path/'out')
    baste, rest = blocks[0][1], [p for _, points in blocks[1:] for p in points]
    # A box 5 mm outside the design's stitches, in long stitches.
    assert min(x for x, _ in baste) == pytest.approx(min(x for x, _ in rest)-5, abs=.2)
    assert max(y for _, y in baste) == pytest.approx(max(y for _, y in rest)+5, abs=.2)
    legs = [math.dist(a, b) for a, b in zip(baste, baste[1:]) if math.dist(a, b) > 0]
    assert max(legs) <= 5.01 and sum(legs)/len(legs) > 4
    assert checked_bytes(tmp_path/'out', 'dst')


def test_basting_around_the_hoop_runs_just_inside_its_field(tmp_path):
    design(tmp_path, {'basting': 'hoop', 'piece_hoop_mm': [100, 120]})
    baste = _blocks(tmp_path/'out')[0][1]
    assert (max(x for x, _ in baste), max(y for _, y in baste)) == pytest.approx((47, 57), abs=.1)
    assert checked_bytes(tmp_path/'out', 'dst')


def test_basting_around_the_hoop_needs_a_hoop():
    with pytest.raises(ValueError, match='Choose a hoop first'):
        choices({'basting': 'hoop'})


def test_buttonholes_are_sewn_last_and_pass_the_release_gate(tmp_path):
    # One over the design, one out on bare fabric past its edge: the checked canvas grows.
    payload, _ = design(tmp_path, {'buttonholes': [HOLE, dict(HOLE, x=40, angle=90, colour='#AA0000')]})
    assert payload['colors'][-2:] == ['#202020', '#aa0000']
    far = _blocks(tmp_path/'out')[-1][1]
    assert max(y for _, y in far)-min(y for _, y in far) == pytest.approx(15, abs=.3)
    assert max(x for x, _ in far)-min(x for x, _ in far) == pytest.approx(4, abs=.3)
    assert checked_bytes(tmp_path/'out', 'dst')


def test_a_buttonhole_has_two_legs_a_slit_and_bar_tacks():
    points = buttonhole_points(HOLE, (0, 0))
    across = [y/10 for _, y in points]
    assert max(across) == pytest.approx(2) and min(across) == pytest.approx(-2)
    # Inside the bar tacks nothing is sewn on the slit, only along the run under the legs.
    middle = [(x/10, y/10) for x, y in points if abs(x/10) < 6]
    assert not any(abs(y) < .29 for _, y in middle)
    # The bar tacks cross the slit at both ends.
    crossing = [(a[0]+b[0])/20 for a, b in zip(points, points[1:]) if a[1]*b[1] < 0 and abs(a[1]-b[1]) > 35]
    assert any(x > 6.3 for x in crossing) and any(x < -6.3 for x in crossing)
    lengths = [math.dist(a, b)/10 for a, b in zip(points, points[1:])]
    assert max(lengths) <= 7 and min(lengths) >= .3


@pytest.mark.parametrize('bad, message', [
    ({'basting': 'frame'}, 'listed basting'),
    ({'buttonholes': [dict(HOLE, length_mm=60)]}, '8–40 mm'),
    ({'buttonholes': [dict(HOLE, colour='red')]}, 'thread colour'),
])
def test_invalid_choices_are_refused(bad, message):
    with pytest.raises(ValueError, match=message):
        choices(bad)
