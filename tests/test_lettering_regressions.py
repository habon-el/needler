"""Lettering cases that failed the export checks before (2026-10-22 test matrix)."""
import pytest

from embroiderly import lettering_native as ln


CASES = [
    # 3D puff: a slanted column end sent the cap into the bowl of the b.
    ('habonaxel', 'small_font', 23, True),  # stitched height; these words allow 22–24.1 mm
    # 3D puff: stitches 6.98 mm long rounded to 7.02 mm on the machine grid.
    ('h', 'small_font', 22, True),
    # 3D puff: the stitch between fanned satin stitches was over 7 mm.
    ('D', 'small_font', 22, True),
    # 3D puff: the tack-down line sewed straight from the stem to the dot.
    ('j', 'small_font', 22, True),
    # Travel through the unsewn notch where two strokes meet.
    ('6', 'small_font', 22, True),
    ('HABONIMANA', 'lato_black', 15, False),
    # A connecting stitch across a notch: the safety net cuts it.
    ('9', 'small_font', 10, False),
]


@pytest.mark.parametrize('text,font,height,puff', CASES)
def test_lettering_passes_checks(tmp_path, text, font, height, puff):
    body = dict(text=text, font=font, height_mm=height, align='center', available_width_mm=400, colour='#202020')
    if puff:
        body.update(puff=True, puff_foam_mm=3.0)
    result = ln.build(tmp_path, ln.recipe(body))
    assert result['issues'] == {'pes': [], 'dst': []}
    assert result['checks_passed']


@pytest.mark.parametrize('text,font,height', [('HAB', 'small_font', 60), ('ABC', 'bungee', 60), ('DOQ', 'alfa_slab_one', 20)])
def test_big_letters_are_tatami_fill_at_the_height_asked(tmp_path, text, font, height):
    # Above the satin range letters are sewn as fill, not refused (2026-10-22). Since
    # 2026-10-25 that range includes split satin up to 12 mm strokes (test_wide_lettering).
    result = ln.build(tmp_path, ln.recipe(dict(text=text, font=font, height_mm=height, align='center',
                                               available_width_mm=400, colour='#202020')))
    assert result['checks_passed'], result['issues']
    assert abs(result['reports']['dst']['height_mm'] - height) <= .2
    assert 'letter_fill' in (tmp_path / 'source.svg').read_text()


def test_jacket_size_letters_use_a_coarser_verifier_grid(tmp_path):
    # 150 mm letters (379 mm wide) were refused by the 0.04 mm verifier raster.
    result = ln.build(tmp_path, ln.recipe(dict(text='TEAM', font='anton', height_mm=150, align='center',
                                               available_width_mm=400, colour='#202020')))
    assert result['checks_passed'], result['issues']
    assert abs(result['reports']['dst']['height_mm'] - 150) <= .2
