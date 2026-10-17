import numpy as np
import pyembroidery as emb
import pytest
from embroiderly.start_lock_repair import repair
from embroiderly.release_gate import check_pattern, ReleaseError
from embroiderly.machine_files import write_pair, read_pattern


def example():
    p = emb.EmbPattern(); p.add_thread('#202020')
    p.stitches = [[30,30,emb.JUMP],[30,30,0],[28,28,0],[30,30,0],
                  [28,28,0],[20,28,0],[12,28,0],[12,28,emb.END]]
    return p


def test_start_lock_roundtrip_and_unchanged_outline(tmp_path):
    p=example(); mask=np.ones((80,80),bool)
    with pytest.raises(ReleaseError, match='too short'):
        check_pattern(p,mask,.1,[0,0])
    original=[s[:] for s in p.stitches]
    report=repair(p,mask,.1,[0,0])
    assert report['start_locks_rebuilt']==1
    assert report['largest_needle_movement_mm']<=.45
    assert len(p.stitches)==len(original)
    assert p.stitches[:2]==original[:2] and p.stitches[5:]==original[5:]
    write_pair(p,tmp_path/'design.pes',tmp_path/'design.dst',{'version':6,'encode':False})
    for fmt in ('pes','dst'):
        check_pattern(read_pattern(tmp_path/('design.'+fmt)),mask,.1,[0,0])
    assert repair(p,mask,.1,[0,0])['start_locks_rebuilt']==0


def test_invalid_mask_and_unknown_lock_are_not_changed():
    for empty in (True,False):
        p=example()
        if not empty:p.stitches[3][0]+=1
        original=[s[:] for s in p.stitches]
        mask=np.full((80,80),not empty,bool)
        assert repair(p,mask,.1,[0,0])['start_locks_rebuilt']==0
        assert p.stitches==original
