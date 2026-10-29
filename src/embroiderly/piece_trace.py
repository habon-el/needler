"""Auto trace and magic wand: artwork regions become clean vector outlines.

Auto trace replaces the selected pieces (the artwork's colour areas, as preparation found them, or
one thread's areas) by curves fitted to their pixel outlines: corners stay sharp, the stair-steps
between them become smooth curves, specks of holes are closed, and the area is kept. It is stored
like Smooth (piece_weld.replace), so style, direction, holes and outline stay with the piece.

The magic wand selects the connected region of similar colour under a click in the artwork itself
(before colour reduction), measured in the same Lab colour space preparation uses, and adds it as a
new piece in the nearest thread already in the design, traced the same way.
"""
import hashlib
import math
import re

import cv2
import numpy as np

CORNER_DEG = 50        # a bend sharper than this, seen over CORNER_PX pixels each side, stays a corner
CORNER_PX = 1.5
SIGMA_PX = 1.2         # the curves between corners follow the outline averaged over about this many pixels
SIGMA_MM = .15         # ...but never less than this
MIN_HOLE_MM2 = 1.      # smaller holes are specks and are closed
TOLERANCE = (1, 60)    # wand: colour difference (Lab, about ΔE) from the clicked colour
DEFAULT_TOLERANCE = 12
MOST_OF_PICTURE = .9   # a wand region covering more of the picture than this is refused


def run(updated, report, selected, value):
    """Auto trace the selected pieces; pieces already clean are left as they are."""
    from .piece_layout import edits
    from .piece_weld import ALREADY_MM, pixel_mm, replace, shape_of
    if value is not None:
        raise ValueError('Invalid auto trace.')
    if any(p.get('line') for p in selected):
        raise ValueError('A stitched line is already a vector line. Choose filled parts to trace.')
    changed = 0
    for p in selected:
        shape = shape_of(p)
        result = traced(shape, pixel_mm(report, updated, p))
        if result.hausdorff_distance(shape) < ALREADY_MM and len(result.interiors) == len(shape.interiors):
            continue
        replace(updated, report, p, result, f"trace:{p['id']}", p['name'])
        changed += 1
    if not changed:
        raise ValueError('These pieces are already clean outlines.')
    edits(updated)
    return updated


def traced(shape, pixel):
    """Fit smooth curves between the corners of each ring of shape (mm); pixel is mm per pixel."""
    from shapely import affinity
    from shapely.geometry import Polygon
    step = max(.03, pixel/2)
    rings, kept = [], []
    for i, ring in enumerate((shape.exterior, *shape.interiors)):
        if i and Polygon(ring).area < MIN_HOLE_MM2:
            continue
        kept.append(ring)
        fitted = fit(resampled(np.asarray(ring.coords[:-1], float), step), step, pixel)
        if len(fitted) >= 3:
            rings.append(fitted)
    if not rings:
        raise ValueError('This piece is too small to trace.')
    result = Polygon(rings[0], rings[1:]).buffer(0)
    result = max(getattr(result, 'geoms', [result]), key=lambda g: g.area)
    if result.is_empty or result.area < 1.0:
        raise ValueError('This piece is too small to trace.')
    # Curves cut inside bends a little; scale back to the area of the outline traced (specks closed).
    k = math.sqrt(Polygon(kept[0], kept[1:]).area/result.area)
    result = affinity.scale(result, k, k, origin=result.centroid)
    return result.simplify(max(.02, pixel/10), preserve_topology=True)


def resampled(points, step):
    """The closed ring with points every step along it."""
    closed = np.vstack([points, points[:1]])
    length = np.r_[0, np.cumsum(np.linalg.norm(np.diff(closed, axis=0), axis=1))]
    n = max(8, int(length[-1]/step))
    at = np.linspace(0, length[-1], n, endpoint=False)
    return np.c_[np.interp(at, length, closed[:, 0]), np.interp(at, length, closed[:, 1])]


def fit(points, step, pixel):
    """Smooth the stretches between corners (Gaussian along the ring); corners stay where they are."""
    from scipy.ndimage import gaussian_filter1d
    n = len(points)
    k = max(2, int(round(CORNER_PX*pixel/step)))
    if n < 4*k+3:
        return points

    def bend(k):
        a, b = points-np.roll(points, k, axis=0), np.roll(points, -k, axis=0)-points
        return np.degrees(np.abs(np.arctan2(a[:, 0]*b[:, 1]-a[:, 1]*b[:, 0], (a*b).sum(axis=1))))
    # A real corner bends as sharply seen from twice as far; a pixel step does not.
    turn = np.minimum(bend(k), bend(2*k))
    window = np.max([np.roll(turn, s) for s in range(-k, k+1)], axis=0)
    corners = np.flatnonzero((turn > CORNER_DEG) & (turn >= window))
    # One corner per bend: neighbours with the same turn count once.
    corners = [c for i, c in enumerate(corners) if not i or c-corners[i-1] > k]
    if len(corners) > 1 and corners[0]+n-corners[-1] <= k:
        corners.pop()
    sigma = max(SIGMA_MM, SIGMA_PX*pixel)/step
    if not corners:
        return gaussian_filter1d(points, sigma, axis=0, mode='wrap')
    out = np.empty_like(points)
    for start, end in zip(corners, corners[1:]+[corners[0]+n]):
        index = np.arange(start, end+1) % n
        stretch = gaussian_filter1d(points[index], min(sigma, (end-start)/4), axis=0, mode='nearest') \
            if end-start > 2 else points[index].copy()
        # Ease back to the corners, so they keep their place.
        ease = np.minimum(1, np.minimum(np.arange(len(index)), np.arange(len(index))[::-1])/max(1., sigma))[:, None]
        out[index[:-1]] = (points[index]*(1-ease)+stretch*ease)[:-1]
    return out


