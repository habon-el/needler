import numpy as np
import pyembroidery as emb
from embroiderly.lock_repair import repair
from embroiderly.release_gate import check_pattern
from embroiderly.machine_files import write_pair,read_pattern


def test_end_lock_repair_survives_both_formats(tmp_path):
    p=emb.EmbPattern();p.add_thread('#202020')
    p.stitches=[[119,377,emb.JUMP],[119,377,0],[114,377,0],
                [118,377,0],[116,377,0],[118,377,0],[118,377,0],
                [118,377,emb.TRIM],[140,377,emb.JUMP],
                [140,377,emb.STITCH],[150,377,emb.STITCH],[150,377,emb.END]]
    mask=np.ones((500,500),bool)
    report=repair(p,mask,.1,[0,0])
    assert report['end_locks_rebuilt']==1
    assert report['largest_endpoint_change_mm']<=.45
    write_pair(p,tmp_path/'design.pes',tmp_path/'design.dst',{'version':6,'encode':False})
    for fmt in ('pes','dst'):
        decoded=read_pattern(tmp_path/('design.'+fmt))
        check_pattern(decoded,mask,.1,[0,0])
        assert decoded.count_stitch_commands(emb.TRIM)==1
    before=[s[:] for s in p.stitches]
    assert repair(p,mask,.1,[0,0])['end_locks_rebuilt']==0
    assert p.stitches==before


def test_empty_area_prevents_lock_repair():
    p=emb.EmbPattern();p.stitches=[[119,377,1],[119,377,0],[114,377,0],
        [118,377,0],[116,377,0],[118,377,0],[118,377,0],[118,377,2]]
    before=[s[:] for s in p.stitches]
    assert repair(p,np.zeros((500,500),bool),.1,[0,0])['end_locks_rebuilt']==0
    assert p.stitches==before
