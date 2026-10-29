import json

import numpy as np
import pyembroidery as emb

from embroiderly import lessons
from embroiderly.export_findings import explain, inspect


def _pattern():
    pattern = emb.EmbPattern()
    pattern.add_thread('#202020'); pattern.add_thread('#607070')
    for x in range(0, 200, 20):       # thread 1, inside the picture: fine
        pattern.add_stitch_absolute(emb.STITCH, x, 0)
    pattern.add_command(emb.COLOR_CHANGE)
    for y in range(-300, 300, 30):    # thread 2, sewn just past the right edge
        pattern.add_stitch_absolute(emb.STITCH, 520, y)
    pattern.add_command(emb.END)
    return pattern


def test_explain_groups_findings_by_thread_and_edge():
    alpha = np.ones((101, 101), bool)            # 100 x 100 mm picture, 1 mm a pixel
    pattern = _pattern()
    issues = [i for i in inspect(pattern, alpha, 1.0, [50, 50]) if i['code'] == 'crossing']
    assert issues
    detail = explain(issues, pattern, alpha.shape, 1.0, [50, 50])
    assert detail['cause'] == 'edge'
    assert [(g['thread'], g['where']) for g in detail['groups']] == [('#607070', 'edge')]
    assert 'picture\'s edge' in detail['text'] and json.loads(detail['signature'])
    # The same failure gives the same signature on the next attempt.
    assert explain(issues, pattern, alpha.shape, 1.0, [50, 50])['signature'] == detail['signature']


def test_a_lesson_records_what_fixed_a_failure(tmp_path):
    failed = dict(number=1, gate='Export blocked', gate_detail=dict(text='on the edge', cause='edge', signature='s'),
                  options=dict(border_placement='center', count=4, edits=[1, 2]))
    passed = dict(number=2, options=dict(border_placement='inside', count=4, edits=[1, 2]))
    row = lessons.record(tmp_path, 'logo', 'add a border', [failed, passed])
    assert row['fixed_by'] == {'border_placement': ['center', 'inside']} and row['cause'] == 'edge'
    assert 'edits' not in row['settings_that_failed']
    assert lessons.record(tmp_path, 'logo', '', [passed]) is None     # nothing to learn
    handed = lessons.for_claude(tmp_path)
    assert len(handed) == 1 and 'settings_that_failed' not in handed[0]


def test_lessons_keep_a_bounded_history(tmp_path):
    failed = dict(gate='Export blocked', options={})
    for n in range(lessons.KEEP + 5):
        lessons.record(tmp_path, 'logo', f'run {n}', [failed])
    assert len(lessons.load(tmp_path)) == lessons.KEEP
    assert len(lessons.for_claude(tmp_path)) == lessons.HANDED
    (tmp_path / 'lessons.json').write_text('not json')
    assert lessons.load(tmp_path) == []
