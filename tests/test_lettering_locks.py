import xml.etree.ElementTree as ET
from embroiderly.lettering_locks import explicit_locks, LOCK_PATH
from embroiderly.lettering_geometry import SVG, INK
from embroiderly.lettering_source import route_font
from test_lettering_native import FONT_SVG


def test_lock_retry_changes_only_known_lock_attributes_not_letter_geometry():
    source, _ = route_font(FONT_SVG)
    altered, count = explicit_locks(source)
    assert count == 4
    before = list(ET.fromstring(source).iter(SVG+'path'))
    after = list(ET.fromstring(altered).iter(SVG+'path'))
    allowed = {INK+'lock_custom_'+end for end in ['start','end']} | {
        INK+'lock_'+end+'_scale_percent' for end in ['start','end']}
    for a, b in zip(before, after):
        assert {k:v for k,v in a.attrib.items() if k not in allowed} == {
            k:v for k,v in b.attrib.items() if k not in allowed}
        assert b.get(INK+'lock_custom_start') == LOCK_PATH
    assert explicit_locks(altered) == (altered, 0)


def test_unrecognized_font_lock_settings_are_not_rewritten():
    source, _ = route_font(FONT_SVG)
    source = source.replace('1 -1 1 -1', 'different custom lock')
    altered, count = explicit_locks(source)
    assert count == 0
    assert 'different custom lock' in altered