def magic_wand(updated, report, image, value):
    """The region of similar colour connected to the click becomes a new piece.
    value: {point (mm on the hoop), tolerance (Lab difference, TOLERANCE)}."""
    from shapely.geometry import Polygon
    from skimage.color import rgb2lab
    from .piece_layout import edits
    if not isinstance(value, dict) or set(value) != {'point', 'tolerance'}:
        raise ValueError('Click on the artwork to select a colour.')
    point, tolerance = value['point'], value['tolerance']
    if not isinstance(point, list) or len(point) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in point):
        raise ValueError('Click on the artwork to select a colour.')
    if type(tolerance) not in (int, float) or not math.isfinite(tolerance) or not TOLERANCE[0] <= tolerance <= TOLERANCE[1]:
        raise ValueError(f'Tolerance must be {TOLERANCE[0]}–{TOLERANCE[1]}.')
    rgba = np.asarray(image)
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError('The magic wand needs the artwork.')
    scale = report['scale']
    x, y = ((np.asarray(point, float)+np.array(report['origin_mm']))/scale).round().astype(int)
    height, width = rgba.shape[:2]
    if not (0 <= x < width and 0 <= y < height) or rgba[y, x, 3] <= 127:
        raise ValueError('Click on the artwork.')
    lab = rgb2lab(rgba[:, :, :3]/255)
    opaque = rgba[:, :, 3] > 127
    # The clicked colour: the median of the artwork around the click, so one noisy pixel does not decide.
    near = (slice(max(0, y-2), y+3), slice(max(0, x-2), x+3))
    seed = np.median(lab[near][opaque[near]], axis=0)
    similar = (np.linalg.norm(lab-seed, axis=2) <= tolerance) & opaque
    _, labels = cv2.connectedComponents(similar.astype(np.uint8), connectivity=4)
    region = (labels == labels[y, x]).astype(np.uint8)
    if region.sum() > MOST_OF_PICTURE*width*height:
        raise ValueError('This selects nearly the whole picture. Lower the tolerance.')
    # Anti-aliased hairs along the edge are not part of the region.
    region = cv2.morphologyEx(region, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    if not region[y, x]:
        raise ValueError('This spot is too thin to select. Click inside a larger area, or raise the tolerance.')
    count, labels = cv2.connectedComponents(region, connectivity=4)
    region = (labels == labels[y, x]).astype(np.uint8)
    contours, hierarchy = cv2.findContours(region, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    outer = max((i for i in range(len(contours)) if hierarchy[0, i, 3] == -1), key=lambda i: cv2.contourArea(contours[i]))
    rings = [contours[outer]]
    child = hierarchy[0, outer, 2]
    while child != -1:
        rings.append(contours[child])
        child = hierarchy[0, child, 0]
    origin = np.array(report['origin_mm'])
    rings_mm = [r[:, 0, :].astype(float)*scale-origin for r in rings if len(r) >= 3]
    if len(rings_mm[0]) < 3 or Polygon(rings_mm[0]).area < 1.0:
        raise ValueError('This area is too small to stitch. Select at least 1 mm², or raise the tolerance.')
    shape = Polygon(rings_mm[0], rings_mm[1:]).buffer(0)
    shape = max(getattr(shape, 'geoms', [shape]), key=lambda g: g.area)
    shape = traced(shape, scale)
    colour = nearest_thread(rgba[:, :, :3][region > 0].mean(axis=0), report)
    stored_rings = [[[round(px, 2), round(py, 2)] for px, py in ((np.asarray(r.coords[:-1])+origin)/scale).tolist()]
                    for r in (shape.exterior, *shape.interiors)]
    stored = updated.setdefault('piece_edits', {})
    n = 0
    while True:
        key = hashlib.sha256(f'wand:{stored_rings[0]}:{n}'.encode()).hexdigest()[:20]
        if key not in stored:
            break
        n += 1
    count = sum(item.get('name', '').startswith('Wand ') for item in stored.values())+1
    stored[key] = {'drawn': colour, 'rings': stored_rings, 'name': f'Wand {count}'}
    edits(updated)
    return updated


def nearest_thread(rgb, report):
    """The design's thread closest to rgb (Lab); the region's own colour when the design has none."""
    from skimage.color import rgb2lab
    threads = sorted({p['colour'].lower() for p in report['pieces'] if not p.get('line')
                      and re.fullmatch('#[0-9a-fA-F]{6}', p['colour'])})
    own = '#%02x%02x%02x' % tuple(int(round(v)) for v in rgb)
    if not threads:
        return own
    target = rgb2lab(np.asarray(rgb, float)[None, None]/255)[0, 0]
    labs = rgb2lab(np.array([[[int(t[i:i+2], 16) for i in (1, 3, 5)] for t in threads]], float)/255)[0]
    return threads[int(np.argmin(np.linalg.norm(labs-target, axis=1)))]
