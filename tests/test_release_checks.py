import numpy as np
import pyembroidery as emb
import pytest
from embroiderly.release_gate import check_pattern,ReleaseError,record_context,checked_bytes
from embroiderly.machine_files import write_pair


def pattern(points):
    p=emb.EmbPattern();p.add_thread('#000000');p.stitches=points;return p


@pytest.mark.parametrize('end', [2,71])
def test_short_and_long_stitch_rejected_with_location(end):
    p=pattern([[10,10,emb.JUMP],[10,10,emb.STITCH],[10+end,10,emb.STITCH]])
    with pytest.raises(ReleaseError,match='outside 0.3') as caught:
        check_pattern(p,np.ones((200,200),bool),.1,[0,0])
    assert caught.value.location['command']==2


def test_removed_area_and_cumulative_uncut_travel_rejected():
    mask=np.ones((100,100),bool);mask[:,40:60]=False
    p=pattern([[20,20,emb.JUMP],[20,20,emb.STITCH],[70,20,emb.STITCH]])
    with pytest.raises(ReleaseError,match='removed area'):check_pattern(p,mask,.1,[0,0])
    p=pattern([[10,10,emb.JUMP],[10,10,emb.STITCH],[45,10,emb.JUMP],[80,10,emb.JUMP]])
    with pytest.raises(ReleaseError,match='uncut travel'):check_pattern(p,np.ones((100,100),bool),.1,[0,0])


def test_good_files_download_and_tampered_pair_fails(tmp_path):
    p=pattern([[10,10,emb.JUMP],[10,10,emb.STITCH],[30,10,emb.STITCH],[30,10,emb.END]])
    write_pair(p,tmp_path/'design.pes',tmp_path/'design.dst',{'version':6})
    record_context(tmp_path,np.ones((100,100),bool),.1,[0,0])
    for fmt in ('pes','dst'):assert checked_bytes(tmp_path,fmt)==(tmp_path/('design.'+fmt)).read_bytes()
    (tmp_path/'design.dst').write_bytes(b'changed')
    with pytest.raises(ReleaseError,match='changed since'):checked_bytes(tmp_path,'pes')
