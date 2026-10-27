"""Hand-look runs: blackwork run, hand stitch and candlewicking borders; Redwork black lines."""
import json
import math
from collections import Counter

import numpy as np
import pytest
from PIL import Image, ImageDraw

from embroiderly.borders import border_plan
from embroiderly.ink_lines import REDWORK, line_settings, redwork_routes
from embroiderly.stitch_paths import blackwork_run, candlewick, hand_stitch

LINE = [(0.0, 0.0), (30.0, 0.0)]
RING = [(10+8*math.cos(i*math.pi/60), 10+8*math.sin(i*math.pi/60)) for i in range(120)]
RING = RING+[RING[0]]


def legs(points):
    return [math.dist(p, q) for p, q in zip(points, points[1:])]


def holes(points):
    return Counter((round(x, 6), round(y, 6)) for x, y in points)


def test_blackwork_run_goes_out_and_back_through_the_same_holes():
    points = blackwork_run(LINE, 2.0)
    assert points[0] == points[-1] == LINE[0]
    assert sum(legs(points)) == pytest.approx(60.0)
    out = points[:len(points)//2+1]
    assert points[len(points)//2:] == out[::-1]
    assert .45 <= min(legs(points)) and max(legs(points)) <= 2.0+1e-6


def test_hand_stitch_is_bold_dashes_joined_by_fine_links():
    points = hand_stitch(LINE, 3.0, 1.0)
    assert points[0] == LINE[0] and points[-1] == pytest.approx(LINE[1])
    assert all(y == 0 for _, y in points)
    steps = legs(points)
    links = [s for s in steps if s == pytest.approx(1.0)]
    dashes = [s for s in steps if s > 1.5]
    assert len(links) >= 5
    # Each dash is sewn three times, and their lengths vary a little like hand sewing.
    assert len(dashes) >= 3*len(links)
    assert len({round(s, 2) for s in dashes}) >= 3 and max(dashes) <= 3.6+1e-6
    assert hand_stitch(LINE, 3.0, 1.0) == points


def test_candlewicking_puts_evenly_spread_raised_knots_on_the_line():
    points = candlewick(LINE, 2.0, 1.6, 3.0)
    # Knot centres are holes the needle returns to many times.
    centres = sorted(x for (x, y), n in holes(points).items() if n >= 10)
    assert len(centres) == 10
    gaps = [b-a for a, b in zip(centres, centres[1:])]
    assert max(gaps)-min(gaps) < 1e-6
    assert max(abs(y) for _, y in points) == pytest.approx(.8)
    assert .45 <= min(legs(points)) and max(legs(points)) <= 2.0+1e-6


@pytest.mark.parametrize('fn', [blackwork_run, hand_stitch, candlewick])
def test_hand_runs_on_a_ring_keep_safe_stitches(fn):
    points = fn(RING)
    assert min(legs(points)) >= .45 and max(legs(points)) <= 3.6+1e-6


@pytest.mark.parametrize('style', ['blackwork', 'handstitch', 'candlewick'])
def test_hand_run_borders_generate_and_pass_the_release_gate(tmp_path, style):
    from test_stitch_types_engine import design
    from embroiderly.release_gate import checked_bytes
    mask = np.zeros((200, 200), bool); mask[40:160, 40:160] = True
    assert border_plan(mask, 50, dict(border_style=style, border_width=2))['style'] == style
    _, svg = design(tmp_path, {'border_style': style, 'border_width': 2, 'border_colour': '#202020'})
    assert f'outline_style="{style}"' in svg
    assert checked_bytes(tmp_path/'out', 'dst')


def test_redwork_sews_every_line_twice_in_one_closed_route_per_drawing():
    lines = [[(0, 0), (5, 0)], [(5, 0), (10, 0)], [(5, 1), (5, 6)], [(20, 20), (25, 25)]]
    routes = redwork_routes(lines)
    assert len(routes) == 2
    for route in routes:
        assert route[0] == route[-1]
    # 15 px of the T, twice, plus a one-pixel hop each way where two line ends meet.
    assert sum(legs(routes[0])) == pytest.approx(2*15+2)
    assert sum(legs(routes[1])) == pytest.approx(2*math.dist((20, 20), (25, 25)))


def test_redwork_is_a_listed_line_weight():
    assert line_settings({'ink_bean_repeats': REDWORK}) == (2.0, REDWORK)


def test_redwork_black_lines_digitize_without_cuts_and_pass_the_release_gate(tmp_path):
    from embroiderly.engine import digitize
    from embroiderly.preparation import prepare
    from embroiderly.release_gate import checked_bytes
    source = tmp_path/'ink.png'
    image = Image.new('RGB', (300, 300), (255, 255, 255))
    d = ImageDraw.Draw(image)
    d.line((40, 60, 260, 60), fill=(0, 0, 0), width=3)
    d.line((150, 60, 150, 260), fill=(0, 0, 0), width=3)
    d.line((60, 120, 120, 200), fill=(0, 0, 0), width=3)
    image.save(source)
    options = {'ink_only': True, 'ink_bean_repeats': REDWORK, 'height_mm': 60}
    prepared_image, _, report = prepare(source, options)
    assert not report['generation_blockers']
    prepared = tmp_path/'prepared.png'; prepared_image.save(prepared)
    prepared.with_suffix('.prep.json').write_text(json.dumps({'options': options, 'report': {}}))
    payload = digitize(prepared, tmp_path/'out', 60)
    svg = (tmp_path/'out'/'design.svg').read_text(encoding='utf-8')
    # The T is one route; the separate stroke is the other.
    assert svg.count('<path') == 2
    assert payload['trim_count'] <= 2 and payload['stitch_count'] > 50
    assert checked_bytes(tmp_path/'out', 'dst')
