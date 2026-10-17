import numpy as np
import pyembroidery as emb
import pytest

from embroiderly.gap_repair import repair
from embroiderly.release_gate import check_pattern, ReleaseError
from embroiderly.machine_files import write_pair, read_pattern


def fixture():
    mask = np.ones((100, 100), bool)
    mask[:, 40:60] = False
    p = emb.EmbPattern()
    p.add_thread('#202020')
    p.stitches = ([[10, 50, emb.JUMP]] +
                  [[x, 50, 0] for x in (10, 14, 18, 22, 26, 30, 70, 74, 78, 82, 86, 90)] +
                  [[90, 50, emb.END]])
    return p, mask


def test_gap_cut_retains_points_and_passes_saved_files(tmp_path):
    p, mask = fixture()
    with pytest.raises(ReleaseError, match='cross'):
        check_pattern(p, mask, .1, [0, 0])
    original = [s[:2] for s in p.stitches if s[2] == emb.STITCH]
    report = repair(p, mask, .1, [0, 0])
    assert report['gaps_cut'] == 1
    assert report['original_needle_movement_mm'] == 0
    assert all(point in [s[:2] for s in p.stitches if s[2] == 0] for point in original)
    write_pair(p, tmp_path/'design.pes', tmp_path/'design.dst', {'version': 6, 'encode': False})
    for fmt in ('pes', 'dst'):
        decoded = read_pattern(tmp_path/('design.'+fmt))
        check_pattern(decoded, mask, .1, [0, 0])
        assert decoded.count_stitch_commands(emb.TRIM) == 1
    saved = [s[:] for s in p.stitches]
    assert repair(p, mask, .1, [0, 0])['gaps_cut'] == 0
    assert p.stitches == saved


def test_no_anchor_or_invalid_endpoint_stays_blocked():
    p, mask = fixture()
    p.stitches[7][:2] = [50, 50]
    saved = [s[:] for s in p.stitches]
    assert repair(p, mask, .1, [0, 0])['gaps_cut'] == 0
    assert p.stitches == saved
    with pytest.raises(ReleaseError):
        check_pattern(p, mask, .1, [0, 0])
