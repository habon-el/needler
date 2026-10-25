"""Outlines per part: a running, triple or satin line around one chosen part, on its edge
or offset outward from it. Sewn after all fills, so it lies on top. Shared by the colour
generator (engine.py) and the piece path (piece_generation.py); document units are pixels
of `scale` mm."""
import math
import re
import xml.etree.ElementTree as ET

import cv2
import numpy as np

NS = '{http://inkstitch.org/namespace}'
STITCHES = ('running', 'triple', 'satin')
MAX_OFFSET_MM = 6.0


def choices(options):
    """Saved outlines: {part id: {stitch, offset_mm, width_mm, colour}}, checked."""
    value = options.get('area_outlines', {})
    if not isinstance(value, dict) or len(value) > 500:
        raise ValueError('Expected at most 500 part outlines.')
    for key, spec in value.items():
        if not isinstance(key, str) or not re.fullmatch('[a-f0-9]{20}', key) or not isinstance(spec, dict) \
                or set(spec) != {'stitch', 'offset_mm', 'width_mm', 'colour'} or spec['stitch'] not in STITCHES:
            raise ValueError('Invalid part outline. Choose Running, Triple or Satin.')
        for name, low, high in (('offset_mm', 0, MAX_OFFSET_MM), ('width_mm', 1.2, 5)):
            if type(spec[name]) not in (int, float) or not math.isfinite(spec[name]) or not low <= spec[name] <= high:
                raise ValueError(f'Outline gap must be 0–{MAX_OFFSET_MM:g} mm and satin width 1.2–5 mm.')
        if not isinstance(spec['colour'], str) or not re.fullmatch('#[0-9a-fA-F]{6}', spec['colour']):
            raise ValueError('Choose a thread colour for the outline.')
    return value


def reach_mm(spec):
    """How far the outline's stitches reach outside the part."""
    return spec['offset_mm']+(spec['width_mm']/2 if spec['stitch'] == 'satin' else .3)


def in_order(pending):
    """[(rings, spec)] in sewing order: each thread's outlines together (threads in first-seen
    order), and within a thread the nearest outline next, so touching outlines follow each
    other and the generator can travel along them instead of cutting (stitch_engine._branch)."""
    from scipy.spatial import cKDTree
    threads = {}
    for item in pending:
        threads.setdefault(item[1]['colour'].lower(), []).append(item)
    ordered = []
    for group in threads.values():
        points = [np.vstack([np.asarray(r, float).reshape(-1, 2) for r in rings]) for rings, _ in group]
        trees = [cKDTree(p) for p in points]
        left = list(range(1, len(group)))
        here = 0
        ordered.append(group[0])
        while left:
            probe = points[here][::max(1, len(points[here])//64)]
            here = min(left, key=lambda k: float(trees[k].query(probe)[0].min()))
            left.remove(here)
            ordered.append(group[here])
    return ordered


def _path(points):
    return 'M '+' L '.join(f'{x:.3f},{y:.3f}' for x, y in points)


def add(document, rings, spec, scale, mask, index):
    """Add one part's outline (rings: pixel point lists, outer first). Marks the band it sews
    in `mask` (the release mask). Returns how many elements were added."""
    from shapely.geometry import Polygon
    from shapely import segmentize
    shape = Polygon(np.asarray(rings[0], float).reshape(-1, 2),
                    [np.asarray(r, float).reshape(-1, 2) for r in rings[1:] if len(r) >= 3]).buffer(0)
    if spec['offset_mm'] > 0:
        shape = shape.buffer(spec['offset_mm']/scale, join_style='round')
    satin = spec['stitch'] == 'satin'
    radius = spec['width_mm']/2/scale
    polygons = [p for p in getattr(shape, 'geoms', [shape]) if not p.is_empty and p.area*scale*scale >= 1]
    if not polygons:
        raise ValueError('This part is too small for an outline. Choose a smaller gap or another part.')
    count, band = 0, np.zeros(mask.shape, np.uint8)
    for polygon in polygons:
        for ring in (polygon.exterior, *polygon.interiors):
            if satin:
                # Smooth this edge line on its own (as the area it encloses): pixel steps go and
                # every corner is rounded, inward and outward. Satin turns a rounded corner
                # cleanly; a sharp one folds over. A part thinner than the satin is not wiped out.
                c = 2.5*radius
                inside = Polygon(ring).simplify(.15/scale).buffer(c).buffer(-2*c).buffer(c)
                if inside.is_empty:
                    continue
                ring = max(getattr(inside, 'geoms', [inside]), key=lambda g: g.area).exterior
            points = []
            for point in [tuple(p) for p in segmentize(ring, .6/scale).coords][:-1]:
                # Points closer than 0.15 mm give an unsteady direction that folds a satin.
                if not points or math.dist(point, points[-1]) >= .15/scale:
                    points.append(point)
            if len(points) > 3 and math.dist(points[0], points[-1]) < .15/scale:
                points.pop()
            if len(points) < 3:
                continue
            if satin:
                from .borders import satin_rails
                try:
                    halves = satin_rails(points+[points[0]], radius)
                except ValueError:
                    raise ValueError('This outline is too tight for satin here. Choose Running or Triple, '
                                     'a thinner satin or a bigger gap.') from None
                for a, b in halves:
                    node = ET.SubElement(document, 'path', {
                        'id': f'outline{index}-{count}', 'd': _path(a)+' '+_path(b),
                        'style': f"fill:none;stroke:{spec['colour']};stroke-width:1",
                        NS+'satin_column': 'true', NS+'center_walk_underlay': 'true', NS+'zigzag_spacing_mm': '.4'})
                    count += 1
                    rails = np.rint(np.vstack((a, b[::-1]))).astype(np.int32)
                    cv2.fillPoly(band, [rails], 1)
                    cv2.polylines(band, [rails], True, 1, thickness=3)
                node.set(NS+'trim_after', 'true')
            else:
                node = ET.SubElement(document, 'path', {
                    'id': f'outline{index}-{count}', 'd': _path(points+[points[0]]),
                    'style': f"fill:none;stroke:{spec['colour']};stroke-width:{.2/scale}",
                    NS+'stroke_method': 'running_stitch', NS+'trim_after': 'true',
                    NS+'running_stitch_length_mm': '2.2' if spec['stitch'] == 'triple' else '2.5'})
                if spec['stitch'] == 'triple':
                    node.set(NS+'bean_stitch_repeats', '1')
                count += 1
                cv2.polylines(band, [np.rint(np.asarray(points)).astype(np.int32)], True, 1,
                              thickness=max(3, int(math.ceil(.6/scale))+2))
    mask |= band.astype(bool) if mask.dtype == bool else band
    return count
