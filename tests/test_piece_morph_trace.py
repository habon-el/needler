"""Morph a piece (pinch, punch, twirl, wave); auto trace pieces into clean outlines; magic wand."""
import cv2
import numpy as np
import pytest
from shapely.geometry import Polygon

from embroiderly.piece_layout import change, inventory
from test_piece_weld import BLUE, RED, apply, area, box, checked, command, disc, layout, setup


def square_with_hole():
    return dict(id='e'*20, colour=BLUE, style='tatami',
                rings=[[[0, 0], [60, 0], [60, 60], [0, 60]], [[20, 20], [40, 20], [40, 40], [20, 40]]])


def morph(areas, kind, strength=50, options=None, ids=None):
    options = options or {}
    done = apply(areas, options, 'morph', dict(kind=kind, strength=strength), ids or [areas[0]['id']])
    return done, layout(areas, done)['pieces']


def test_pinch_draws_the_sides_in_and_punch_bulges_them_out():
    areas = [box('a', 0, 0, 40, 40)]
    before = layout(areas, {})['pieces'][0]
    _, (pinched,) = morph(areas, 'pinch')
    _, (punched,) = morph(areas, 'punch')
    assert area(pinched) < area(before)*.85 < area(before) < area(punched)
    # Pinch keeps the corners where they were; the sides' middles move in.
    assert pinched['width_mm'] == pytest.approx(before['width_mm'], abs=.2)
    assert punched['width_mm'] > before['width_mm']
    stronger = morph(areas, 'pinch', 100)[1][0]
    assert area(stronger) < area(pinched)


def test_twirl_and_wave_bend_the_outline_and_keep_style_and_holes():
    areas = [square_with_hole()]
    styled = apply(areas, {}, 'style', 'step', ['e'*20])
    before = layout(areas, styled)['pieces'][0]
    done, (twirled,) = morph(areas, 'twirl', 60, styled)
    assert twirled['style'] == 'step' and len(twirled['rings_mm']) == 2
    assert Polygon(twirled['rings_mm'][0]).hausdorff_distance(Polygon(before['rings_mm'][0])) > 1
    assert done['piece_edits']['e'*20]['cut']
    _, (waved,) = morph(areas, 'wave', 100, styled)
    # Two waves across: the top and bottom edges rise and fall, so it gets taller; the area stays.
    assert waved['height_mm'] > before['height_mm']+2 and area(waved) == pytest.approx(area(before), rel=.03)
    assert len(waved['rings_mm']) == 2


def test_several_pieces_morph_together_around_one_centre():
    areas = [box('a', 0, 0, 20, 40), box('b', 20, 0, 40, 40, RED)]
    done, pieces = morph(areas, 'pinch', 80, ids=['a'*20, 'b'*20])
    left, right = sorted(pieces, key=lambda p: p['x_mm'])
    # Mirror images of each other about the shared centre, both pulled in along their shared edge.
    assert area(left) == pytest.approx(area(right), rel=.01)
    assert left['colour'] == BLUE and right['colour'] == RED


def test_morph_refuses_bad_choices_lines_and_locked_pieces():
    areas = [box('a', 0, 0, 40, 40)]
    with pytest.raises(ValueError, match='Pinch, Punch, Twirl or Wave'):
        apply(areas, {}, 'morph', dict(kind='spin', strength=50), ['a'*20])
    with pytest.raises(ValueError, match='strength'):
        apply(areas, {}, 'morph', dict(kind='pinch', strength=150), ['a'*20])
    locked = apply(areas, {}, 'locked', True, ['a'*20])
    with pytest.raises(ValueError, match='locked'):
        apply(areas, locked, 'morph', dict(kind='pinch', strength=50), ['a'*20])
    # A circle looks the same twirled: nothing to do.
    round_piece = dict(id='c'*20, colour=BLUE, style='tatami', rings=[
        [[40+30*np.cos(t), 40+30*np.sin(t)] for t in np.linspace(0, 2*np.pi, 90, endpoint=False)]])
    with pytest.raises(ValueError, match='too small or too round'):
        apply([round_piece], {}, 'morph', dict(kind='twirl', strength=50), ['c'*20])
    line = apply(areas, {}, 'draw', dict(shape='line', points=[[0, 0], [10, 0]], colour=BLUE), [])
    key = next(k for k, v in line['piece_edits'].items() if v.get('line'))
    with pytest.raises(ValueError, match='cannot be morphed'):
        apply(areas, line, 'morph', dict(kind='wave', strength=50), [key])


