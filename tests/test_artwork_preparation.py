import hashlib
import json
import numpy as np
import pytest
from PIL import Image, ImageDraw
from embroiderly.preparation import prepare, selection
from embroiderly.web import create_app

@pytest.fixture
def artwork(tmp_path):
    p=tmp_path/"art.png"
    im=Image.new("RGBA",(100,100),(0,0,0,0))
    d=ImageDraw.Draw(im)
    d.rectangle((10,10,89,89),fill="#aa4422")
    d.rectangle((30,20,65,75),fill="white")
    d.rectangle((45,40,46,41),fill="black")
    im.save(p)
    return p

def test_determinism_and_exact_mask(artwork):
    settings={"count":3,"smooth":0,"floor_mm2":0}
    a,p,r=prepare(artwork,settings);b,q,s=prepare(artwork,settings)
    assert a.tobytes()==b.tobytes() and p==q and r==s
    assert a.getpixel((0,0))[3]==0
    assert any(x["hex"]=="#ffffff" for x in p)
    assert len(p)==3

def test_cleanup_reports_small_features(artwork):
    _,_,r=prepare(artwork,{"count":3,"height_mm":20,"floor_mm2":1,"smooth":0})
    assert r["below_floor_before"]>0
    assert r["below_floor_after"]==0
    assert r["specks_reassigned"]>0
    assert r["regions_after"]<r["regions_before"]

def test_locks_preserve_detail_and_report_warning(artwork):
    _,p,r=prepare(artwork,{"count":3,"locks":["#000000"],"height_mm":20,"floor_mm2":1})
    assert any(c["hex"]=="#000000" and c["locked"] for c in p)
    assert r["below_floor_after"]>0

def test_lasso_and_erase(artwork):
    a,_,_=prepare(artwork,{"selection":"lasso","outline":[[10,10],[89,10],[10,89]],
        "edits":[{"kind":"erase","points":[[20,20]],"radius":3}],"floor_mm2":0})
    assert a.getpixel((20,20))[3]==0
    assert a.getpixel((80,80))[3]==0
    assert a.getpixel((30,25))[3]==255

@pytest.mark.parametrize("o",[{"count":9},{"height_mm":float("nan")},{"locks":["invalid"]},
    {"selection":"grabcut","rect":[0,0,101,100]},{"selection":"lasso","outline":[[1,2]]}])
def test_invalid_settings(artwork,o):
    with pytest.raises(ValueError): prepare(artwork,o)

def test_grabcut_box_and_hints():
    im=Image.new("RGB",(100,100),"blue");ImageDraw.Draw(im).ellipse((25,20,75,80),fill="orange")
    a=selection(im,{"selection":"grabcut","rect":[15,10,85,90]})
    b=selection(im,{"selection":"grabcut","rect":[15,10,85,90]})
    assert np.array_equal(a,b) and a[50,50] and not a[5,5]

def test_persistence_and_original_preserved(tmp_path,artwork):
    client=create_app(tmp_path).test_client();upload=tmp_path/"work/uploads"/artwork.name
    upload.write_bytes(artwork.read_bytes());before=hashlib.sha256(upload.read_bytes()).hexdigest()
    o={"count":3,"smooth":0,"floor_mm2":0}
    a=client.post("/artwork/art.png",json={"options":o,"save":True})
    assert a.status_code==200
    b=client.post("/artwork/art.png",json={"options":o,"save":True})
    assert a.json==b.json
    assert hashlib.sha256(upload.read_bytes()).hexdigest()==before
    saved=tmp_path/"work/uploads"/a.json["prepared_name"]
    assert saved.with_suffix(".prep.json").exists()
    assert json.loads((tmp_path/"work/decisions/art.png.preparation.json").read_text())==o
    assert client.get("/artwork/art.png").status_code==200
    assert client.post("/artwork/art.png",json={"options":{"count":99}}).status_code==400

def test_isolated_speck_is_removed_not_recoloured(artwork):
    im=Image.open(artwork);ImageDraw.Draw(im).rectangle((1,1,2,2),fill="red");im.save(artwork)
    out,_,r=prepare(artwork,{"count":4,"smooth":0,"height_mm":20,"floor_mm2":1})
    assert out.getpixel((1,1))[3]==0
    assert r["mask_specks_removed"]==1
    assert r["below_floor_after"]==0

def test_merge_and_paint(artwork):
    _,palette,_=prepare(artwork,{"count":3,"smooth":0,"floor_mm2":0})
    source=next(c["hex"] for c in palette if c["hex"]!="#ffffff")
    _,after,_=prepare(artwork,{"count":3,"smooth":0,"floor_mm2":0,"merges":{source:"#ffffff"}})
    assert len(after)==2
    out,p,_=prepare(artwork,{"count":4,"smooth":0,"floor_mm2":0,"locks":["#00ff00"],
       "edits":[{"kind":"paint","colour":"#00ff00","points":[[50,50]],"radius":6}]})
    assert out.getpixel((50,50))==(0,255,0,255)

def test_prepared_white_and_exact_pes_rgb(tmp_path,artwork,monkeypatch):
    import subprocess
    from types import SimpleNamespace
    from embroiderly.engine import digitize
    from xml.etree import ElementTree as ET
    artwork.with_suffix(".prep.json").write_text("{}")
    plan={"threadlist":[{"color":"#aa4422"},{"color":"#ffffff"}],
      "stitches":[[0,0,"JUMP"],[10,10,"STITCH"],[20,10,"STITCH"],[20,10,"COLOR_CHANGE"],
                  [30,20,"STITCH"],[40,30,"STITCH"],[40,30,"END"]],"extras":{}}
    def run(args,**kwargs):
        for thread in plan['threadlist']:
            for key in ('description','catalog_number','details','brand','chart','weight'):
                thread[key]=None
        assert "--format=json" in args
        svg=ET.parse(args[-1])
        fills=[el.get("style") for el in svg.getroot() if el.tag.endswith("path")]
        assert any("fill:#ffffff" in f for f in fills)
        return SimpleNamespace(returncode=0,stdout=json.dumps(plan).encode(),stderr=b"")
    monkeypatch.setattr(subprocess,"run",run)
    # This palette-only fixture intentionally exports red and white. Previously
    # its tiny black detail was silently omitted; exclusion must now be explicit.
    choices={'#000000':{'include':False}}
    out=tmp_path/"export";payload=digitize(artwork,out,colours=choices)
    assert payload["colors"]==["#aa4422","#ffffff"]
    hashes=[hashlib.sha256((out/("design."+f)).read_bytes()).hexdigest() for f in ("pes","dst")]
    digitize(artwork,out,colours=choices)
    assert hashes==[hashlib.sha256((out/("design."+f)).read_bytes()).hexdigest() for f in ("pes","dst")]

def test_prepared_navigation_returns_to_source(tmp_path,artwork):
    client=create_app(tmp_path).test_client();(tmp_path/"work/uploads/art.png").write_bytes(artwork.read_bytes())
    preview=client.post("/artwork/art.png",json={"options":{}}).json
    decisions={item['id']:'drop' for item in preview['report']['cleanup_review']}
    result=client.post("/artwork/art.png",json={"options":{"cleanup_decisions":decisions},"save":True})
    assert result.status_code==200
    response=client.get("/artwork/"+result.json["prepared_name"])
    assert response.status_code==302 and response.location.endswith("/artwork/art.png")
