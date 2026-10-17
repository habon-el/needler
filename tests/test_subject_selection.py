"""Subject selection Stage A: no model dependency and persisted binary masks."""
import numpy as np
from PIL import Image
from embroiderly import preparation as p
from embroiderly.web import create_app

def test_saved_mask_reused_without_running_selector(tmp_path,monkeypatch):
    image=Image.new("RGBA",(30,30),"red");source=tmp_path/"source.png";image.save(source)
    count=[]
    def select(*args):
        count.append(1)
        mask=np.zeros((30,30),bool);mask[5:25,5:25]=True
        return mask
    monkeypatch.setattr(p,"selection",select)
    a=p.cached_selection(source,image,{"selection":"full"},tmp_path/"masks")
    b=p.cached_selection(source,image,{"selection":"full","count":7},tmp_path/"masks")
    assert np.array_equal(a,b) and len(count)==1
    c=p.cached_selection(source,image,{"selection":"full","edge":1},tmp_path/"masks")
    assert len(count)==2
    assert set(np.unique(np.asarray(Image.open(next((tmp_path/"masks").glob("*.png"))))))<={0,255}

def test_mask_holes_specks_and_manual_background():
    image=Image.new("RGBA",(100,100),"red")
    mask=np.zeros((100,100),bool);mask[10:90,10:90]=True
    mask[50,50]=False;mask[1,1]=True
    cleaned,r=p.clean_selection(mask.copy(),image,{"height_mm":20,"floor_mm2":1,"mask_holes_mm2":1})
    assert cleaned[50,50] and not cleaned[1,1]
    assert r["mask_holes_filled"]==1 and r["mask_specks_removed"]==1
    cleaned,r=p.clean_selection(mask.copy(),image,{"selection":"grabcut","height_mm":20,"floor_mm2":1,
        "hints":[{"kind":"remove","points":[[50,50]],"radius":1}]})
    assert not cleaned[50,50]

def test_explicit_subject_confirmation_and_saved_mask(tmp_path):
    c=create_app(tmp_path).test_client()
    Image.new("RGB",(20,20),"red").save(tmp_path/"work/uploads/a.png")
    response=c.post("/artwork/a.png",json={"options":{},"digitize":True})
    assert response.status_code==400 and "Confirm" in response.json["error"]
    saved=c.post("/artwork/a.png",json={"options":{},"save":True})
    assert saved.status_code==200 and saved.json["isolated"].startswith("data:image/png")
    mask=tmp_path/"work/decisions"/(saved.json["prepared_name"]+".mask.png")
    assert mask.exists() and Image.open(mask).mode=="L"

def test_missing_sam_does_not_affect_stage_a(tmp_path,monkeypatch):
    monkeypatch.setenv("SAM2_CHECKPOINT",str(tmp_path/"missing-model.pt"))
    image=Image.new("RGBA",(30,30),"red");source=tmp_path/"source.png";image.save(source)
    prepared,_,_=p.prepare(source,{"selection":"lasso","outline":[[2,2],[25,2],[2,25]]})
    assert prepared.getpixel((5,5))[3]==255
    assert prepared.getpixel((28,28))[3]==0
