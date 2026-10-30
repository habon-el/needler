"""Stitch edits: an added stop or cut, a deleted or moved stitch, kept as a recipe."""
import json
import math
from pathlib import Path

import pytest
import pyembroidery as emb
from PIL import Image, ImageDraw

from embroiderly.stitch_edits import apply, choices


def plan(points, threads=('#112233',), tail=('END',)):
    stitches = [[0, 0, 'JUMP']] + [[x, y, 'STITCH'] for x, y in points] + [[*points[-1], c] for c in tail]
    return dict(stitches=stitches, threadlist=[dict(color=c) for c in threads], extras={})


ROW = [(x, 0) for x in range(0, 301, 30)]       # 3 mm stitches along a row; stitch n=k+1 is at x=3k mm


def kinds(p):
    return [s[2] for s in p['stitches']]


def test_saved_edits_are_checked():
    assert choices({}) == []
    edit = dict(kind='stop', x=1.234, y=-2, n=7)
    assert choices(dict(stitch_edits=[edit])) == [dict(kind='stop', x=1.23, y=-2.0, n=7)]
    for bad in ([dict(edit, kind='jump')], [dict(edit, n=0)], [dict(edit, x=float('nan'))], 'stop',
                [dict(edit, kind='move')], [dict(edit, kind='move', to=[5, -2])], [edit]*201):
        with pytest.raises(ValueError):
            choices(dict(stitch_edits=bad))
    assert choices(dict(stitch_edits=[dict(edit, kind='move', to=[3.5, -1])]))[0]['to'] == [3.5, -1.0]


def test_a_stop_repeats_the_thread_and_shifts_later_threads():
    p = plan(ROW + [(300, 40)], threads=('#111111', '#222222'), tail=())
    p['stitches'] += [[300, 40, 'TRIM'], [300, 40, 'COLOR_CHANGE'], [0, 40, 'JUMP'], [0, 40, 'STITCH'],
                      [40, 40, 'STITCH'], [40, 40, 'END']]
    p['extras']['puff_threads'] = [1]
    report = apply(p, [dict(kind='stop', x=9, y=0, n=4)])
    assert report == dict(applied=1, dropped=[], stops=[1])
    i = kinds(p).index('COLOR_CHANGE')
    assert p['stitches'][i][:2] == [90, 0] and p['stitches'][i+1] == [120, 0, 'STITCH']
    assert [t['color'] for t in p['threadlist']] == ['#111111', '#111111', '#222222']
    assert p['extras']['puff_threads'] == [2]
    # The machine already stops at a thread change.
    with pytest.raises(ValueError, match='already stops'):
        apply(plan(ROW), [dict(kind='stop', x=30, y=0, n=11)])


def test_a_cut_ties_off_cuts_and_ties_in():
    p = plan(ROW)
    apply(p, [dict(kind='trim', x=15, y=0, n=6)])
    s = p['stitches']
    t = kinds(p).index('TRIM')
    assert s[t][:2] == [150, 0]
    assert s[t-2][:2] == [144, 0] and s[t-1][:2] == [150, 0]           # tie-off: back 0.6 mm and return
    assert [c for *_, c in s[t+1:t+3]] == ['JUMP', 'STITCH'] and s[t+3][:2] == [156, 0] and s[t+4][:2] == [150, 0]
    assert s[t+5][:2] == [180, 0]                                       # then the row goes on
    with pytest.raises(ValueError, match='already cut'):
        apply(plan(ROW, tail=('TRIM', 'END')), [dict(kind='trim', x=30, y=0, n=11)])


