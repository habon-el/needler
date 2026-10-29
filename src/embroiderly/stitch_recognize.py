"""Recognize stitches: a machine file becomes editable pieces.

The file is split into blocks at every colour change, cut and jump. Each block
is read from how its needle moves: a narrow band is a running line (triple when
the needle goes back and forth over it); a band whose stitches turn back at
almost every needle hole is satin; anything else is a fill, and its rows give
the stitch direction. The outline of a fill or satin is the area its thread
covers (stitches drawn one thread wide, small gaps closed, travel lines
opened away). The pieces keep the thread colours and the file's sewing order;
Needler sews them again with its own stitches, so they edit like any piece.
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
JUMP_MM = 2.0         # shorter jumps are sewn through, longer ones start a new block
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
        current, last = [], None
        for x, y, flag in stitches:
            command = flag & emb.COMMAND_MASK
            point = (x / 10, y / 10)
            if command == emb.STITCH:
                if not current and last is not None:
                    current.append(last)
                current.append(point)
            elif command == emb.JUMP and current and math.dist(current[-1], point) < JUMP_MM:
                current.append(point)
            elif command in (emb.JUMP, emb.TRIM, emb.COLOR_CHANGE, emb.STOP, emb.END, emb.COLOR_BREAK):
                if len(current) > 2:
                    blocks.append(dict(colour=colour, points=current))
                current = []
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


def _band(points, low):
    """The area the block's thread covers, on a 0.1 mm grid from `low`."""
    pts = np.rint((np.asarray(points) - low) / RES_MM).astype(np.int32)
    size = pts.max(axis=0) + int(CLOSE_MM / RES_MM) * 2 + 3
    mask = np.zeros((size[1], size[0]), np.uint8)
    cv2.polylines(mask, [pts], False, 1, thickness=max(1, int(round(THREAD_MM / RES_MM))))
    return mask


def _line(points):
    """A running line's path: back-and-forth (triple) stitches folded onto one pass, then simplified;
    and whether it is a triple line (the thread covers the path about three times; tie-offs add little)."""
    from shapely.geometry import LineString
    path = []
    for p in points:
        if len(path) >= 2 and math.dist(p, path[-2]) < .15:
            path.pop()
        elif not path or math.dist(p, path[-1]) >= .05:
            path.append(p)
    if len(path) < 2:
        return None, False
    line = LineString(path)
    sewn = float(np.linalg.norm(np.diff(np.asarray(points), axis=0), axis=1).sum())
    triple = sewn > TRIPLE * line.length
    line = line.simplify(.1)
    return ([list(map(float, c)) for c in line.coords] if line.length >= 2 else None), triple


def pieces(blocks):
    """Each block as pieces: dict(kind fill|satin|line, colour, rings (mm), stitch, angle)."""
    from .region_stitches import satin_reason
    found = []
    disc = lambda mm: cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * int(round(mm / RES_MM / 2)) + 1,) * 2)
    for block in blocks:
        points = block['points']
        low = np.asarray(points).min(axis=0) - CLOSE_MM - RES_MM
        band = _band(points, low)
        area = cv2.morphologyEx(band, cv2.MORPH_CLOSE, disc(CLOSE_MM))
        width = 2 * float(cv2.distanceTransform(area, cv2.DIST_L2, 5).max()) * RES_MM
        turns = _turns(points)
        if width < LINE_MM:
            path, triple = _line(points)
            if path:
                found.append(dict(kind='line', colour=block['colour'], rings=[path],
                                  stitch='triple' if triple else 'running'))
            continue
        # Travel runs inside the block are thinner than any area: open them away.
        area = cv2.morphologyEx(area, cv2.MORPH_OPEN, disc(OPEN_MM))
        contours, hierarchy = cv2.findContours(area, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        satin = turns >= SATIN_TURNS
        angle = None if satin else _direction(points)
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
            found.append(dict(kind=kind, colour=block['colour'], rings=rings,
                              angle=None if kind == 'satin' else angle))
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
    """Read a machine file into a new design: the silhouette as its picture (hidden), and every
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
            # The picture is only the file's silhouette: the recognized pieces are sewn instead.
            stored[p['id']] = dict(visible=False, name='File outline')
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
