"""Appliqué: placement run, stop, tack-down, stop, satin cover; the inside stays unstitched."""
import sys
from pathlib import Path

import pyembroidery as emb
import pytest
from shapely.geometry import Point, box

sys.path.insert(0, str(Path(__file__).parent))
from test_stitch_types_engine import design  # noqa: E402

from embroiderly.release_gate import checked_bytes
from embroiderly.stitch_engine import _applique


def test_three_parts_with_stops_before_tack_down_and_cover():
    parts = _applique(box(0, 0, 30, 20), 3.0)
    assert [stop for _, stop in parts] == [False, True, True]
    placement, tack, cover = (runs for runs, _ in parts)
    edge = box(0, 0, 30, 20).exterior
    assert all(edge.distance(Point(p)) < 1e-6 for run in placement for p in run)
    # Tack-down sits inside the edge, under where the cover will be.
    assert all(box(0, 0, 30, 20).contains(Point(p)) and edge.distance(Point(p)) < 1.5 for run in tack for p in run)
    # The cover straddles the cut edge, half inside and half outside.
    points = [Point(p) for run in cover for p in run]
    assert max(edge.distance(p) for p in points) == pytest.approx(1.5, abs=.8)
    assert any(not box(0, 0, 30, 20).contains(p) for p in points)
    # Nothing is sewn in the middle of the piece: the fabric shows there.
    middle = box(5, 5, 25, 15)
    assert not any(middle.contains(Point(p)) for runs, _ in parts for run in runs for p in run)


def test_pieces_too_small_for_the_cover_are_refused():
    with pytest.raises(ValueError, match='at least 6 mm'):
        _applique(box(0, 0, 5, 30), 3.0)


def test_applique_design_stops_twice_per_piece_and_passes_the_release_gate(tmp_path):
    _, svg = design(tmp_path, {'region_styles': 'applique'})
    assert 'fill_method="applique"' in svg
    pes = emb.read(str(tmp_path/'out'/'design.pes'))
    commands = [c & emb.COMMAND_MASK for _, _, c in pes.stitches]
    assert commands.count(emb.STOP) == 4          # two pieces, two stops each
    assert checked_bytes(tmp_path/'out', 'dst')


def test_cutting_file_has_each_piece_at_actual_size(tmp_path):
    payload, _ = design(tmp_path, {'region_styles': 'applique'})
    cut = (tmp_path/'out'/'applique-cut.svg').read_text(encoding='utf-8')
    assert payload['applique'] == {'pieces': 2, 'cut_file': 'applique-cut.svg'}
    assert cut.count('<path') == 2 and 'mm"' in cut
    # The disc is 320 of the canvas's 400 px at 60 mm: 48 mm, plus a 2 mm margin each side.
    height = float(cut.split('height="')[1].split('mm')[0])
    assert abs(height-52) < 1


def test_designs_without_applique_have_no_cutting_file(tmp_path):
    payload, _ = design(tmp_path, {'region_styles': 'step'})
    assert 'applique' not in payload and not (tmp_path/'out'/'applique-cut.svg').exists()
