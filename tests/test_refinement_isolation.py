import numpy as np
from PIL import Image,ImageDraw
from embroiderly.refinement import make_operation,replay


def test_point_split_does_not_change_disconnected_same_colour_in_patch():
    source=Image.new('RGBA',(80,40),'#c8a080');draw=ImageDraw.Draw(source)
    draw.rectangle((10,10,20,20),fill='#604030')
    draw.rectangle((50,10,60,20),fill='#604030')
    prepared=Image.new('RGBA',source.size,'#c8a080')
    patch=dict(bounds=[0,0,80,40],point=[15,15],remedies=['split-region'],diagnosis='colour-merge')
    op,_=make_operation(source,prepared,patch,'split-region',{})
    result,history=replay(source,prepared,[op]);pixels=np.array(result)
    assert tuple(pixels[15,15,:3])==(96,64,48)
    assert np.array_equal(pixels[10:21,50:61],np.array(prepared)[10:21,50:61])
    assert history[0]['changed_pixels']==121
