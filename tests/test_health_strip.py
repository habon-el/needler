import numpy as np
from PIL import Image, ImageDraw
from embroiderly.preparation import prepare

def test_small_feature_warnings_have_actionable_bounds(tmp_path):
    p=tmp_path/"warning.png"
    image=Image.new("RGBA",(100,100),"red")
    ImageDraw.Draw(image).rectangle((48,48,49,49),fill="black")
    image.save(p)
    _,_,r=prepare(p,{"count":2,"height_mm":20,"floor_mm2":1,"smooth":0,"locks":["#000000"]})
    assert r["below_floor_after"]==1
    assert r["small_features"][0]["bounds"]==[48,48,50,50]
    assert r["small_features"][0]["colour"]=="#000000"
    assert r["small_features"][0]["area_mm2"]<1
