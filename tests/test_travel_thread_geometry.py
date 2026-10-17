"""A loose thread spans needle penetrations, not every travel waypoint."""
import numpy as np
import pyembroidery as emb
import pytest
from embroiderly.release_gate import check_pattern, ReleaseError


def ring():
    mask = np.ones((70, 70), bool)
    mask[25:36, 25:36] = False
    return mask


def test_jump_around_hole_still_leaves_diagonal_loose_thread():
    p = emb.EmbPattern()
    p.stitches = [[10, 10, emb.JUMP], [10, 10, emb.STITCH],
                  [50, 10, emb.JUMP], [50, 50, emb.STITCH], [50, 50, emb.END]]
    with pytest.raises(ReleaseError, match='removed area'):
        check_pattern(p, ring(), .1, [0, 0])


def test_stop_does_not_cut_the_thread():
    p = emb.EmbPattern()
    p.stitches = [[10, 10, emb.JUMP], [10, 10, emb.STITCH],
                  [10, 10, emb.STOP], [50, 50, emb.STITCH], [50, 50, emb.END]]
    with pytest.raises(ReleaseError, match='removed area'):
        check_pattern(p, ring(), .1, [0, 0])


def test_explicit_trim_allows_positioning_to_other_side():
    p = emb.EmbPattern()
    p.stitches = [[10, 10, emb.JUMP], [10, 10, emb.STITCH],
                  [10, 10, emb.TRIM], [50, 50, emb.JUMP],
                  [50, 50, emb.STITCH], [55, 50, emb.STITCH], [55, 50, emb.END]]
    check_pattern(p, ring(), .1, [0, 0])


def test_sewn_span_includes_uncut_positioning_move():
    p = emb.EmbPattern()
    p.stitches = [[10, 10, emb.JUMP], [10, 10, emb.STITCH],
                  [50, 10, emb.JUMP], [90, 10, emb.STITCH], [90, 10, emb.END]]
    with pytest.raises(ReleaseError, match='stitch length 8.00'):
        check_pattern(p, np.ones((100, 100), bool), .1, [0, 0])