def turns(p, limit=30):
    ring = np.asarray(p['rings_mm'][0])
    a, b = ring-np.roll(ring, 1, axis=0), np.roll(ring, -1, axis=0)-ring
    turn = np.degrees(np.abs(np.arctan2(a[:, 0]*b[:, 1]-a[:, 1]*b[:, 0], (a*b).sum(axis=1))))
    return int((turn > limit).sum())


def test_auto_trace_turns_pixel_steps_into_curves_and_keeps_the_area():
    areas = [disc()]
    before = layout(areas, {})['pieces'][0]
    traced = layout(areas, apply(areas, {}, 'auto_trace', None, ['d'*20]))['pieces'][0]
    assert area(traced) == pytest.approx(area(before), rel=.01)
    assert turns(before) > 20 and turns(traced) == 0 and traced['nodes'] < before['nodes']


def test_auto_trace_keeps_corners_and_closes_speck_holes():
    # A pixel-traced square (0.5 mm per px) with a one-pixel speck hole and a real hole.
    mask = np.zeros((100, 100), np.uint8)
    mask[10:70, 10:70] = 1
    mask[30, 30] = 0
    mask[45:60, 45:60] = 0
    contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    outer = next(i for i in range(len(contours)) if hierarchy[0, i, 3] == -1)
    rings = [contours[outer][:, 0, :].tolist()]+[c[:, 0, :].tolist() for i, c in enumerate(contours) if i != outer]
    areas = [dict(id='5'*20, colour=BLUE, style='tatami', rings=rings)]
    before = layout(areas, {})['pieces'][0]
    assert len(before['rings_mm']) == 3
    traced = layout(areas, apply(areas, {}, 'auto_trace', None, ['5'*20]))['pieces'][0]
    assert len(traced['rings_mm']) == 2   # the speck is closed, the real hole stays
    assert traced['width_mm'] == pytest.approx(before['width_mm'], abs=.3)
    # The four outer corners stay sharp.
    ring = np.asarray(traced['rings_mm'][0])
    for corner in np.asarray(before['rings_mm'][0])[[0]]:
        assert np.linalg.norm(ring-corner, axis=1).min() < .4
    assert turns(traced, 60) == 4


def test_auto_trace_refuses_clean_pieces_and_lines():
    areas = [box('a', 0, 0, 40, 20)]
    with pytest.raises(ValueError, match='already clean'):
        apply(areas, {}, 'auto_trace', None, ['a'*20])
    with pytest.raises(ValueError, match='Invalid'):
        apply([disc()], {}, 'auto_trace', 'lots', ['d'*20])


def test_auto_trace_of_a_whole_thread_traces_each_piece():
    other = disc()
    other['id'] = 'f'*20
    other['rings'] = [[[x+10, y] for x, y in other['rings'][0]]]
    areas = [disc(), other, box('a', 0, 0, 40, 20, RED)]
    done = apply(areas, {}, 'auto_trace', None, ['d'*20, 'f'*20])
    assert done['piece_edits']['d'*20]['cut'] and done['piece_edits']['f'*20]['cut']
    assert 'a'*20 not in done['piece_edits']


SCALE = .25


def artwork():
    """A noisy red square on a blue square, transparent around them; a darker red spot in the red."""
    rng = np.random.default_rng(1)
    rgba = np.zeros((200, 200, 4), np.uint8)
    rgba[20:180, 20:180] = [40, 70, 200, 255]
    red = np.clip(np.array([200, 40, 50])+rng.integers(-12, 13, (80, 80, 3)), 0, 255)
    rgba[60:140, 60:140, :3] = red
    rgba[90:100, 90:100, :3] = [150, 30, 40]
    return rgba


