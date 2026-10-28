"""Appliqué: placement run, stop, tack-down, stop, satin cover; the inside stays unstitched."""
import sys
from pathlib import Path

import pyembroidery as emb
import pytest
from shapely.geometry import LineString, Point, box

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


# Partial, shared-stop and join options across pieces (applique_layout.py).
def _picture(tmp_path, draw_on, styles, options=None):
    """A drawn picture through preparation and the engine; styles(rings) -> style per part."""
    import json
    import numpy as np
    from PIL import Image, ImageDraw
    from embroiderly.engine import digitize
    from embroiderly.preparation import prepare
    from embroiderly.region_stitches import regions
    tmp_path.mkdir(parents=True, exist_ok=True)
    image = Image.new('RGBA', (400, 400), (0, 0, 0, 0))
    draw_on(ImageDraw.Draw(image))
    image.save(tmp_path/'art.png')
    prepared_image, _, report = prepare(tmp_path/'art.png', {'height_mm': 60})
    prepared = tmp_path/'prepared.png'; prepared_image.save(prepared)
    array = np.asarray(prepared_image.convert('RGBA'))
    chosen = {key: styles(rings) for key, _, rings in regions(array[..., :3], array[..., 3] > 0)}
    prepared.with_suffix('.prep.json').write_text(json.dumps({'options': {
        'height_mm': 60, 'region_styles': {k: v for k, v in chosen.items() if v}, **(options or {})}, 'report': {}}))
    payload = digitize(prepared, tmp_path/'out', 60)
    stops = [c & emb.COMMAND_MASK for _, _, c in emb.read(str(tmp_path/'out'/'design.pes')).stitches].count(emb.STOP)
    return payload, (tmp_path/'out'/'design.svg').read_text(encoding='utf-8'), stops


def _disc_and_square(draw):
    draw.ellipse((40, 40, 360, 360), fill=(30, 90, 200, 255))
    draw.rectangle((150, 150, 250, 250), fill=(230, 180, 30, 255))


def _cover_points(parts):
    return [Point(p) for run in parts[2][0] for p in run]


def test_bare_edges_get_no_cover_and_covers_tuck_under_their_ends():
    piece, hidden = box(0, 0, 30, 20), box(20, -5, 40, 25)
    covers = _cover_points(_applique(piece, 3.0, hidden))
    right = LineString([(30, 0), (30, 20)])
    assert covers and min(right.distance(p) for p in covers) > 4    # the hidden side has none
    left = LineString([(0, 0), (0, 20)])
    assert min(left.distance(p) for p in covers) < 1.6               # the open sides keep theirs
    # The cover runs on under the part on top for TUCK_MM, past where it hides the edge.
    assert max(p.x for p in covers) > 20.5
    # Placement and tack-down still go all round: the fabric is held everywhere.
    placement = [Point(p) for run in _applique(piece, 3.0, hidden)[0][0] for p in run]
    assert any(right.distance(p) < 1e-6 for p in placement)


def test_short_hidden_stretches_are_covered_anyway():
    covers = _cover_points(_applique(box(0, 0, 30, 20), 3.0, box(29, 9, 31, 11)))
    assert any(LineString([(30, 9), (30, 11)]).distance(p) < 1.6 for p in covers)


def test_joined_pieces_sew_the_shared_edge_once(tmp_path):
    every = lambda rings: 'applique'
    _, plain, _ = _picture(tmp_path/'plain', _disc_and_square, every)
    _, joined, stops = _picture(tmp_path/'joined', _disc_and_square, every, {'applique_join': True})
    assert stops == 4 and 'applique_bare' in joined and 'applique_bare' not in plain
    count = lambda folder: len(emb.read(str(tmp_path/folder/'out'/'design.pes')).stitches)
    assert count('joined') < count('plain')       # the disc's inner edge has no cover now
    assert checked_bytes(tmp_path/'joined'/'out', 'dst')


def test_partial_applique_runs_under_the_part_on_top(tmp_path):
    disc = lambda rings: 'applique' if len(rings) > 1 else None   # the square stays a fill
    _, plain, _ = _picture(tmp_path/'plain', _disc_and_square, disc)
    _, partial, stops = _picture(tmp_path/'partial', _disc_and_square, disc, {'applique_partial': True})
    assert stops == 2 and 'applique_bare' in partial
    # The cutting file's hole (under the square) is smaller: the fabric reaches under it.
    from embroiderly import svg_geometry as sg
    from embroiderly.stitch_fills import fill_shape

    def fabric_mm2(folder):
        cut = (tmp_path/folder/'out'/'applique-cut.svg').read_text(encoding='utf-8')
        d = cut.split(' d="')[1].split('"')[0]
        return fill_shape([(pts, True) for pts, _ in sg.parse_path(d)], 'evenodd').area
    # The square's hole is 15 mm across; 1.5 mm more fabric on each side is about 80 mm² more.
    assert 'applique_bare' not in plain and 50 < fabric_mm2('partial')-fabric_mm2('plain') < 110
    assert checked_bytes(tmp_path/'partial'/'out', 'dst')


def test_pieces_of_one_thread_share_their_stops(tmp_path):
    def two_discs(draw):
        draw.ellipse((30, 120, 190, 280), fill=(30, 90, 200, 255))
        draw.ellipse((210, 120, 370, 280), fill=(30, 90, 200, 255))
    every = lambda rings: 'applique'
    _, _, apart = _picture(tmp_path/'apart', two_discs, every)
    payload, svg, together = _picture(tmp_path/'together', two_discs, every, {'applique_combine': True})
    assert apart == 4 and together == 2
    assert svg.count('fill_method="applique"') == 1 and payload['applique']['pieces'] == 2
    assert checked_bytes(tmp_path/'together'/'out', 'dst')


def test_applique_options_are_on_or_off(tmp_path):
    with pytest.raises(ValueError, match='on or off'):
        _picture(tmp_path, _disc_and_square, lambda rings: 'applique', {'applique_join': 'yes'})
