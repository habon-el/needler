"""Recognize stitches: a machine file becomes editable pieces.

The file is split into blocks at every colour change, cut and jump (a run of short
jumps counts as one move). A block may hold several objects of one thread sewn without
a cut: each separate area its thread covers is an object, and the stitches between
areas are travel runs (straight, from one object to the next) or running lines. Each
object is read from how its needle moves: a narrow band is a running line (triple when
the needle goes back and forth over it; tie stitches fold away); an area whose top
stitches turn back at almost every needle hole is satin; anything else is a fill, and
its rows give the stitch direction. Underlay is told apart from the top stitching by
being sewn first and covered by it: only the stitches that still cover the whole area
on their own count. The outline of a fill or satin is the area its thread covers
(stitches drawn one thread wide, small gaps closed, travel lines opened away). The
pieces keep the thread colours and the file's sewing order; Needler sews them again
with its own stitches, so they edit like any piece.
"""
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np
import pyembroidery as emb

FORMATS = ('.dst', '.pes', '.pec', '.jef', '.exp', '.vp3', '.xxx', '.u01', '.hus', '.vip', '.sew')
RES_MM = .1           # outline raster: one pixel per 0.1 mm
THREAD_MM = .4        # each stitch is drawn this wide
CLOSE_MM = 1.0        # gaps between rows and satin stitches up to this close
OPEN_MM = .8          # thinner than this, a band is travel, not area
LINE_MM = 1.2         # a block whose band is narrower than this is a line
SATIN_TURNS = .5      # share of needle holes where the stitch turns back: satin
TRIPLE = 2.2          # a line sewn this many times over its length is a triple line
JUMP_MM = 2.0         # shorter moves by jumps are sewn through, longer ones start a new block
TOP_COVERS = .95      # the top stitching alone covers this share of its area; what comes before is underlay
TURN_DEG = 30         # a running path turning more than this is two runs (travel, then a line)
STRAIGHT = 1.1        # a run no longer than this times its ends' distance is straight (travel)
REACH_MM = .3         # stitches this close to an area belong to it
MARGIN_MM = 2.0       # empty fabric around the design in its picture
PICTURE_PX = 700      # the longest side of the design's picture
MAX_PIECES = 100      # as many as Needler keeps drawn pieces
SILHOUETTE = (200, 200, 200)


def read(path):
    """Blocks of sewn points (mm, y down) with their thread colour, in sewing order."""
    from .machine_files import read_pattern
    path = Path(path)
    if path.suffix.lower() not in FORMATS:
        raise ValueError('Open a machine file: ' + ', '.join(f[1:].upper() for f in FORMATS) + '.')
    try:
        pattern = read_pattern(path)
    except Exception as error:   # pyembroidery raises many kinds on a damaged file
        raise ValueError(f'This machine file could not be read ({error.__class__.__name__}).') from None
    if pattern is None:
        raise ValueError('This machine file could not be read.')
    blocks = []
    for stitches, thread in pattern.get_as_colorblocks():
        colour = '#%06x' % (thread.color & 0xffffff) if thread is not None else '#000000'
        current, last, moved = [], None, None
        for x, y, flag in stitches:
            command = flag & emb.COMMAND_MASK
            point = (x / 10, y / 10)
            if command == emb.STITCH:
                if not current and last is not None:
                    current.append(last)
                elif moved is not None:
                    current.append(moved)   # a short move by jumps is sewn through
                moved = None
                current.append(point)
            elif command == emb.JUMP and current and math.dist(current[-1], point) < JUMP_MM:
                # Measured from the last stitch: a long move is often many short jumps.
                moved = point
            elif command in (emb.JUMP, emb.TRIM, emb.COLOR_CHANGE, emb.STOP, emb.END, emb.COLOR_BREAK):
                if len(current) > 2:
                    blocks.append(dict(colour=colour, points=current))
                current, moved = [], None
            if command in (emb.STITCH, emb.JUMP, emb.TRIM):
                last = point
        if len(current) > 2:
            blocks.append(dict(colour=colour, points=current))
    if not blocks:
        raise ValueError('This machine file has no stitches.')
    return blocks


