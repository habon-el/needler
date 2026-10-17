from pathlib import Path
import pytest
from PIL import Image
from embroiderly.size_sets import PRESETS, resolve_size, exported_audit, regenerate_sizes
from embroiderly.web import create_app

def test_presets_and_subject_sizing():
    assert [p["mm"] for p in PRESETS]==[80,55,60,280]
    assert resolve_size({"axis":"width","mm":80},(100,200), (20,30,60,110))==400
    with pytest.raises(ValueError): resolve_size({"axis":"width","mm":float("nan")},(100,100),(0,0,50,50))

def test_export_audit_reads_file(tmp_path):
    import pyembroidery as emb
    p=emb.EmbPattern();p.add_thread("#123456");p.add_stitch_absolute(emb.JUMP,30,40)
    p.add_stitch_absolute(emb.STITCH,60,80)
    p.add_stitch_absolute(emb.STITCH,90,120)
    p.add_stitch_absolute(emb.TRIM,90,120)
    p.add_stitch_absolute(emb.END,60,80)
    path=tmp_path/"plan.pes";emb.write_pes(p,str(path),{"version":6})
    audit=exported_audit(path)
    assert audit["stitch_count"]>=1
    assert audit["total_jump_mm"]>=5
    assert audit["longest_jump_mm"]>=5
    assert audit["thread_length_mm"]>=5

def test_size_set_requires_confirmation(tmp_path):
    c=create_app(tmp_path).test_client()
    Image.new("RGB",(30,30),"red").save(tmp_path/"work/uploads/a.png")
    r=c.post("/size-set/a.png",json={"options":{},"sizes":PRESETS[:1]})
    assert r.status_code==400 and "confirm" in r.json["error"].lower()

def test_each_size_prepares_and_generates_independently(tmp_path,monkeypatch):
    import embroiderly.size_sets as module
    from types import SimpleNamespace
    p=tmp_path/"source.png";Image.new("RGBA",(100,100),"red").save(p)
    calls=[]
    def engine(source,folder,height_mm):
        calls.append(height_mm)
        import pyembroidery as emb
        plan=emb.EmbPattern();plan.add_thread("#ff0000");plan.add_stitch_absolute(emb.STITCH,10,10);plan.add_stitch_absolute(emb.STITCH,20,20);plan.add_stitch_absolute(emb.END,20,20)
        emb.write_pes(plan,str(folder/"design.pes"),{"version":6});emb.write_dst(plan,str(folder/"design.dst"))
        return {"steps":[{"x":1,"y":1,"t":"stitch","color":"#ff0000"},{"x":2,"y":2,"t":"stitch","color":"#ff0000"}],"colors":["#ff0000"],"stitch_count":2,"trim_count":0}
    monkeypatch.setattr(module,"digitize",engine)
    result=regenerate_sizes(p,{},PRESETS[:2],tmp_path/"set")
    assert calls==[80,55]
    assert len(result)==2 and all(r["status"]=="generated" for r in result)
    assert all((tmp_path/"set"/str(i)/"design.pes").exists() for i in range(2))
