import xml.etree.ElementTree as ET
import pytest
from PIL import Image, ImageDraw
from embroiderly import engine


def test_generated_svg_is_versioned_before_unattended_export(tmp_path,monkeypatch):
    path=tmp_path/'source.png'
    image=Image.new('RGB',(40,40),'white')
    ImageDraw.Draw(image).rectangle((10,10,30,30),fill='black')
    image.save(path)
    monkeypatch.setattr('embroiderly.engine_cache.cache_key',lambda *args:'test')
    monkeypatch.setattr('embroiderly.engine_cache.lookup',lambda *args:None)
    monkeypatch.setattr('embroiderly.thread_recolour.reuse',lambda *args:None)
    class ExportReached(Exception):pass
    def inspect(svg):
        root=ET.parse(svg).getroot()
        assert root.find('.//{http://inkstitch.org/namespace}inkstitch_svg_version').text=='3'
        raise ExportReached
    monkeypatch.setattr(engine,'generate_plan',inspect)
    with pytest.raises(ExportReached):engine.digitize(path,tmp_path/'output')
