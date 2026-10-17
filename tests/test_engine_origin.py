import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
import pytest
import pyembroidery as emb
from embroiderly.engine_origin import set_origin
from embroiderly.thread_recolour import colour_mapping


def svg(origin):
    root=ET.Element('svg',xmlns='http://www.w3.org/2000/svg',width='100mm',height='100mm',viewBox='0 0 100 100')
    metadata=ET.SubElement(root,'metadata')
    ET.SubElement(metadata,'{http://inkstitch.org/namespace}inkstitch_svg_version').text='3'
    ET.SubElement(root,'path',d='M 20,20 L 30,20 L 30,30 L 20,30 Z',style='fill:#000000;stroke:none')
    if origin is not None:set_origin(root,origin,1)
    return root


def test_origin_is_part_of_recolour_geometry(tmp_path):
    a,b=tmp_path/'a.svg',tmp_path/'b.svg'
    ET.ElementTree(svg([0,0])).write(a)
    ET.ElementTree(svg([0,0])).write(b)
    assert colour_mapping(a,b)=={'#000000':'#000000'}
    ET.ElementTree(svg([1,0])).write(b)
    assert colour_mapping(a,b) is None


@pytest.mark.skipif(not Path('/opt/inkstitch/bin/inkstitch').exists(),reason='Local engine unavailable')
def test_real_engine_uses_explicit_source_origin(tmp_path):
    # Demonstrate old auto-centering then verify the explicit source-space frame.
    results=[]
    for origin in (None,[0,0]):
        source=tmp_path/'source.svg';ET.ElementTree(svg(origin)).write(source)
        run=subprocess.run(['/opt/inkstitch/bin/inkstitch','--extension=output','--format=json',str(source)],capture_output=True,timeout=60,check=True)
        plan=tmp_path/'plan.json';plan.write_bytes(run.stdout)
        pattern=emb.EmbPattern(str(plan))
        results.append([x/10 for x,y,c in pattern.stitches if c&emb.COMMAND_MASK==emb.STITCH])
    assert min(results[0])<0  # Previous implicit origin is not source coordinates.
    assert 19<=min(results[1])<=21
    assert 29<=max(results[1])<=31
