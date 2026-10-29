"""Bottom join: each satin letter starts at its baseline on the left, the thread running under
the letter's own stitches; letters with fabric between them still cut (release gate)."""
import re

import pytest

from embroiderly import embroidery_fonts as ef
from embroiderly import lettering_native as ln
from embroiderly import small_lettering as sl


def groups(svg):
    return re.findall(r'<g [^>]*letter-group="glyph"[^>]*>(.*?)</g>', svg, re.S)


def first_point(group):
    x, y = re.search(r' d="M (-?[\d.]+),(-?[\d.]+)', group).groups()
    return float(x), float(y)


def test_letters_start_at_their_baseline_and_keep_their_cuts():
    plain, bottom = ef.layout('HELLO', 'graduate', 300), ef.layout('HELLO', 'graduate', 300, join='bottom')
    assert 'id="entry' not in plain
    assert bottom.count('trim_after="true"') == plain.count('trim_after="true"')
    for before, after in zip(groups(plain), groups(bottom)):
        assert 'id="entry' in after.split('column')[0]          # sewn before the letter's strokes
        (_, y0), (_, y1) = first_point(before), first_point(after)
        assert y1 >= y0                                           # lower down (y points down), at the foot
    # H starts at the bottom of its left stem.
    xs = [float(x) for x, _ in re.findall(r'(-?[\d.]+),(-?[\d.]+)', groups(bottom)[0])]
    x, y = first_point(groups(bottom)[0])
    assert x-min(xs) < 1/ef.PX_MM


def test_touching_script_letters_still_join_inside_the_letters():
    svg = ef.layout('Hello', 'pacifico', 300, join='bottom')
    assert 'id="join-' in svg and 'id="entry' in svg


def test_only_listed_joins():
    with pytest.raises(ValueError):
        ef.layout('AB', 'graduate', 200, join='top')
    with pytest.raises(ValueError):
        sl.layout_options(dict(join='top'))
    assert sl.layout_options(dict(join='bottom'))['join'] == 'bottom'
    # Closest is the plain line: earlier saved lettering keeps its cache key.
    body = dict(text='AB', font='graduate', height_mm=10, available_width_mm=100)
    assert 'join' not in ln.recipe(body) and ln.recipe({**body, 'join': 'bottom'})['join'] == 'bottom'


@pytest.mark.parametrize('settings', [dict(text='Hello', font='graduate'), dict(text='Hello', font='pacifico'),
                                      dict(text='CHAMPIONS', font='graduate', baseline='arc_over', arc_degrees=90),
                                      dict(text='Good Day', font='graduate', envelope='arch_top')])
def test_bottom_joined_lettering_passes_the_file_checks(tmp_path, settings):
    from embroiderly.web import create_app
    client = create_app(tmp_path).test_client()
    result = client.post('/lettering/native/check', json=dict(height_mm=12, available_width_mm=200, colour='#1e3a6e',
                                                              join='bottom', **settings))
    body = result.get_json()
    assert result.status_code == 200, body
    assert body['checks_passed'], body
