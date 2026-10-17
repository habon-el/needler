import numpy as np
import pyembroidery as emb
import pytest
from embroiderly.machine_files import write_pair, read_pattern
from embroiderly.release_gate import check_pattern, ReleaseError


def test_real_serialized_short_remainder_before_and_after(tmp_path):
    p=emb.EmbPattern();p.add_thread('#123456')
    p.stitches=[[10,10,emb.JUMP],[10,10,emb.STITCH],[10,40,emb.STITCH],
                [10,42,emb.STITCH],[20,42,emb.STITCH],[20,42,emb.END]]
    mask=np.ones((100,100),bool)
    pes,dst=tmp_path/'design.pes',tmp_path/'design.dst'
    write_pair(p,pes,dst,{'version':6})
    with pytest.raises(ReleaseError,match='0.20 mm'):
        check_pattern(read_pattern(pes),mask,.1,[0,0])
    result=write_pair(p,pes,dst,{'version':6},repair_spacing=True)
    assert result.extras['spacing_repair']['straight_runs']==1
    for path in (pes,dst):check_pattern(read_pattern(path),mask,.1,[0,0])
    before=[f.read_bytes() for f in (pes,dst)]
    write_pair(p,pes,dst,{'version':6},repair_spacing=True)
    assert before==[f.read_bytes() for f in (pes,dst)]


def test_corner_below_minimum_is_still_refused(tmp_path):
    p=emb.EmbPattern();p.add_thread('#000000')
    p.stitches=[[10,10,emb.JUMP],[10,10,emb.STITCH],[10,40,emb.STITCH],
                [12,40,emb.STITCH],[12,60,emb.STITCH],[12,60,emb.END]]
    pes,dst=tmp_path/'design.pes',tmp_path/'design.dst'
    write_pair(p,pes,dst,repair_spacing=True)
    with pytest.raises(ReleaseError,match='0.20 mm'):
        check_pattern(read_pattern(pes),np.ones((100,100),bool),.1,[0,0])
