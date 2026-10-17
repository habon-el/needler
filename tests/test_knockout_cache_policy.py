import hashlib
import pytest
from embroiderly.engine import digitize, ENGINE
from test_output_safety import circle_image


def test_warm_cold_knockout_circles_identical(tmp_path):
    if not ENGINE.is_file():pytest.skip('Installed stitch engine required')
    normal=tmp_path/'normal.png';selected=tmp_path/'selected.png'
    circle_image(normal);circle_image(selected,knockout=True)
    digitize(normal,tmp_path/'warm'/'normal',6)
    warm=digitize(selected,tmp_path/'warm'/'selected',6)
    cold=digitize(selected,tmp_path/'cold'/'selected',6)
    assert warm['stitch_count']==cold['stitch_count']
    for suffix in ('pes','dst'):
        assert (tmp_path/'warm'/'selected'/('design.'+suffix)).read_bytes()==(tmp_path/'cold'/'selected'/('design.'+suffix)).read_bytes()
