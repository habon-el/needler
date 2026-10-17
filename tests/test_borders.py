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
