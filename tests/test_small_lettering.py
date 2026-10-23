import pytest
from embroiderly.small_lettering import validate


@pytest.mark.parametrize('text',['Hello World','tiny','Baby 0689','romans 12:12 NLT'])
@pytest.mark.parametrize('height',[6,8,12])
def test_small_font_accepts_words_without_image_filters(text,height):
    from embroiderly.embroidery_fonts import text_metrics
    actual,font,scale,align=validate(dict(text=text,font='small_font',height_mm=height))
    stitched=text_metrics(text,'small_font')['height']*font['size']*scale/100+2*font['pull_mm']
    assert actual==text and abs(stitched-height)<.01


def test_missing_glyph_never_silently_replaced():
    with pytest.raises(ValueError,match='does not contain'):
        validate(dict(text='Hello 🦉',font='small_font',height_mm=5))


def test_size_below_installed_font_range_rejected_honestly():
    with pytest.raises(ValueError,match='Choose a height from'):
        validate(dict(text='tiny',font='small_font',height_mm=2))
