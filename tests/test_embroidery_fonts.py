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


def _bare_across_mm(char, word_mm):
    """Widest bare place in a Damion letter with the columns layout sews when
    "habonimana" is word_mm high, and how many gap columns it sews."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from embroiderly import embroidery_fonts as ef
    path = ef.font_path('damion')
    mm = word_mm/0.6650390625  # mm per em: "habonimana" is 0.665 em high
    shape = ef.glyph_columns(path, char)[2]
    sewn = [ef._wedge(c, mm, shape) if added else c for c, wide, added in ef.gap_cover(path, char)
            if wide is None or wide*mm >= ef.GAP_SHOW_MM]
    sewn = [c for c in sewn if c]
    bare = shape.difference(unary_union([Polygon(list(a)+list(b)[::-1]).buffer(0) for a, b, *_ in sewn]))
    return ef._across(bare)*mm, sum(c[2] is None for c in sewn)


def test_script_gaps_the_thread_cannot_hide_are_sewn():
    # Damion "habonimana" 15.8 mm high: each a's foot kept a 0.4 mm bare sliver (2.2% of
    # the letter) that no column reached. Any patch wider than the thread hides is sewn now.
    # (An m's 0.46 mm wedge at 15.8 mm has no room for its ties and stays bare.)
    for word_mm, chars in ((15.8, 'habo'), (25, 'habonim')):
        for char in chars:
            assert _bare_across_mm(char, word_mm)[0] < .4, (char, word_mm)
    # Small words sew the gap columns while their patch shows (they were dropped under
    # 1.5 mm long), and leave out the ones the thread hides.
    assert _bare_across_mm('h', 6)[1] == 2 and _bare_across_mm('a', 4)[1] == 0
