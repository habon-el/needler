import io
import cv2
import numpy as np
from PIL import Image
from verify_lettering_batch import render,CASES
from embroiderly.colour_knockout import propose_background,remove_colour


def test_baby_0689_nine_counters_are_never_silently_filled():
    data,coverage,_=render(CASES[-1]);image=Image.open(io.BytesIO(data))
    rgb=np.asarray(image.convert('RGB'));operation=propose_background(image)
    _,mask,report=remove_colour(rgb,np.ones(coverage.shape,bool),operation,10)
    n,labels,_,_=cv2.connectedComponentsWithStats(np.uint8(coverage<128),8)
    outside=set(np.unique(np.concatenate([labels[0],labels[-1],labels[:,0],labels[:,-1]])))
    holes=[(labels==i)&(coverage<=5) for i in range(1,n) if i not in outside]
    holes=[hole for hole in holes if hole.any()]
    assert len(holes)==9
    assert sum(int((hole&mask).sum()) for hole in holes)==0
    assert report['filled_specks']==0
    assert len([p for p in report['parts'] if p['review_hole']])==9
