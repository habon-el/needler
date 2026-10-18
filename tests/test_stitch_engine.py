"""Needler's own stitch engine: fills, satin, running stitch, locks and routing."""
import json
import math
import pyembroidery as emb
import pytest
from PIL import Image, ImageDraw
from embroiderly import stitch_engine
from embroiderly.engine import digitize
from embroiderly.release_gate import checked_bytes

NS = 'xmlns:i="http://inkstitch.org/namespace"'


def document(body, size=50):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" {NS} xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{size}mm" height="{size}mm" viewBox="0 0 {size} {size}"><metadata><i:inkstitch_svg_version>3'
            f'</i:inkstitch_svg_version></metadata>{body}<use xlink:href="#inkstitch_origin" x="0" y="0"/></svg>')


def sewn(plan):
    points, previous = [], None
    for x, y, command in plan['stitches']:
        if command == 'STITCH':
            if previous is not None:
                points.append((previous, (x/10, y/10)))
            previous = (x/10, y/10)
        elif command != 'JUMP':
            previous = None
    return points


def test_tatami_fills_inside_and_keeps_stitch_lengths():
    plan = stitch_engine.generate(document('<path d="M10,10 L40,10 L40,30 L10,30 Z" style="fill:#ff0000" '
                                           'i:row_spacing_mm="0.4" i:min_stitch_length_mm="0.45"/>'))
    segments = sewn(plan)
    assert plan['threadlist'][0]['color'] == '#ff0000'
    assert all(9.9 <= x <= 40.1 and 9.9 <= y <= 30.1 for a, b in segments for x, y in (a, b))
    lengths = [math.dist(a, b) for a, b in segments if math.dist(a, b) > 1e-9]
    assert min(lengths) >= .44 and max(lengths) <= 7
    rows = {round(b[1], 2) for a, b in segments if abs(a[1]-b[1]) < 1e-6}
    assert len(rows) > 40   # 20 mm high at 0.4 mm rows, plus underlay rows


def test_satin_column_zigzags_between_rails():
    plan = stitch_engine.generate(document('<path d="M10,10 L40,10 M10,13 L40,13" style="fill:none;stroke:#000000" '
                                           'i:satin_column="true" i:zigzag_spacing_mm="0.4"/>'))
    segments = sewn(plan)
    across = [s for s in segments if abs(s[0][1]-s[1][1]) > 2.5]
    assert len(across) > 100
    assert all(9.9 <= y <= 13.1 for a, b in segments for _, y in (a, b))


def test_running_stitch_bean_and_locks():
    plain = stitch_engine.generate(document('<path d="M5,5 L45,5" style="fill:none;stroke:#000000" '
                                            'i:running_stitch_length_mm="2"/>'))
    bean = stitch_engine.generate(document('<path d="M5,5 L45,5" style="fill:none;stroke:#000000" '
                                           'i:running_stitch_length_mm="2" i:bean_stitch_repeats="1"/>'))
    locks = 8   # four start and four end lock stitches in both
    assert len(sewn(bean))-locks == 3*(len(sewn(plain))-locks)
    first = [s for s in plain['stitches'] if s[2] == 'STITCH'][:5]
    # Start lock retraces 0.6 mm along the path: out, back, out, back.
    assert [round(s[0]) for s in first] == [50, 56, 50, 56, 50]


def test_colour_change_and_trims_between_objects():
    plan = stitch_engine.generate(document(
        '<path d="M5,5 L20,5 L20,20 L5,20 Z" style="fill:#ff0000" i:trim_after="true"/>'
        '<path d="M30,5 L45,5 L45,20 L30,20 Z" style="fill:#0000ff"/>'))
    commands = [s[2] for s in plan['stitches']]
    assert [t['color'] for t in plan['threadlist']] == ['#ff0000', '#0000ff']
    assert commands.count('COLOR_CHANGE') == 1 and commands.count('TRIM') >= 1
    assert commands[-1] == 'END'


@pytest.mark.parametrize('method', ['contour_fill', 'circular_fill', 'meander_fill'])
def test_other_fill_methods_stay_inside(method):
    plan = stitch_engine.generate(document(f'<path d="M10,10 L40,10 L40,40 L10,40 Z" style="fill:#00aa00" '
                                           f'i:fill_method="{method}" i:row_spacing_mm="1"/>'))
    segments = sewn(plan)
    assert len(segments) > 50
    assert all(9.8 <= v <= 40.2 for a, b in segments for p in (a, b) for v in p)


def test_generated_artwork_passes_release_gate(tmp_path):
    path = tmp_path/'art.png'
    image = Image.new('RGB', (300, 200), 'white')
    draw = ImageDraw.Draw(image)
    draw.ellipse((20, 20, 180, 180), fill=(200, 30, 40)); draw.rectangle((200, 40, 280, 160), fill=(20, 60, 160))
    image.save(path)
    payload = digitize(path, tmp_path/'out', 40)
    assert payload['engine'] == stitch_engine.NAME and payload['stitch_count'] > 500
    for fmt in ('pes', 'dst'):
        assert checked_bytes(tmp_path/'out', fmt)
