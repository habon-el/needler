import xml.etree.ElementTree as ET
import pytest
from embroiderly.lettering_rebuild import prepare, NS, SVG


def test_minimum_applied_without_changing_letter_geometry_or_font_settings():
    original = '<svg xmlns="http://www.w3.org/2000/svg" xmlns:i="http://inkstitch.org/namespace"><metadata><i:min_stitch_len_mm>0.1</i:min_stitch_len_mm></metadata><path d="M 0,0 L 3,4" i:satin_column="true" i:zigzag_spacing_mm="0.4" i:center_walk_underlay="true"/></svg>'
    result, count = prepare(original)
    root = ET.fromstring(result)
    assert count == 1
    assert len(root.findall('.//'+NS+'min_stitch_len_mm')) == 1
    assert root.find('.//'+NS+'min_stitch_len_mm').text == '0.45'
    path = root.find(SVG+'path')
    assert path.get('d') == 'M 0,0 L 3,4'
    assert path.get(NS+'min_stitch_length_mm') == '0.45'
    assert path.get(NS+'zigzag_spacing_mm') == '0.4'
    assert path.get(NS+'center_walk_underlay') == 'true'
    again, _ = prepare(result)
    assert again == result


def test_empty_font_geometry_is_refused():
    with pytest.raises(ValueError, match='no letter paths'):
        prepare('<svg xmlns="http://www.w3.org/2000/svg"/>')
