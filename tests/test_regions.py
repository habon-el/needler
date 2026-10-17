from pathlib import Path

from PIL import Image, ImageDraw

from embroiderly.regions import analyze_image, recommend
from embroiderly.simulation import audit_preview_coverage, create_preview


def test_simple_flat_art_extracts_stable_regions(tmp_path: Path) -> None:
    image = Image.new("RGB", (80, 40), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((5, 5, 25, 30), fill="red")
    draw.rectangle((50, 5, 70, 30), fill="blue")
    path = tmp_path / "art.png"
    image.save(path)
    first = analyze_image(path)
    second = analyze_image(path)
    assert first == second
    assert not first.rejected
    assert len(first.palette) == 3
    assert len(first.regions) == 3
    assert recommend(first.regions[0], first.estimated_dpi).stitch_type == "fill"
    preview = create_preview(path, first, {region.id: {"stitch_type": "fill"} for region in first.regions})
    assert preview and any(segment.kind == "sewn" for segment in preview)


def test_black_line_art_preserves_white_as_fabric(tmp_path: Path) -> None:
    image = Image.new("RGB", (100, 100), "white")
    ImageDraw.Draw(image).rectangle((20, 20, 80, 80), outline="black", width=2)
    path = tmp_path / "line.png"
    image.save(path)
    analysis = analyze_image(path)
    assert analysis.line_art_mode
    white = next(region for region in analysis.regions if min(region.rgb) > 210)
    assert recommend(white, analysis.estimated_dpi, analysis.line_art_mode).stitch_type == "none"


def test_black_line_art_preview_follows_more_than_a_bbox_axis(tmp_path: Path) -> None:
    image = Image.new("RGB", (100, 100), "white")
    drawing = ImageDraw.Draw(image)
    drawing.line([(15, 80), (50, 20), (85, 80)], fill="black", width=3)
    path = tmp_path / "v.png"
    image.save(path)
    analysis = analyze_image(path)
    preview = create_preview(path, analysis, {})
    assert all(segment.colour == "#000000" for segment in preview)
    assert len({point for segment in preview for point in segment.points}) > 10
    audit = audit_preview_coverage(path, preview)
    assert audit.coverage_percent > 90