def test_deleting_a_stitch_is_refused_when_it_would_break_the_rules():
    p = plan(ROW)
    apply(p, [dict(kind='delete', x=6, y=0, n=3)])
    assert [60, 0, 'STITCH'] not in p['stitches'] and kinds(p).count('STITCH') == 10
    long = plan([(0, 0), (40, 0), (80, 0), (150, 0)])
    with pytest.raises(ValueError, match='longest allowed is 7 mm'):
        apply(long, [dict(kind='delete', x=8, y=0, n=3)])        # would leave 4 -> 15: 11 mm
    short = plan([(0, 0), (40, 0), (41.5, 0), (42.5, 0)])
    with pytest.raises(ValueError, match='shortest allowed is 0.3 mm'):
        apply(short, [dict(kind='delete', x=4.15, y=0, n=3)])    # would leave 4.0 -> 4.25 mm: 0.25 mm
    with pytest.raises(ValueError, match='empty fabric'):
        apply(plan(ROW), [dict(kind='delete', x=6, y=0, n=3)], crosses=lambda a, b: True)
    with pytest.raises(ValueError, match='starts a run'):
        apply(plan(ROW), [dict(kind='delete', x=0, y=0, n=1)])


def test_moving_a_stitch_checks_both_stitches_and_the_fabric():
    p = plan(ROW)
    apply(p, [dict(kind='move', x=6, y=0, n=3, to=[6, 1])])
    assert [60, 10, 'STITCH'] in p['stitches'] and [60, 0, 'STITCH'] not in p['stitches']
    # The first stitch of a run takes its jump along.
    p = plan(ROW)
    apply(p, [dict(kind='move', x=0, y=0, n=1, to=[0, 1])])
    assert p['stitches'][:2] == [[0, 10, 'JUMP'], [0, 10, 'STITCH']]
    with pytest.raises(ValueError, match='longest allowed is 7 mm'):
        apply(plan([(0, 0), (60, 0), (120, 0), (180, 0)]), [dict(kind='move', x=12, y=0, n=3, to=[14, 0])])  # 6 -> 14 mm
    inside = lambda a, b: a[1] > 15 or b[1] > 15                  # fabric ends 1.5 mm above the row
    with pytest.raises(ValueError, match='empty fabric'):
        apply(plan(ROW), [dict(kind='move', x=6, y=0, n=3, to=[6, 2])], crosses=inside)


def test_an_edit_that_no_longer_matches_is_left_out_and_the_nearest_in_order_is_chosen():
    p = plan(ROW + [(0, 0), (30, 0)])                             # the row comes back to x=0, 3
    report = apply(p, [dict(kind='delete', x=3, y=0, n=13), dict(kind='trim', x=99, y=0, n=2)])
    assert report['applied'] == 1 and 'Cut 2 no longer matches' in report['dropped'][0]
    assert p['stitches'][2] == [30, 0, 'STITCH']                   # the early x=3 stitch stays


# --- Through generation, the machine files and the release gate ---

def generate(tmp_path, **extra):
    from embroiderly.auto_digitize import AutoDigitizer
    from embroiderly.web import create_app
    if not (tmp_path / 'work/uploads/block.png').exists():
        create_app(tmp_path)
        image = Image.new('RGB', (300, 200), 'white')
        ImageDraw.Draw(image).rectangle((40, 40, 260, 160), fill='#1d4f91')
        image.save(tmp_path / 'work/uploads/block.png')
    auto = AutoDigitizer(create_app(tmp_path), tmp_path)
    return auto._attempt(tmp_path / 'work/uploads/block.png', dict(artwork_type='logo', count=2, height_mm=40, **extra), .8, True)[0]


