import xml.etree.ElementTree as ET
import numpy as np
import pytest
from embroiderly.ink_lines import add_running_paths, line_settings
from embroiderly.saved_plans import equivalent


@pytest.mark.parametrize('options', [
    {'ink_length_mm':0}, {'ink_length_mm':float('nan')},
    {'ink_length_mm':float('inf')}, {'ink_length_mm':'2'},
    {'ink_length_mm':True}, {'ink_length_mm':5},
    {'ink_bean_repeats':3}, {'ink_bean_repeats':True},
])
def test_invalid_line_settings(options):
    with pytest.raises(ValueError):line_settings(options)


def test_defaults_preserve_previous_geometry_and_cache():
    assert line_settings({}) == (2,0)
    assert equivalent({}, {'ink_length_mm':2,'ink_bean_repeats':0})
    assert not equivalent({'ink_only':True}, {'ink_only':True,'ink_bean_repeats':1})
    assert not equivalent({'ink_only':True}, {'ink_only':True,'ink_length_mm':1})


def test_real_engine_attributes_and_unchanged_line_coordinates():
    rgb=np.full((50,50,3),255,dtype=np.uint8)
    alpha=np.zeros((50,50),bool);alpha[25,5:45]=True
    normal=ET.Element('svg');bean=ET.Element('svg')
    add_running_paths(normal,rgb,alpha)
    add_running_paths(bean,rgb,alpha,{'ink_length_mm':1.2,'ink_bean_repeats':1})
    assert [p.get('d') for p in normal] == [p.get('d') for p in bean]
    ns='{http://inkstitch.org/namespace}'
    assert all(p.get(ns+'bean_stitch_repeats')=='1' for p in bean)
    assert all(p.get(ns+'running_stitch_length_mm')=='1.2' for p in bean)
    assert all(p.get(ns+'bean_stitch_repeats') is None for p in normal)
