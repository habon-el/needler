import numpy as np
import pyembroidery as emb
import pytest
from embroiderly.knockout_routing import protect, verify


def design():
    mask=np.zeros((60,100),bool)
    mask[10:50,10:40]=True;mask[10:50,60:90]=True
    p=emb.EmbPattern();p.add_thread('#000000')
    p.stitches=[[15,25,emb.JUMP],[15,25,emb.STITCH],[30,25,emb.STITCH],
                [65,25,emb.STITCH],[80,25,emb.STITCH],[80,25,emb.END]]
    return mask,p


def test_cut_and_lock_crossing_preserves_ink_paths(tmp_path):
    mask,p=design()
    with pytest.raises(ValueError,match='across a removed'):verify(p,mask,.1,[0,0])
    assert protect(p,mask,.1,[0,0])==1
    verify(p,mask,.1,[0,0])
    assert sum(s[2]==emb.TRIM for s in p.stitches)==1
    assert [30,25,emb.STITCH] in p.stitches and [80,25,emb.STITCH] in p.stitches
    for suffix,writer in [('pes',emb.write_pes),('dst',emb.write_dst)]:
        target=tmp_path/('design.'+suffix);writer(p,str(target))
        verify(emb.EmbPattern(str(target)),mask,.1,[0,0])
        first=target.read_bytes();writer(p,str(target));assert first==target.read_bytes()


def test_unchanged_path_is_byte_identical(tmp_path):
    mask,p=design();mask[:]=True
    old=tmp_path/'before.pes';new=tmp_path/'after.pes';emb.write_pes(p,str(old))
    assert protect(p,mask,.1,[0,0])==0
    emb.write_pes(p,str(new));assert old.read_bytes()==new.read_bytes()


def test_loose_jump_is_cut():
    mask,p=design();p.stitches.insert(3,[65,25,emb.JUMP])
    assert protect(p,mask,.1,[0,0])==1
    verify(p,mask,.1,[0,0])


def test_unrecoverable_isolated_stitch_fails_closed():
    mask,p=design();p.stitches=p.stitches[:4]+[[65,25,emb.END]]
    with pytest.raises(ValueError,match='isolated stitch'):protect(p,mask,.1,[0,0])
def test_failed_readback_does_not_replace_existing_machine_files(tmp_path,monkeypatch):
    import json
    from types import SimpleNamespace
    from PIL import Image
    from embroiderly import engine
    from embroiderly import knockout_routing
    mask,p=design()
    rgba=np.zeros((*mask.shape,4),np.uint8);rgba[mask,3]=255
    source=tmp_path/'prepared.png';Image.fromarray(rgba).save(source)
    source.with_suffix('.prep.json').write_text(json.dumps({'options':{'colour_knockouts':[{}]}}))
    raw=tmp_path/'plan.json';emb.write_json(p,str(raw))
    directory=tmp_path/'export';directory.mkdir()
    for suffix in ['pes','dst']:(directory/('design.'+suffix)).write_bytes(b'previous-approved-file')
    monkeypatch.setattr('embroiderly.engine_cache.cache_key',lambda *args:'test')
    monkeypatch.setattr('embroiderly.engine_cache.lookup',lambda *args:None)
    monkeypatch.setattr('embroiderly.thread_recolour.reuse',lambda *args:None)
    monkeypatch.setattr(engine.subprocess,'run',lambda *args,**kwargs:SimpleNamespace(returncode=0,stdout=raw.read_bytes()))
    monkeypatch.setattr(knockout_routing,'protect',lambda *args:0)
    def fail(*args):raise ValueError('Controlled unsafe readback')
    monkeypatch.setattr(knockout_routing,'verify',fail)
    with pytest.raises(ValueError,match='Controlled unsafe readback'):engine.digitize(source,directory,6)
    for suffix in ['pes','dst']:assert (directory/('design.'+suffix)).read_bytes()==b'previous-approved-file'