def test_stop_cut_delete_and_move_pass_the_release_gate_and_reach_both_files(tmp_path):
    from embroiderly.machine_files import read_pattern
    from embroiderly.release_gate import checked_bytes
    from embroiderly.worksheet import summary
    whole = generate(tmp_path)
    steps = whole['playback']['steps']
    sewn = [i for i, s in enumerate(steps) if s['t'] == 'stitch']
    # Inside a run (stitch before and after), well away from the row ends.
    inner = [i for i in sewn[50:-50] if steps[i-1]['t'] == steps[i+1]['t'] == 'stitch'
             and 1 < math.dist((steps[i-1]['x'], steps[i-1]['y']), (steps[i+1]['x'], steps[i+1]['y'])) < 6]
    def at(i):
        return dict(x=steps[i]['x'], y=steps[i]['y'], n=sum(s['t'] == 'stitch' for s in steps[:i+1]))
    a, b, c, d = inner[len(inner)//5], inner[2*len(inner)//5], inner[3*len(inner)//5], inner[4*len(inner)//5]
    moved = [round(steps[d]['x'] + .2, 1), steps[d]['y']]
    edits = [dict(kind='stop', **at(a)), dict(kind='trim', **at(b)), dict(kind='delete', **at(c)),
             dict(kind='move', **at(d), to=moved), dict(kind='stop', x=steps[a]['x']+50, y=0, n=5)]
    edited = generate(tmp_path, stitch_edits=edits)
    assert not edited.get('error') and not edited.get('gate'), edited
    report = edited['playback']['stitch_edits']
    assert report['applied'] == 4 and len(report['dropped']) == 1 and 'Stop 5' in report['dropped'][0]
    # The stop sews the same thread again: one more colour block, the same number of threads.
    assert len(edited['playback']['colors']) == len(whole['playback']['colors']) + 1
    assert edited['colours'] == whole['colours'] and edited['trims'] == whole['trims'] + 1
    folder = tmp_path / 'work/inkstitch-preview' / Path(edited['prepared']).stem
    for fmt in ('pes', 'dst'):
        assert checked_bytes(folder, fmt)                           # both files pass the release gate
    pes, dst = emb.EmbPattern(str(folder / 'design.pes')), read_pattern(folder / 'design.dst')
    before = read_pattern(tmp_path / 'work/inkstitch-preview' / Path(whole['prepared']).stem / 'design.dst')
    assert pes.count_stitch_commands(emb.STOP) == 1                 # PES: a stop that keeps the thread
    assert dst.count_stitch_commands(emb.COLOR_CHANGE) == before.count_stitch_commands(emb.COLOR_CHANGE) + 1
    assert dst.count_stitch_commands(emb.TRIM) == before.count_stitch_commands(emb.TRIM) + 1
    points = [(x, y) for x, y, f in dst.stitches if f & emb.COMMAND_MASK == emb.STITCH]
    assert (round(moved[0]*10), round(moved[1]*10)) in points
    # Playback and the worksheet show the stop on its own (same-thread) block.
    thread = sum(s['t'] == 'color_change' for s in steps[:a]) + 1
    assert report['stops'] == [thread]
    notes = summary(edited['playback'])['sequence'][thread]['notes']
    assert notes and 'Machine stop you added' in notes[0]
    # Saved edits are part of the cache key: the same edits give the cached result,
    # without them the original stitches come back.
    assert generate(tmp_path, stitch_edits=edits)['playback'] == edited['playback']
    assert generate(tmp_path)['stitches'] == whole['stitches']


def test_a_stitch_moved_onto_empty_fabric_is_refused_with_a_plain_message(tmp_path):
    whole = generate(tmp_path)
    steps = whole['playback']['steps']
    # The left-most stitch lies on the edge of the blue block; 2.5 mm further left is bare fabric.
    i = min((i for i, s in enumerate(steps) if s['t'] == 'stitch' and steps[i-1]['t'] in ('stitch', 'jump')),
            key=lambda i: steps[i]['x'])
    n = sum(s['t'] == 'stitch' for s in steps[:i+1])
    result = generate(tmp_path, stitch_edits=[dict(kind='move', x=steps[i]['x'], y=steps[i]['y'], n=n,
                                                   to=[steps[i]['x']-2.5, steps[i]['y']])])
    assert 'empty fabric' in result.get('error', ''), result


def test_the_lock_guard_allows_stitch_edits():
    # A stop, a cut or one stitch moves no piece, so it never trips a lock.
    from embroiderly.piece_layout import guard
    previous = {'piece_edits': {'a'*20: {'locked': True}}, 'count': 2}
    guard(previous, {**previous, 'stitch_edits': [dict(kind='stop', x=1, y=2, n=3)]})
