import pytest
from embroiderly.lettering_native import glyph_check
from test_lettering_native import FONT_SVG


def test_missing_punctuation_is_named_instead_of_a_generic_failure():
    with pytest.raises(ValueError, match='Missing:') as error:
        glyph_check(FONT_SVG, 'A;')
    assert "';'" in str(error.value)
    assert 'Nothing was approved' in str(error.value)
