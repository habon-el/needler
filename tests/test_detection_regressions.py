from PIL import Image, ImageDraw
from embroiderly.regions import analyze_image
from embroiderly.simulation import create_preview, audit_preview_coverage


def test_sparse_coloured_logo_keeps_colour(tmp_path):
    image = Image.new('RGB', (100, 100), 'white')
    ImageDraw.Draw(image).rectangle((40, 40, 60, 60), fill='red')
    path = tmp_path / 'colour.png'
    image.save(path)
    analysis = analyze_image(path)
    assert not analysis.line_art_mode
    assert (255, 0, 0) in analysis.palette


def test_transparent_background_is_fabric(tmp_path):
    image = Image.new('RGBA', (100, 100), (0, 0, 0, 0))
    ImageDraw.Draw(image).line((20, 20, 80, 80), fill=(0, 0, 0, 255), width=2)
    path = tmp_path / 'transparent.png'
    image.save(path)
    analysis = analyze_image(path)
    assert analysis.line_art_mode
    assert sum(r.pixel_area for r in analysis.regions if r.rgb == (0, 0, 0)) < 300


def test_isolated_dot_is_not_lost(tmp_path):
    image = Image.new('RGB', (100, 100), 'white')
    ImageDraw.Draw(image).ellipse((45, 45, 55, 55), fill='black')
    path = tmp_path / 'dot.png'
    image.save(path)
    analysis = analyze_image(path)
    preview = create_preview(path, analysis, {})
    assert preview
    assert audit_preview_coverage(path, preview).missed_dark_pixels == 0
