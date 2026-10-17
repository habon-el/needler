import pytest
import pyembroidery as emb
from embroiderly.thread_variants import recolour_plan

def test_excluded_colour_does_not_create_crossing():
    p={'colors':['#000000','#ff0000'],'steps':[
        dict(x=1,y=0,t='stitch',color='#000000'),
        dict(x=20,y=0,t='stitch',color='#ff0000'),
        dict(x=21,y=0,t='stitch',color='#000000')]}
    choices={'#000000':dict(include=True,thread='#00ff00'),'#ff0000':dict(include=False,thread='#ff0000')}
    result=recolour_plan(p,choices)
    assert [t.hex_color() for t in result.threadlist]==['#00ff00']
    sew=[s for s in result.stitches if s[2]==emb.STITCH]
    assert [s[0] for s in sew]==[10,210]
    i=result.stitches.index(sew[-1]);assert result.stitches[i-1][:3]==[200,0,emb.JUMP]
    choices['#000000']['include']=False
    with pytest.raises(ValueError):recolour_plan(p,choices)

def test_bad_thread_choices():
    with pytest.raises(ValueError):recolour_plan({'colors':['#000000']},{})
