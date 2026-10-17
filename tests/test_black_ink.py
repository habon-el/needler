import copy
import numpy as np
import pytest
from PIL import Image, ImageDraw
from embroiderly.preparation import prepare
from embroiderly.ink_lines import ink_mask, add_running_paths
from embroiderly.saved_plans import equivalent
import xml.etree.ElementTree as ET


def sample(tmp_path):
    im=Image.new('RGBA',(100,100),'white');d=ImageDraw.Draw(im)
    d.rectangle((15,10,80,85),outline='black',width=1)
    d.line((20,60,70,60),fill=(120,120,120),width=1)
    d.ellipse((30,25,33,28),fill='black');d.point((60,30),fill='black')
    path=tmp_path/'drawing.png';im.save(path)
    return path,im


def test_white_removed_without_dropping_thin_ink(tmp_path):
    path,im=sample(tmp_path)
    options={'ink_only':True,'smooth':3,'floor_mm2':25,'simplify':100,'height_mm':20}
    before=copy.deepcopy(options)
    result,palette,report=prepare(path,options)
    pixels=np.asarray(result);expected=ink_mask(np.asarray(im)[:,:,:3])
    assert np.array_equal(pixels[:,:,3]>0,expected)
    assert np.all(pixels[expected,:3]==0)
    assert [p['hex'] for p in palette]==['#000000']
    assert report['boundary_pixels_changed']==0 and report['specks_reassigned']==0
    assert options==before


def test_normal_mode_retains_intentional_white(tmp_path):
    path,_=sample(tmp_path)
    result,palette,_=prepare(path,{'count':2,'smooth':0,'floor_mm2':0})
    assert result.getpixel((50,50))[3]==255
    assert min(result.getpixel((50,50))[:3])>245


def test_selection_and_eraser_still_limit_black_ink(tmp_path):
    path,_=sample(tmp_path)
    result,_,_=prepare(path,{'ink_only':True,'selection':'lasso','outline':[[0,0],[49,0],[49,99],[0,99]],'edits':[{'kind':'erase','points':[[30,25]],'radius':6}]})
    pixels=np.asarray(result)
    assert not pixels[:,50:,3].any() and pixels[25,30,3]==0
    assert pixels[60,20,3]==255


def test_transparent_dark_pixels_do_not_become_ink(tmp_path):
    path,im=sample(tmp_path);im.putpixel((5,5),(0,0,0,0));im.save(path)
    result,_,_=prepare(path,{'ink_only':True})
    assert result.getpixel((5,5))[3]==0


@pytest.mark.parametrize('options',[{'artwork_type':'portrait'},{'border_style':'satin'},{'refinement_ops':[{}]}])
def test_conflicting_modes_are_explicit(tmp_path,options):
    path,_=sample(tmp_path)
    with pytest.raises(ValueError,match='Black lines only'):prepare(path,dict(options,ink_only=True))


def test_line_vectors_not_white_fill_and_no_stale_normal_plan(tmp_path):
    path,_=sample(tmp_path);im,_,_=prepare(path,{'ink_only':True})
    array=np.asarray(im);root=ET.Element('svg')
    assert add_running_paths(root,array[:,:,:3],array[:,:,3]>0)>0
    assert all('#ffffff' not in element.attrib['style'] for element in root)
    assert any('fill:none;stroke:#000000' in element.attrib['style'] for element in root)
    assert not equivalent({'ink_only':True},{})
    assert equivalent({'ink_only':False},{})
