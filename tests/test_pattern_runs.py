"""Pattern run (wave, loops, key repeated end to end) and sculpture run (raised cord) borders."""
import math

import pytest

from embroiderly.stitch_paths import PATTERNS, pattern_run, sculpture_run

LINE = [(0.0, 0.0), (30.0, 0.0)]
RING = [(10+8*math.cos(i*math.pi/60), 10+8*math.sin(i*math.pi/60)) for i in range(120)]
RING.append(RING[0])


def legs(points):
    return [math.dist(p, q) for p, q in zip(points, points[1:])]


@pytest.mark.parametrize('pattern', PATTERNS)
@pytest.mark.parametrize('width', (2.0, 2.5, 4.0, 6.0))
def test_patterns_fill_the_band_with_safe_stitches(pattern, width):
    for line in (LINE, RING):
        points = pattern_run(line, 2.0, width, pattern)
        assert min(legs(points)) >= .45 and max(legs(points)) <= 2.0+1e-6
        assert points[0] == pytest.approx(line[0]) and points[-1] == pytest.approx(line[-1])
    # On a straight line the pattern reaches both edges of the band, and no further.
    ys = [y for _, y in pattern_run(LINE, 2.0, width, pattern)]
    assert max(ys) == pytest.approx(width/2, abs=.02) and min(ys) == pytest.approx(-width/2, abs=.02)


def test_wave_has_no_plain_stitches_between_repeats():
    points = pattern_run(LINE, 2.0, 2.5, 'wave')
    # Every crest and trough is sewn: about 30 / (1.6 * 2.5) = 8 waves.
    crests = sum(1 for _, y in points if y == pytest.approx(1.25, abs=.02))
    troughs = sum(1 for _, y in points if y == pytest.approx(-1.25, abs=.02))
    assert crests == troughs == 8
    # The line is crossed only where the wave crosses it, never followed.
    on_line = [i for i, (_, y) in enumerate(points) if abs(y) < 1e-6]
    assert all(b-a > 1 for a, b in zip(on_line, on_line[1:]))


def test_loops_run_back_on_themselves():
    points = pattern_run(LINE, 2.0, 2.5, 'loop')
    backwards = sum(1 for p, q in zip(points, points[1:]) if q[0] < p[0]-1e-6)
    assert backwards >= 6


def test_key_turns_square_corners():
    points = pattern_run(LINE, 2.0, 4.0, 'key')
    # Key strokes run along or straight across the line, nothing slanted.
    assert all(abs(q[0]-p[0]) < 1e-6 or abs(q[1]-p[1]) < 1e-6 for p, q in zip(points[1:-1], points[2:-1]))


def test_sculpture_run_sews_two_forward_one_back():
    points = sculpture_run(LINE, 2.5)
    xs = [x for x, _ in points]
    steps = [b-a for a, b in zip(xs, xs[1:])]
    assert all(s == pytest.approx(2.5) or s == pytest.approx(-1.25) for s in steps[:-1])
    assert all(y == 0 for _, y in points)
    # Each part of the line is sewn three times by overlapping stitches; the half step at
    # either end only twice.
    assert sum(legs(points)) == pytest.approx(3*30.0-2*1.25)
    assert points[-1] == pytest.approx(LINE[-1])


def test_sculpture_run_on_a_short_line_is_still_a_triple_line():
    points = sculpture_run([(0, 0), (2, 0)], 2.5)
    assert sum(legs(points)) == pytest.approx(6.0)


@pytest.mark.parametrize('options', [{'border_style': 'pattern', 'border_pattern': 'key', 'border_width': 2.5},
                                     {'border_style': 'pattern', 'border_pattern': 'loop', 'border_width': 2.0},
                                     {'border_style': 'sculpture', 'border_width': 1.0}])
def test_pattern_and_sculpture_borders_pass_the_release_gate(tmp_path, options):
    from test_stitch_types_engine import design
    from embroiderly.release_gate import checked_bytes
    _, svg = design(tmp_path, dict(options, border_colour='#202020'))
    assert f'outline_style="{options["border_style"]}"' in svg
    if options['border_style'] == 'pattern':
        assert f'outline_pattern="{options["border_pattern"]}"' in svg
    assert checked_bytes(tmp_path/'out', 'dst')


def test_unknown_pattern_is_refused():
    import numpy as np
    from embroiderly.borders import border_plan
    mask = np.zeros((100, 100), bool)
    mask[20:80, 20:80] = True
    with pytest.raises(ValueError, match='pattern'):
        border_plan(mask, 50, {'border_style': 'pattern', 'border_pattern': 'zigzag'})
