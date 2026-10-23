"""Needler's satin embroidery fonts generated from bundled TrueType outlines."""
import pytest
from embroiderly import lettering_native as native
from embroiderly.embroidery_fonts import FONTS, catalogue, layout
from embroiderly.lettering_geometry import outline


def test_catalogue_lists_bundled_fonts_with_licences():
    fonts = catalogue()
    assert set(fonts) == set(FONTS)
    for font in fonts.values():
        assert {'A', 'z', '0', '&', 'é'} <= set(font['glyphs'])


def test_layout_is_satin_columns_grouped_by_glyph():
    svg = layout('Hi!', 'small_font', 125, 'center')
    assert svg.count('letter-group="glyph"') == 3
    shape, envelope, columns = outline(svg)
    assert columns >= 3 and envelope.area > shape.area


@pytest.mark.parametrize('key', sorted(FONTS))
@pytest.mark.parametrize('text,height', [('Hello World', 5), ('Baby 0689', 4), ('Café & Co.', 8)])
def test_words_pass_every_release_check(tmp_path, key, text, height):
    # Each font allows its own heights for these words (thin scripts start larger): stay inside them.
    from embroiderly.small_lettering import fonts, height_range
    low, high = height_range(text, fonts()[key])
    height = min(max(float(height), low), high)
    result = native.build(tmp_path, dict(text=text, font=key, height_mm=height, align='center',
                                         available_width_mm=400.0, colour='#202020'))
    assert result['checks_passed'], result['message']
    report = result['reports']['dst']
    assert report['short'] == report['long'] == report['crossings'] == report['missing_columns'] == 0
