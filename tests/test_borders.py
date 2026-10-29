import numpy as np
import pytest
import xml.etree.ElementTree as ET
from embroiderly.borders import border_plan,add_border,NS

def mask():
    a=np.zeros((100,100),bool);a[20:80,20:80]=True;return a

def test_disabled_and_validation():
    assert border_plan(mask(),100,{}) is None
    for options in [{'border_style':'puff'},{'border_style':'satin','border_width':float('nan')},{'border_style':'satin','border_width':1},{'border_style':'running','border_colour':'bad'}]:
        with pytest.raises(ValueError):border_plan(mask(),100,options)

def test_outer_only_physical_offsets_and_satin_parameters():
    a=mask();a[40:60,40:60]=False
    plans={place:border_plan(a,100,dict(border_style='satin',border_width=2,border_placement=place)) for place in ('inside','center','outside')}
    assert all(len(p['paths'])==1 for p in plans.values())
    assert min(x for x,y in plans['inside']['paths'][0])==21
    assert min(x for x,y in plans['outside']['paths'][0])==19
    doc=ET.Element('svg');add_border(doc,plans['center'])
    assert doc.find('path').get('{'+NS+'}satin_column')=='true'
    assert doc.find('path').get('{'+NS+'}center_walk_underlay')=='true'
    assert doc.find('metadata').find('{'+NS+'}inkstitch_svg_version').text=='3'
    assert len(doc.findall('path'))==2
    assert all(p.get('d').count('M ')==2 and 'Z' not in p.get('d') for p in doc.findall('path'))

def test_no_silent_topology_loss():
    a=np.zeros((100,100),bool);a[49:52,10:90]=True
    with pytest.raises(ValueError):border_plan(a,100,dict(border_style='satin',border_width=6,border_placement='inside'))


def test_line_inside_the_border_is_a_triple_stitch_ring_that_passes_the_gate(tmp_path):
    from pathlib import Path
    from PIL import Image
    from embroiderly.web import create_app
    from embroiderly.release_gate import checked_bytes
    (tmp_path/'work/uploads').mkdir(parents=True)
    rgba=np.zeros((400,400,4),np.uint8);rgba[60:340,60:340]=[40,90,170,255]
    Image.fromarray(rgba).save(tmp_path/'work/uploads/p.png')
    client=create_app(tmp_path).test_client()
    options={'height_mm':80,'count':2,'smooth':0,'border_style':'satin','border_width':3,'border_inner':'triple'}
    body=client.post('/artwork/p.png',json=dict(options=options,subject_confirmed=True,digitize=True)).get_json()
    assert body.get('playback'),body.get('error')
    plan=body['report']['border']
    assert len(plan['inner'])==1
    # The ring sits inside the border's inner edge (half the width plus the gap).
    xs=[x for x,_ in plan['inner'][0]];outer=[x for x,_ in plan['paths'][0]]
    assert (min(xs)-min(outer))*plan['scale']==pytest.approx(1.5+1.2,abs=.4)
    assert checked_bytes(tmp_path/'work'/'inkstitch-preview'/Path(body['prepared_name']).stem,'dst')
    with pytest.raises(ValueError):
        border_plan(np.ones((50,50),bool),50,dict(border_style='satin',border_width=2,border_inner='wavy'))


@pytest.mark.parametrize('placement', ['inside', 'center'])
def test_satin_border_on_the_whole_picture_stays_on_the_canvas(tmp_path, placement):
    # Whole picture stitched: the outline is the canvas edge itself. The satin band
    # must sit inside the canvas, or every edge stitch fails the release gate as a
    # "stitch across a removed area" (seen on a 56 x 100 mm portrait, Oct 2026).
    from pathlib import Path
    from PIL import Image
    from embroiderly.web import create_app
    from embroiderly.release_gate import checked_bytes
    (tmp_path/'work/uploads').mkdir(parents=True)
    # 768 px for 100 mm (0.13 mm a pixel), as in the original failure: a satin's last stitch
    # landing 0.1 mm past its rail is then a whole pixel off the canvas.
    rgb=np.zeros((768,431,3),np.uint8);rgb[:,:215]=[40,40,40];rgb[:,215:]=[96,112,112];rgb[300:470,100:330]=[160,176,168]
    Image.fromarray(rgb).save(tmp_path/'work/uploads/p.png')
    client=create_app(tmp_path).test_client()
    options={'height_mm':100,'count':3,'smooth':0,'selection':'full','border_style':'satin','border_width':4,
             'border_placement':placement,'border_inner':'triple'}
    body=client.post('/artwork/p.png',json=dict(options=options,subject_confirmed=True,digitize=True)).get_json()
    assert body.get('playback'),body.get('error')
    assert checked_bytes(tmp_path/'work'/'inkstitch-preview'/Path(body['prepared_name']).stem,'dst')
    assert any('inside the picture' in w for w in body['report']['border']['warnings'])
