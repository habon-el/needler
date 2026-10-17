import xml.etree.ElementTree as ET
import numpy as np
from embroiderly.region_stitches import decorative_paths, apply_style


def test_point_touching_lobes_can_be_decorated_without_dropping_either():
    ring=np.array([[0,0],[8,0],[8,8],[16,8],[16,16],[8,16],[8,8],[0,8]],dtype=np.int32).reshape(-1,1,2)
    path=decorative_paths([ring],1,'embossed')
    assert path and '16.' in path


def test_tiny_embossed_area_keeps_base_without_empty_overlay():
    ring=np.array([[0,0],[1,0],[1,1],[0,1]],dtype=np.int32).reshape(-1,1,2)
    root=ET.Element('svg');node=ET.SubElement(root,'path',id='small',d='original',style='fill:#123456;stroke:none')
    apply_style(root,node,[ring],.1,'embossed')
    assert len(root)==1 and node.get('d')=='original'