def _turns(points):
    """Share of needle holes where the stitch turns back (more than 150 degrees)."""
    v = np.diff(np.asarray(points), axis=0)
    v = v[np.linalg.norm(v, axis=1) > .05]
    if len(v) < 2:
        return 0.
    a, b = v[:-1], v[1:]
    cos = (a * b).sum(1) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1))
    return float((cos < -.87).mean())


def _direction(points):
    """Stitch direction in Needler's convention (degrees, rising to the right is positive) from
    the stitches longer than 1 mm; None when there are too few."""
    v = np.diff(np.asarray(points), axis=0)
    length = np.linalg.norm(v, axis=1)
    v, length = v[length > 1], length[length > 1]
    if len(v) < 4:
        return None
    angle = np.arctan2(-v[:, 1], v[:, 0])   # y down on the hoop, so flip it
    mean = np.angle((length * np.exp(2j * angle)).sum()) / 2
    degrees = math.degrees(mean)
    return round((degrees + 90) % 180 - 90, 1)


def _band(points, low, shape=None):
    """The area the block's thread covers, on a 0.1 mm grid from `low`."""
    pts = np.rint((np.asarray(points) - low) / RES_MM).astype(np.int32)
    if shape is None:
        size = pts.max(axis=0) + int(CLOSE_MM / RES_MM) * 2 + 3
        shape = (size[1], size[0])
    mask = np.zeros(shape, np.uint8)
    cv2.polylines(mask, [pts], False, 1, thickness=max(1, int(round(THREAD_MM / RES_MM))))
    return mask


def _line(points):
    """A running line's path: back-and-forth (triple) stitches folded onto one pass, then simplified;
    and whether it is a triple line (the thread covers the path about three times; tie-offs add little)."""
    from shapely.geometry import LineString
    path = _folded(points)[0]
    if len(path) < 2:
        return None, False
    line = LineString(path)
    sewn = float(np.linalg.norm(np.diff(np.asarray(points), axis=0), axis=1).sum())
    triple = sewn > TRIPLE * line.length
    line = line.simplify(.1)
    return ([list(map(float, c)) for c in line.coords] if line.length >= 2 else None), triple


def _folded(points):
    """The path with back-and-forth stitches (tie stitches, triple runs) folded onto one pass, and
    for each of its points the index of the stitch that placed it."""
    path, index = [], []
    for i, p in enumerate(points):
        if len(path) >= 2 and math.dist(p, path[-2]) < .15:
            path.pop(); index.pop()
        elif not path or math.dist(p, path[-1]) >= .05:
            path.append(p); index.append(i)
    return path, index


def _runs(points, before, after):
    """Stitches off every area, between area `before` and area `after` (None: the block's start
    or end), as running lines. The path is split where it turns sharply; a straight stretch
    leaving an area or reaching one is travel, and so is a run from an area back into it."""
    if before is not None and before == after:
        return []
    path, index = _folded(points)
    if len(path) < 2:
        return []
    cuts = [0]
    for i in range(1, len(path) - 1):
        a, b = np.subtract(path[i], path[i - 1]), np.subtract(path[i + 1], path[i])
        if a @ b < math.cos(math.radians(TURN_DEG)) * np.linalg.norm(a) * np.linalg.norm(b):
            cuts.append(i)
    cuts.append(len(path) - 1)
    stretches = list(zip(cuts, cuts[1:]))

    def straight(stretch):
        part = path[stretch[0]:stretch[1] + 1]
        return sum(map(math.dist, part, part[1:])) <= STRAIGHT * math.dist(part[0], part[-1])
    if len(stretches) == 1:
        if before is not None and after is not None and straight(stretches[0]):
            return []
    else:
        if before is not None and straight(stretches[0]):
            stretches = stretches[1:]
        if after is not None and stretches and straight(stretches[-1]):
            stretches = stretches[:-1]
    return [points[index[stretches[0][0]]:index[stretches[-1][1]] + 1]] if stretches else []


