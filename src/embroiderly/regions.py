"""Deterministic first-pass raster scope checks and colour-region extraction."""

from __future__ import annotations
from .knowledge_messages import message as knowledge_message

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class Region:
    id: str
    rgb: tuple[int, int, int]
    pixel_area: int
    bounds_px: tuple[int, int, int, int]


@dataclass(frozen=True)
class EmbroideryRecommendation:
    stitch_type: str
    contour: str
    fill: str
    explanation: str


@dataclass(frozen=True)
class ImageAnalysis:
    source: str
    width_px: int
    height_px: int
    estimated_dpi: int
    source_dpi_was_missing: bool
    palette: tuple[tuple[int, int, int], ...]
    regions: tuple[Region, ...]
    rejected: bool
    reasons: tuple[str, ...]
    line_art_mode: bool


def artwork_rgb(image: Image.Image) -> Image.Image:
    """Composite transparent pixels onto the fabric background consistently."""
    rgba = image.convert('RGBA')
    return Image.alpha_composite(Image.new('RGBA', rgba.size, 'white'), rgba).convert('RGB')


def _quantize(image: Image.Image, colors: int) -> np.ndarray:
    import cv2
    from skimage.color import rgb2lab
    pixels = np.array(image.convert('RGB'), dtype=np.uint8)
    pixels[np.all(pixels >= 245, axis=2)] = 255
    pixels = cv2.bilateralFilter(pixels, 5, 12, 3)
    reduced = Image.fromarray(pixels).quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    result = np.array(reduced.convert('RGB'), dtype=np.uint8)
    palette, counts = np.unique(result.reshape(-1, 3), axis=0, return_counts=True)
    lab = rgb2lab(palette[None, :, :].astype(float) / 255)[0]
    order = sorted(range(len(palette)), key=lambda i: (-int(counts[i]), tuple(palette[i])))
    representatives = []
    original = result.copy()
    for i in order:
        matches = [j for j in representatives if np.linalg.norm(lab[i] - lab[j]) <= 6.0]
        if matches:
            j = min(matches, key=lambda j: (float(np.linalg.norm(lab[i]-lab[j])), j))
            result[np.all(original == palette[i], axis=2)] = palette[j]
        else:
            representatives.append(i)
    return result


def _components(mask: np.ndarray, rgb: tuple[int, int, int], offset: int) -> list[Region]:
    """4-connected components, walked in row-major order for stable IDs."""
    height, width = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    result: list[Region] = []
    counter = 0
    for start_y, start_x in zip(*np.where(mask & ~seen)):
        if seen[start_y, start_x]:
            continue
        stack = [(int(start_y), int(start_x))]
        seen[start_y, start_x] = True
        points: list[tuple[int, int]] = []
        while stack:
            y, x = stack.pop()
            points.append((y, x))
            for ny, nx in ((y - 1, x), (y, x - 1), (y, x + 1), (y + 1, x)):
                if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        if len(points) < 4:
            continue
        ys, xs = zip(*points)
        result.append(Region(
            id=f"r{offset + counter:03d}", rgb=rgb, pixel_area=len(points),
            bounds_px=(min(xs), min(ys), max(xs) + 1, max(ys) + 1),
        ))
        counter += 1
    return result


def analyze_image(path: Path, max_colors: int = 6) -> ImageAnalysis:
    with Image.open(path) as opened:
        dpi_info = opened.info.get("dpi")
        dpi = int(round(dpi_info[0])) if dpi_info else 96
        missing_dpi = dpi_info is None
        rgb = artwork_rgb(opened)
        raw = np.asarray(rgb, dtype=np.uint8)
        raw_luminance = raw.mean(axis=2)
        raw_dark_fraction = float(np.mean(raw_luminance < 170))
        raw_bright_fraction = float(np.mean(raw_luminance > 230))
        # Detect before colour reduction: JPEG anti-aliasing otherwise creates
        # several near-white/near-black palette colours from a simple drawing.
        chromatic = (raw.max(axis=2).astype(int) - raw.min(axis=2).astype(int)) > 30
        has_colour = int(chromatic.sum()) >= 4
        line_art_mode = not has_colour and 0 < raw_dark_fraction < 0.15 and raw_bright_fraction > 0.75
        if line_art_mode:
            line = raw_luminance < 170
            array = np.where(line[:, :, None], (0, 0, 0), (255, 255, 255)).astype(np.uint8)
        else:
            array = _quantize(rgb, max_colors)
    palette = tuple(sorted({tuple(int(v) for v in color) for color in array.reshape(-1, 3)}))
    regions: list[Region] = []
    for color in palette:
        mask = np.all(array == color, axis=2)
        regions.extend(_components(mask, color, len(regions)))
    # Photos tend to retain every requested palette colour and many fragmented
    # components after reduction. This is a conservative scope signal, not an
    # attempt to digitise them.
    fragmentation = len(regions) / max(len(palette), 1)
    reasons: list[str] = []
    if fragmentation > 30:
        reasons.append(f"image is too fragmented ({len(regions)} regions across {len(palette)} colours); likely photographic or textured")
    return ImageAnalysis(
        source=path.name, width_px=array.shape[1], height_px=array.shape[0],
        estimated_dpi=dpi, source_dpi_was_missing=missing_dpi, palette=palette,
        regions=tuple(regions), rejected=bool(reasons), reasons=tuple(reasons), line_art_mode=line_art_mode,
    )


def recommend(region: Region, dpi: int, line_art_mode: bool = False) -> EmbroideryRecommendation:
    """Conservative, visible automatic choice; the reviewer can override it."""
    left, top, right, bottom = region.bounds_px
    width_mm = (right - left) * 25.4 / dpi
    height_mm = (bottom - top) * 25.4 / dpi
    narrow = min(width_mm, height_mm)
    long = max(width_mm, height_mm)
    aspect = long / max(narrow, 0.01)
    if line_art_mode and min(region.rgb) > 210:
        return EmbroideryRecommendation("none", "none", "none", knowledge_message('regions.12'))
    if line_art_mode:
        return EmbroideryRecommendation("running", "running", "none", knowledge_message('regions.13'))
    if narrow < 0.8:
        return EmbroideryRecommendation("running", "none", "none", knowledge_message('regions.14'))
    if narrow <= 7.0 and aspect >= 2.5:
        return EmbroideryRecommendation("satin", "none", "none", knowledge_message('regions.15'))
    return EmbroideryRecommendation("fill", "running", "tatami", knowledge_message('regions.11'))
