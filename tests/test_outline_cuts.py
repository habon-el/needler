"""Fewer cuts between outlines: outline pieces of one thread are sewn nearest first and
joined by travel along their own lines instead of a cut."""
import json
import math

import numpy as np
import pytest
from PIL import Image, ImageDraw

from embroiderly.engine import digitize
from embroiderly.part_outlines import in_order
from embroiderly.preparation import prepare
from embroiderly.release_gate import checked_bytes
from embroiderly.stitch_engine import generate

INK = 'http://inkstitch.org/namespace'


def rings_svg(rings, branching=True):
    paths = ''.join(
        f'<path id="r{k}" d="M {" L ".join(f"{x},{y}" for x, y in ring+ring[:1])}" '
        f'style="fill:none;stroke:#101010" inkstitch:stroke_method="running_stitch" inkstitch:trim_after="true"/>'
        for k, ring in enumerate(rings))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkstitch="{INK}" width="100mm" height="100mm" '
            f'viewBox="0 0 100 100"><metadata><inkstitch:branching>{str(branching).lower()}</inkstitch:branching>'
            f'<inkstitch:collapse_len_mm>0</inkstitch:collapse_len_mm></metadata>{paths}</svg>')


def thread_trims(plan):
    """Trims in each thread (the last one before a change counts for the thread it ends)."""
    counts, k = [0]*len(plan['threadlist']), 0
    for _, _, command in plan['stitches']:
        if command == 'COLOR_CHANGE':
            k += 1
        elif command == 'TRIM':
            counts[k] += 1
    return counts


# Two squares sharing an edge, a third below the second (sharing its lower edge), one far away.
SQUARES = [[(10, 10), (30, 10), (30, 30), (10, 30)], [(30, 10), (50, 10), (50, 30), (30, 30)],
           [(30, 30), (50, 30), (50, 50), (30, 50)], [(10, 70), (25, 70), (25, 85), (10, 85)]]


def test_touching_outline_rings_travel_along_their_lines_instead_of_cutting():
    before = generate(rings_svg(SQUARES, branching=False))
    after = generate(rings_svg(SQUARES))
    assert thread_trims(before) == [4]
    assert thread_trims(after) == [2]          # one cut to the far square, one at the end
    # Every travel stitch lies on a sewn line: no stitch crosses empty fabric.
    from shapely.geometry import LineString, Point
    sewn = LineString(SQUARES[0]+SQUARES[0][:1]).union(LineString(SQUARES[1]+SQUARES[1][:1])) \
        .union(LineString(SQUARES[2]+SQUARES[2][:1])).union(LineString(SQUARES[3]+SQUARES[3][:1]))
    xs, ys = [x for r in SQUARES for x, _ in r], [y for r in SQUARES for _, y in r]
    origin = ((min(xs)+max(xs))/2, (min(ys)+max(ys))/2)   # plan coordinates start at the centre
    stitches = [(x/10+origin[0], y/10+origin[1]) for x, y, c in after['stitches'] if c == 'STITCH']
    assert max(sewn.distance(Point(p)) for p in stitches) < .4
    for (x0, y0, c0), (x1, y1, c1) in zip(after['stitches'], after['stitches'][1:]):
        if c0 == c1 == 'STITCH':
            mid = Point((x0+x1)/20+origin[0], (y0+y1)/20+origin[1])
            assert sewn.distance(mid) < .4


def test_far_apart_rings_still_cut():
    far = [[(10, 10), (20, 10), (20, 20), (10, 20)], [(60, 60), (70, 60), (70, 70), (60, 70)]]
    assert thread_trims(generate(rings_svg(far))) == [2]


def test_outlines_are_grouped_by_thread_and_sewn_nearest_first():
    square = lambda x, y: [np.array([[x, y], [x+10, y], [x+10, y+10], [x, y+10]], float)]
    spec = lambda colour: dict(stitch='running', offset_mm=0, width_mm=2, colour=colour)
    pending = [(square(0, 0), spec('#111111')), (square(100, 0), spec('#222222')),
               (square(200, 0), spec('#111111')), (square(10, 0), spec('#111111'))]
    ordered = in_order(pending)
    assert [s['colour'] for _, s in ordered] == ['#111111']*3+['#222222']
    assert [r[0][0, 0] for r, _ in ordered[:3]] == [0, 10, 200]


def artwork(path):
    image = Image.new('RGBA', (500, 400), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)
    d.rectangle((40, 40, 200, 160), fill=(30, 90, 200, 255))
    d.rectangle((120, 100, 260, 220), fill=(200, 60, 40, 255))      # lies over the blue one
    d.ellipse((300, 50, 440, 190), fill=(40, 160, 70, 255))
    d.ellipse((340, 90, 400, 150), fill=(240, 220, 40, 255))        # inside the green one
    d.polygon([(220, 360), (300, 250), (380, 360)], fill=(30, 90, 200, 255))
    image.save(path)


def make(tmp_path, name, options):
    out = tmp_path/name
    out.mkdir()
    artwork(out/'art.png')
    image, _, _ = prepare(out/'art.png', {'height_mm': 80})
    prepared = out/'prepared.png'
    image.save(prepared)
    prepared.with_suffix('.prep.json').write_text(json.dumps({'options': {'height_mm': 80, **options}, 'report': {}}))
    payload = digitize(prepared, out/'o', 80)
    assert checked_bytes(out/'o', 'dst')
    plan = generate((out/'o'/'design.svg').read_bytes())
    trims = dict(zip([t['color'] for t in plan['threadlist']], thread_trims(plan)))
    return payload, trims, (out/'o'/'design.svg').read_text(encoding='utf-8')


def test_round_and_slanted_colour_outlines_are_not_broken_into_pieces(tmp_path):
    # Outline networks: blue and red together, green, yellow, triangle. Before, every
    # slanted stretch of a round or slanted edge broke the line (12 outline cuts here).
    _, trims, svg = make(tmp_path, 'one', {'outlines': True, 'outline_colour': '#101010'})
    assert svg.count('id="detail') == 4
    assert trims['#101010'] == 4


def test_part_outlines_of_one_thread_cut_less_and_pass_the_release_gate(tmp_path):
    payload, _, _ = make(tmp_path, 'plain', {})
    spec = dict(stitch='triple', offset_mm=0, width_mm=2, colour='#101010')
    outlines = {'area_outlines': {key: spec for key in payload['sew_parts']}}
    _, cut, _ = make(tmp_path, 'cut', {**outlines, 'branching': False})
    _, joined, _ = make(tmp_path, 'joined', outlines)
    # Rings: blue, red, green, green's hole, yellow, triangle. Blue touches red and the
    # hole touches yellow, so two of the six cuts go.
    assert cut['#101010'] == 6 and joined['#101010'] == 4
