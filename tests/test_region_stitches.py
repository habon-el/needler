import xml.etree.ElementTree as ET
import numpy as np
import pytest
from embroiderly.region_stitches import regions, inventory, assignments, apply_style, satin_rails, NS


def sample():
    rgb=np.zeros((100,100,3),np.uint8);alpha=np.zeros((100,100),bool)
    alpha[10:80,10:30]=True;alpha[10:80,60:80]=True
    return rgb,alpha


def test_same_colour_areas_are_independent_and_ids_survive_recolour():
    rgb,alpha=sample();items=list(regions(rgb,alpha));assert len(items)==2
    rgb[alpha]=[200,50,50]
    assert {i[0] for i in items}=={i[0] for i in regions(rgb,alpha)}
    selected={items[0][0]:'contour'}
    report=inventory(rgb,alpha,.1,{'region_styles':selected})
    assert sorted(r['style'] for r in report['areas'])==['contour','tatami']
    assert not report['stale']
    alpha[10:80,10:30]=False
    assert len(inventory(rgb,alpha,.1,{'region_styles':{i[0]:'contour' for i in items}})['stale'])==1


@pytest.mark.parametrize('styles',[[],{'bad':'tatami'},{'a'*20:'fake'},{'a'*20:None}])
def test_invalid_styles_rejected(styles):
    with pytest.raises(ValueError):assignments({'region_styles':styles})


@pytest.mark.parametrize('kind',['tatami','satin','raised_satin','motif','embossed','ripple','contour','cross','stipple','wave'])
def test_all_styles_produce_real_distinct_svg_configuration(kind):
    rgb,alpha=sample();_,_,rings=next(regions(rgb,alpha))
    root=ET.Element('svg');node=ET.SubElement(root,'path',id='test',d='original',style='fill:#123456;fill-rule:evenodd;stroke:none')
    apply_style(root,node,rings,.1,kind)
    if kind=='tatami':assert node.get('d')=='original'
    elif kind in ('satin','raised_satin'):
        assert node.get(NS+'satin_column')=='true'
        assert len(root)==(3 if kind=='raised_satin' else 1)
    elif kind in ('contour','ripple','stipple'):assert node.get(NS+'fill_method')
    elif kind=='wave':assert node.get(NS+'fill_method')=='wave_fill' and node.get(NS+'angle')
    else:
        assert root[-1].get(NS+'stroke_method')=='running_stitch'
        assert '#123456' in root[-1].get('style')
        assert len(root)==(2 if kind=='embossed' else 1)


def test_satin_rejects_wide_shapes_and_holes():
    rgb,alpha=sample();_,_,rings=next(regions(rgb,alpha))
    with pytest.raises(ValueError):satin_rails(rings,1)
    alpha[30:50,15:25]=False
    rings=next(r for _,_,r in regions(rgb,alpha) if len(r)>1)
    with pytest.raises(ValueError):satin_rails(rings,.1)


def test_ink_and_portrait_do_not_silently_use_area_fill_assignments():
    rgb,alpha=sample()
    for options in ({'ink_only':True},{'artwork_type':'portrait'}):
        assert not inventory(rgb,alpha,.1,options)['areas']


def test_svg_version_metadata_does_not_disable_safe_recolour(tmp_path):
    from embroiderly.thread_recolour import colour_mapping
    a=tmp_path/'a.svg';b=tmp_path/'b.svg'
    text='<svg><metadata><version>3</version></metadata><path d="M0,0L3,3" style="fill:#112233;stroke:none"/></svg>'
    a.write_text(text);b.write_text(text.replace('#112233','#223344'))
    assert colour_mapping(a,b)=={'#112233':'#223344'}
    b.write_text(text.replace('<version>3','<version>4'))
    assert colour_mapping(a,b) is None
