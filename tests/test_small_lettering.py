import pytest
from embroiderly.small_lettering import validate


@pytest.mark.parametrize('text',['Hello World','tiny','Baby 0689','romans 12:12 NLT'])
@pytest.mark.parametrize('height',[4,5,6])
def test_small_font_accepts_words_without_image_filters(text,height):
    actual,font,scale,align=validate(dict(text=text,font='small_font',height_mm=height))
    assert actual==text and abs(font['size']*scale/100-height)<.05


def test_missing_glyph_never_silently_replaced():
    with pytest.raises(ValueError,match='does not contain'):
        validate(dict(text='Hello 🦉',font='small_font',height_mm=5))


def test_size_below_installed_font_range_rejected_honestly():
    with pytest.raises(ValueError,match='Choose a font size'):
        validate(dict(text='tiny',font='small_font',height_mm=3))