def wand(rgba, point_px, tolerance=15, options=None, threads=True):
    options = options or {}
    areas = [box('a', 20, 20, 180, 180, '#2846c8'), box('b', 60, 60, 140, 140, '#c82832')] if threads else []
    report = inventory({'areas': areas}, options, 200, 200, SCALE)
    point = [point_px[0]*SCALE-report['origin_mm'][0], point_px[1]*SCALE-report['origin_mm'][1]]
    return change(options, report, dict(ids=[], field='magic_wand', value=dict(point=point, tolerance=tolerance)),
                  image=rgba), areas


def wand_piece(options, areas):
    return next(p for p in inventory({'areas': areas}, options, 200, 200, SCALE)['pieces'] if p['name'].startswith('Wand'))


def test_magic_wand_selects_the_similar_colour_around_the_click():
    rgba = artwork()
    options, areas = wand(rgba, (70, 70))
    piece = wand_piece(options, areas)
    assert piece['colour'] == '#c82832' and piece['name'] == 'Wand 1'
    # The red square (80 px, 20 mm) less the dark spot (2.5 mm), which stays a hole.
    assert piece['width_mm'] == pytest.approx(20, abs=.5)
    assert piece['area_mm2'] == pytest.approx(400-6.25, rel=.03) and len(piece['rings']) == 2
    # A high tolerance takes the darker spot in too; the blue around is still left out.
    piece = wand_piece(*wand(rgba, (70, 70), 60))
    assert len(piece['rings']) == 1 and piece['width_mm'] == pytest.approx(20, abs=.5)
    # Clicking the blue selects the frame around the red.
    piece = wand_piece(*wand(rgba, (30, 30)))
    assert piece['colour'] == '#2846c8' and len(piece['rings']) == 2


def test_magic_wand_uses_the_regions_own_colour_without_threads_and_refuses_bad_clicks():
    rgba = artwork()
    options, areas = wand(rgba, (70, 70), threads=False)
    (piece,) = inventory({'areas': []}, options, 200, 200, SCALE)['pieces']
    r, g, b = (int(piece['colour'][i:i+2], 16) for i in (1, 3, 5))
    assert abs(r-200) < 8 and abs(g-40) < 8 and abs(b-50) < 8
    with pytest.raises(ValueError, match='Click on the artwork'):
        wand(rgba, (5, 5))
    with pytest.raises(ValueError, match='Tolerance'):
        wand(rgba, (70, 70), 0)
    full = np.full((200, 200, 4), 255, np.uint8)
    with pytest.raises(ValueError, match='nearly the whole picture'):
        wand(full, (70, 70))


def test_morph_route_passes_the_release_gate(tmp_path):
    def draw(rgba):
        rgba[100:260, 100:260] = [200, 30, 60, 255]
    client, options, body = setup(tmp_path, draw)
    before = body['report']['piece_layout']['pieces'][0]
    done = command(client, options, body, [before['id']], 'morph', dict(kind='pinch', strength=50))
    (after,) = done['report']['piece_layout']['pieces']
    assert after['area_mm2'] < before['area_mm2']*.9
    checked(tmp_path, client, done)


def test_magic_wand_route_reads_the_artwork(tmp_path):
    def draw(rgba):
        rgba[100:300, 100:300] = [40, 70, 200, 255]
        rgba[150:250, 150:250] = [200, 30, 60, 255]
        rgba[150:250, 150:200] = [235, 75, 90, 255]   # a shade preparation may merge with the red
    client, options, body = setup(tmp_path, draw)
    report = body['report']['piece_layout']
    point = [160*report['scale']-report['origin_mm'][0], 160*report['scale']-report['origin_mm'][1]]
    done = command(client, options, body, [], 'magic_wand', dict(point=point, tolerance=8))
    piece = next(p for p in done['report']['piece_layout']['pieces'] if p['name'] == 'Wand 1')
    # Only the left half: the other red differs by more than the tolerance.
    assert piece['width_mm'] == pytest.approx(50*report['scale'], abs=.6)