def _top(points, area, low):
    """The top stitching of an area: the stitches from the latest start (of 16 tried) that still
    cover TOP_COVERS of it on their own, closed like the area. Underlay comes before them."""
    disc = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * int(round(CLOSE_MM / RES_MM / 2)) + 1,) * 2)
    total, best = cv2.countNonZero(area), 0
    for k in np.linspace(0, .8 * len(points), 17).astype(int)[1:]:
        if len(points) - k < 3:
            break
        covered = cv2.morphologyEx(_band(points[k:], low, area.shape), cv2.MORPH_CLOSE, disc)
        if cv2.countNonZero(covered & area) >= TOP_COVERS * total:
            best = k
    return points[best:]


def pieces(blocks):
    """Each block as pieces: dict(kind fill|satin|line, colour, rings (mm), stitch, angle)."""
    from .region_stitches import satin_reason
    found = []
    disc = lambda mm: cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * int(round(mm / RES_MM / 2)) + 1,) * 2)

    def line(points, colour):
        path, triple = _line(points)
        return [dict(kind='line', colour=colour, rings=[path], stitch='triple' if triple else 'running')] if path else []
    for block in blocks:
        points = block['points']
        low = np.asarray(points).min(axis=0) - CLOSE_MM - RES_MM
        band = _band(points, low)
        area = cv2.morphologyEx(band, cv2.MORPH_CLOSE, disc(CLOSE_MM))
        width = 2 * float(cv2.distanceTransform(area, cv2.DIST_L2, 5).max()) * RES_MM
        if width < LINE_MM:
            found += line(points, block['colour'])
            continue
        # Travel runs inside the block are thinner than any area: open them away. Each area left is
        # one object, with the stitches on it; the stitches between areas are travel or lines.
        area = cv2.morphologyEx(area, cv2.MORPH_OPEN, disc(OPEN_MM))
        count, labels = cv2.connectedComponents(area, connectivity=8)
        reach = cv2.dilate(labels.astype(np.float32), disc(2 * REACH_MM)).astype(int)
        pixel = np.rint((np.asarray(points) - low) / RES_MM).astype(int)
        owner = [int(reach[y, x]) or None for x, y in pixel]
        objects = []   # (first stitch, pieces), put in sewing order at the end
        start = None
        for i, label in enumerate(owner + [None]):
            if i < len(owner) and label is None:
                start = i if start is None else start
                continue
            if start is not None:
                # From the last stitch on the area before, so a run starts where it leaves it.
                run = points[max(0, start - 1):i + 1]
                for part in _runs(run, owner[start - 1] if start else None, label if i < len(owner) else None):
                    objects.append((start, line(part, block['colour'])))
                start = None
        for label in range(1, count):
            own = [p for p, o in zip(points, owner) if o == label]
            component = (labels == label).astype(np.uint8)
            if len(own) < 3:
                continue
            top = _top(own, component, low)
            satin = _turns(top) >= SATIN_TURNS
            angle = None if satin else _direction(top)
            contours, hierarchy = cv2.findContours(component, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
            parts = []
            objects.append((owner.index(label), parts))
            for i, contour in enumerate(contours):
                if hierarchy[0, i, 3] != -1 or cv2.contourArea(contour) * RES_MM ** 2 < 1:
                    continue
                rings = [contour]
                child = hierarchy[0, i, 2]
                while child != -1:
                    if cv2.contourArea(contours[child]) * RES_MM ** 2 >= 1:
                        rings.append(contours[child])
                    child = hierarchy[0, child, 0]
                rings = [(cv2.approxPolyDP(r, 1, True)[:, 0, :] * RES_MM + low).tolist() for r in rings]
                rings = [r for r in rings if len(r) >= 3]
                if not rings:
                    continue
                kind = 'satin' if satin and not satin_reason(rings, 1) else 'fill'
                parts.append(dict(kind=kind, colour=block['colour'], rings=rings,
                                  angle=None if kind == 'satin' else angle))
        for _, parts in sorted(objects, key=lambda item: item[0]):
            found += parts
    if not found:
        raise ValueError('No stitched parts were found in this machine file.')
    if len(found) > MAX_PIECES:
        raise ValueError(f'This machine file has {len(found)} parts; Needler opens files with up to {MAX_PIECES}.')
    return found


def picture(found):
    """The design's silhouette as a transparent picture, and its scale (mm per pixel) and corner (mm)."""
    every = np.concatenate([np.asarray(r, float) for p in found for r in p['rings']])
    low = every.min(axis=0) - MARGIN_MM
    span = every.max(axis=0) + MARGIN_MM - low
    if span[1] > 400 or span[0] > 1000:
        raise ValueError('This machine file is larger than Needler designs (400 mm high).')
    scale = max(span) / PICTURE_PX
    size = np.maximum(np.ceil(span / scale).astype(int), 8)
    rgba = np.zeros((size[1], size[0], 4), np.uint8)
    mask = np.zeros(rgba.shape[:2], np.uint8)
    for p in found:
        rings = [np.rint((np.asarray(r) - low) / scale).astype(np.int32) for r in p['rings']]
        if p['kind'] == 'line':
            cv2.polylines(mask, rings, False, 1, thickness=max(2, int(round(.6 / scale))))
        else:
            cv2.fillPoly(mask, rings, 1)
    rgba[mask > 0] = [*SILHOUETTE, 255]
    return rgba, scale, low


def open_file(path, uploads, decisions):
    """Read a machine file into a new design: the silhouette as its picture (its areas cut), and every
    recognized part as a drawn piece with its colour, style and stitch direction, sewn in the
    file's order. Returns the new picture's name."""
    from PIL import Image
    from uuid import uuid4
    from .piece_layout import edits
    from .preparation import prepare
    found = pieces(read(path))
    rgba, scale, low = picture(found)
    name = uuid4().hex + '.png'
    target = Path(uploads) / name
    Image.fromarray(rgba).save(target)
    options = dict(height_mm=round(rgba.shape[0] * scale, 2), count=2, floor_mm2=0, smooth=0, simplify=0,
                   mask_holes_mm2=0, selection='full')
    try:
        _, _, report = prepare(target, options, Path(decisions) / (name + '.masks'))
        stored = options['piece_edits'] = {}
        for p in report['piece_layout']['pieces']:
            # The picture is only the file's silhouette: its areas are replaced by the recognized
            # pieces (cut, like a knife cut), so they are neither listed nor sewn.
            stored[p['id']] = dict(cut=True)
        styles, angles, order = {}, {}, []
        for n, p in enumerate(found, 1):
            rings = [[[round(x, 2), round(y, 2)] for x, y in ((np.asarray(r) - low) / scale).tolist()] for r in p['rings']]
            key = hashlib.sha256(f'file:{name}:{n}'.encode()).hexdigest()[:20]
            item = dict(drawn=p['colour'], rings=rings, name=f"{dict(fill='Fill', satin='Satin', line='Line')[p['kind']]} {n}")
            if p['kind'] == 'line':
                item['line'] = p['stitch']
            else:
                styles[key] = 'satin' if p['kind'] == 'satin' else 'tatami'
                if p.get('angle') is not None:
                    angles[key] = p['angle']
            stored[key] = item
            order.append(key)
        options.update(region_styles=styles, area_angles=angles, sew_sequence=order)
        edits(options)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    (Path(decisions) / (name + '.preparation.json')).write_text(json.dumps(options, sort_keys=True))
    return name
