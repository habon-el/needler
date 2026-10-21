"""Generate a visible, deterministic sew-path preview from current review choices.

This is intentionally a planning preview, not a claim about physical sew-out.
The eventual generator will use the same command model and file audit boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from skimage.morphology import skeletonize

from .regions import ImageAnalysis, Region, _quantize, artwork_rgb


@dataclass(frozen=True)
class PreviewSegment:
    points: tuple[tuple[int, int], ...]
    colour: str
    kind: str  # sewn or jump


@dataclass(frozen=True)
class CoverageAudit:
    dark_pixels: int
    covered_dark_pixels: int
    missed_dark_pixels: int
    missed_components: int
    coverage_percent: float
    missed_mask: np.ndarray


def _region_mask(array: np.ndarray, region: Region) -> np.ndarray:
    """Recover exactly one connected colour component using its stable bounds."""
    matches = np.all(array == region.rgb, axis=2)
    left, top, right, bottom = region.bounds_px
    candidates = np.argwhere(matches[top:bottom, left:right])
    if not len(candidates):
        return np.zeros(matches.shape, dtype=bool)
    sy, sx = candidates[0] + (top, left)
    found = np.zeros(matches.shape, dtype=bool)
    todo = [(int(sy), int(sx))]
    found[sy, sx] = True
    height, width = matches.shape
    while todo:
        y, x = todo.pop()
        for ny, nx in ((y - 1, x), (y, x - 1), (y, x + 1), (y + 1, x)):
            if 0 <= ny < height and 0 <= nx < width and matches[ny, nx] and not found[ny, nx]:
                found[ny, nx] = True
                todo.append((ny, nx))
    return found


def _runs(values: np.ndarray) -> list[tuple[int, int]]:
    indexes = np.flatnonzero(values)
    if not len(indexes):
        return []
    breaks = np.flatnonzero(np.diff(indexes) > 1)
    starts = np.r_[0, breaks + 1]
    ends = np.r_[breaks, len(indexes) - 1]
    return [(int(indexes[a]), int(indexes[b])) for a, b in zip(starts, ends)]


def _fill_segments(mask: np.ndarray, choice: str, colour: str) -> list[PreviewSegment]:
    ys, xs = np.where(mask)
    if not len(xs):
        return []
    vertical = choice == "satin" and (xs.max() - xs.min()) >= (ys.max() - ys.min())
    axis = range(int(xs.min()), int(xs.max()) + 1, 3) if vertical else range(int(ys.min()), int(ys.max()) + 1, 3)
    result: list[PreviewSegment] = []
    backwards = False
    for coordinate in axis:
        spans = _runs(mask[:, coordinate] if vertical else mask[coordinate, :])
        for start, end in spans:
            points = ((coordinate, start), (coordinate, end)) if vertical else ((start, coordinate), (end, coordinate))
            result.append(PreviewSegment(tuple(reversed(points)) if backwards else points, colour, "sewn"))
            backwards = not backwards
    return result


def _running_segment(mask: np.ndarray, colour: str) -> list[PreviewSegment]:
    ys, xs = np.where(mask)
    if not len(xs):
        return []
    if (xs.max() - xs.min()) >= (ys.max() - ys.min()):
        points = ((int(xs.min()), int(np.median(ys))), (int(xs.max()), int(np.median(ys))))
    else:
        points = ((int(np.median(xs)), int(ys.min())), (int(np.median(xs)), int(ys.max())))
    return [PreviewSegment(points, colour, "sewn")]


def _line_art_segments(array: np.ndarray) -> list[PreviewSegment]:
    """Walk each skeleton edge once, giving a black running-stitch preview.

    This follows the actual dark artwork rather than collapsing a component to
    a bounding-box line. It remains a preview path; production generation will
    later add tie-ins, trim policy, and file-grid validation.
    """
    skeleton = skeletonize(np.all(array < 100, axis=2))
    points = sorted((int(y), int(x)) for y, x in np.argwhere(skeleton))
    point_set = set(points)
    neighbours = {
        point: sorted(
            (ny, nx) for ny in range(point[0] - 1, point[0] + 2)
            for nx in range(point[1] - 1, point[1] + 2)
            if (ny, nx) != point and (ny, nx) in point_set
        )
        for point in points
    }
    unused = {tuple(sorted((point, neighbour))) for point in points for neighbour in neighbours[point]}
    result: list[PreviewSegment] = []
    # Line ends and junctions first, then the rest, each in sorted order: the same
    # start the old per-trail full scan chose, without rescanning every pixel per
    # trail (that was quadratic and froze on detailed ink drawings).
    order = [p for p in points if len(neighbours[p]) != 2] + [p for p in points if len(neighbours[p]) == 2]
    cursor = 0
    while unused:
        while not any(tuple(sorted((order[cursor], n))) in unused for n in neighbours[order[cursor]]):
            cursor += 1
        current = order[cursor]
        trail = [current]
        while True:
            next_points = [n for n in neighbours[current] if tuple(sorted((current, n))) in unused]
            if not next_points:
                break
            following = next_points[0]
            unused.remove(tuple(sorted((current, following))))
            trail.append(following)
            current = following
        # Pixel skeletons have a point per pixel. Preserve corners but sample
        # straight runs at roughly a 0.8 mm / 96 DPI preview interval.
        sampled = trail[::3]
        if sampled[-1] != trail[-1]:
            sampled.append(trail[-1])
        if len(sampled) > 1:
            result.append(PreviewSegment(tuple((x, y) for y, x in sampled), "#000000", "sewn"))
    # Compact dots (pupils, punctuation) can collapse to a single skeleton
    # pixel. Cover only residual dark pixels with short row paths; never bridge
    # white gaps. The independent audit retains its original tolerance.
    ink = np.all(array < 100, axis=2)
    painted = np.zeros(ink.shape, dtype=np.uint8)
    for segment in result:
        cv2.polylines(painted, [np.asarray(segment.points, dtype=np.int32)], False, 1, 1)
    residual = ink & (cv2.dilate(painted, np.ones((7, 7), dtype=np.uint8)) == 0)
    for y in range(residual.shape[0]):
        for start, end in _runs(residual[y]):
            result.append(PreviewSegment(((start, y), (end, y)), '#000000', 'sewn'))
    return result


def create_preview(path: Path, analysis: ImageAnalysis, choices: dict[str, dict[str, str]]) -> list[PreviewSegment]:
    with Image.open(path) as image:
        rgb = artwork_rgb(image)
        raw = np.asarray(rgb, dtype=np.uint8)
        if analysis.line_art_mode:
            array = np.where((raw.mean(axis=2) < 170)[:, :, None], (0, 0, 0), (255, 255, 255)).astype(np.uint8)
        else:
            array = _quantize(rgb, 6)
    if analysis.line_art_mode:
        for region in analysis.regions:
            if region.rgb == (0, 0, 0) and choices.get(region.id, {}).get('stitch_type') == 'none':
                array[_region_mask(array, region)] = 255
        return _line_art_segments(array)
    result: list[PreviewSegment] = []
    for region in analysis.regions:
        selected = choices.get(region.id, {})
        stitch = selected.get("stitch_type", "fill")
        if stitch == "none":
            continue
        colour = "#%02x%02x%02x" % region.rgb
        mask = _region_mask(array, region)
        lines = _running_segment(mask, colour) if stitch == "running" else _fill_segments(mask, stitch, colour)
        if result and lines:
            result.append(PreviewSegment((result[-1].points[-1], lines[0].points[0]), "#7c8792", "jump"))
        result.extend(lines)
    return result


def audit_preview_coverage(path: Path, preview: list[PreviewSegment]) -> CoverageAudit:
    """Find source linework not covered by the planned running-stitch path."""
    with Image.open(path) as image:
        raw = np.asarray(artwork_rgb(image), dtype=np.uint8)
    dark = (raw.mean(axis=2) < 170).astype(np.uint8)
    sewn = np.zeros(dark.shape, dtype=np.uint8)
    for segment in preview:
        if segment.kind != "sewn" or len(segment.points) < 2:
            continue
        cv2.polylines(sewn, [np.asarray(segment.points, dtype=np.int32)], False, 1, thickness=1, lineType=cv2.LINE_8)
    # The source line is thicker than a centreline and JPEG creates soft edges;
    # a 3-pixel halo tests whether an ink mark has a nearby planned penetration.
    covered = cv2.dilate(sewn, np.ones((7, 7), dtype=np.uint8))
    missed = (dark == 1) & (covered == 0)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(missed.astype(np.uint8), connectivity=8)
    meaningful = sum(int(stats[index, cv2.CC_STAT_AREA]) >= 8 for index in range(1, count))
    total = int(dark.sum())
    covered_count = int((dark & (covered == 1)).sum())
    return CoverageAudit(
        dark_pixels=total, covered_dark_pixels=covered_count,
        missed_dark_pixels=int(missed.sum()), missed_components=meaningful,
        coverage_percent=100.0 * covered_count / max(total, 1), missed_mask=missed,
    )
