"""Basting and buttonholes, added to the engine plan after the design's own stitches.

- Basting (`basting`: off, design or hoop): long running stitches round a box, sewn first in
  their own thread so the fabric is held to the backing and the line pulls out easily
  afterwards. `design` is a box BASTE_GAP_MM outside the stitches; `hoop` runs just inside
  the chosen hoop's sewing field (`piece_hoop_mm`), centred on the design as the machine is.
- Buttonholes (`buttonholes`: [{x, y, length_mm, width_mm, angle, colour}], x and y in mm as
  playback shows them): a run along both legs, satin up one leg, a bar tack, satin down the
  other leg and a closing bar tack, sewn last. The gap between the legs is where the slit is cut.

Plan units are 0.1 mm around the design's centre. Both can reach outside the picture, so
`band` gives the pixels they sew for the release check, on a canvas grown by its `pad`."""
import math
import re

import cv2
import numpy as np

BASTINGS = ('off', 'design', 'hoop')
BASTE_COLOUR = '#ff8c1a'
BASTE_GAP_MM = 5.0      # basting box this far outside the design
BASTE_STITCH_MM = 5.0   # long stitches: quick to sew and to pull out
HOOP_INSET_MM = 3.0     # basting this far inside the hoop's sewing field
SLIT_MM = .6            # gap between the legs, where the slit is cut
TACK_MM = 1.2           # bar tack length at each end
MAX_BUTTONHOLES = 40


def _number(value, low, high, message):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) \
            or not low <= value <= high:
        raise ValueError(message)
    return float(value)


def choices(settings):
    """(basting, [buttonhole]) from the saved settings, checked."""
    basting = settings.get('basting', 'off')
    if basting not in BASTINGS:
        raise ValueError('Choose a listed basting: off, around the design or around the hoop.')
    if basting == 'hoop':
        field = settings.get('piece_hoop_mm')
        if not isinstance(field, (list, tuple)) or len(field) != 2:
            raise ValueError('Choose a hoop first, then baste around it.')
        for value in field:
            _number(value, 20, 2000, 'Choose a hoop first, then baste around it.')
    raw = settings.get('buttonholes') or []
    if not isinstance(raw, list) or len(raw) > MAX_BUTTONHOLES:
        raise ValueError(f'At most {MAX_BUTTONHOLES} buttonholes.')
    holes = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError('Invalid buttonhole. Remove it and add it again.')
        colour = item.get('colour')
        if not isinstance(colour, str) or not re.fullmatch('#[0-9a-fA-F]{6}', colour):
            raise ValueError('Choose a thread colour for the buttonhole.')
        holes.append(dict(
            x=_number(item.get('x'), -1000, 1000, 'A buttonhole has an invalid position.'),
            y=_number(item.get('y'), -1000, 1000, 'A buttonhole has an invalid position.'),
            length_mm=_number(item.get('length_mm'), 8, 40, 'Buttonholes are 8–40 mm long.'),
            width_mm=_number(item.get('width_mm', 4), 3, 6, 'Buttonholes are 3–6 mm wide.'),
            angle=_number(item.get('angle', 90), -180, 180, 'A buttonhole angle is −180° to 180°.'),
            colour=colour.lower()))
    return basting, holes


def _along(a, b, step):
    """Points from a to b at most `step` apart (a left out, b included)."""
    n = max(1, math.ceil(math.dist(a, b)/step))
    return [(a[0]+(b[0]-a[0])*k/n, a[1]+(b[1]-a[1])*k/n) for k in range(1, n+1)]


def basting_line(kind, stitches, field, more=()):
    """Closed box of plan points for the basting, or None. `more`: other sewn points
    (buttonholes) the box goes round too."""
    if kind == 'design':
        sewn = np.asarray([s[:2] for s in stitches if s[2] == 'STITCH']+[list(p) for p in more], float)
        left, top = sewn.min(axis=0)-BASTE_GAP_MM*10
        right, bottom = sewn.max(axis=0)+BASTE_GAP_MM*10
    elif kind == 'hoop':
        half = [max(5., v/2-HOOP_INSET_MM)*10 for v in field]
        left, top, right, bottom = -half[0], -half[1], half[0], half[1]
    else:
        return None
    corners = [(left, top), (right, top), (right, bottom), (left, bottom), (left, top)]
    points = [corners[0]]
    for a, b in zip(corners, corners[1:]):
        points += _along(a, b, BASTE_STITCH_MM*10)
    return [(float(x), float(y)) for x, y in points]


def buttonhole_points(hole, centre):
    """One buttonhole's sewn points in plan units around `centre` (plan units), tie-in and
    tie-off included."""
    length, width = hole['length_mm'], hole['width_mm']
    turn = math.radians(hole['angle'])
    along, across = (math.cos(turn), math.sin(turn)), (-math.sin(turn), math.cos(turn))

    def at(u, v):   # mm along and across the buttonhole
        return (centre[0]+(u*along[0]+v*across[0])*10, centre[1]+(u*along[1]+v*across[1])*10)
    half, inner, outer = length/2, SLIT_MM/2, width/2
    low, high = -half+TACK_MM, half-TACK_MM
    middle = (inner+outer)/2

    def satin(u0, u1, v0, v1, spacing):
        steps = max(2, math.ceil(abs(u1-u0)/spacing))
        return [at(u0+(u1-u0)*k/steps, v1 if k % 2 else v0) for k in range(steps+1)]
    # Tie-in, then a run along both legs: it holds the fabric and lifts the satin.
    start = at(low, -middle)
    points = [start, at(low+.6, -middle), start]
    for a, b in zip([(low, -middle), (high, -middle), (high, middle), (low, middle)],
                    [(high, -middle), (high, middle), (low, middle), (low, -middle)]):
        points += _along(at(*a), at(*b), 20.0)
    points += satin(low, high, -outer, -inner, .35)[1:]    # first leg
    points += satin(high, half, -outer, outer, .3)[1:]     # bar tack across both legs
    points += satin(high, low, outer, inner, .35)[1:]      # second leg
    points += satin(low, -half, outer, -outer, .3)[1:]     # closing bar tack
    # Tie-off: back 0.6 mm along the last stitch and out again.
    end, before = points[-1], points[-2]
    k = 6/max(math.dist(end, before), 6)
    return points+[(end[0]+(before[0]-end[0])*k, end[1]+(before[1]-end[1])*k), end]


def apply(plan, basting, holes, field, to_plan):
    """Basting first (its own thread), the design, then the buttonholes. Returns the drawn
    lines (plan units) for `band`: [(points, closed area?)]."""
    stitches, threads = plan['stitches'], plan['threadlist']
    sewn = [buttonhole_points(hole, to_plan(hole['x'], hole['y'])) for hole in holes]
    drawn = []
    line = basting_line(basting, stitches, field, [p for points in sewn for p in points])
    if line:
        thread = dict(threads[0], color=BASTE_COLOUR, description='Basting (pull out afterwards)')
        # No tie-offs: basting is pulled out after sewing.
        head = [[*line[0], 'JUMP']]+[[*p, 'STITCH'] for p in line]+[[*line[-1], 'TRIM'], [*line[-1], 'COLOR_CHANGE']]
        stitches[:0] = head
        threads.insert(0, thread)
        extras = plan.setdefault('extras', {})
        if extras.get('puff_threads'):
            extras['puff_threads'] = [i+1 for i in extras['puff_threads']]
        drawn.append((line, False))
    if holes:
        if stitches and stitches[-1][2] == 'END':
            stitches.pop()
        here = stitches[-1][:2] if stitches else [0, 0]
        colour = threads[-1]['color'] if threads else None
        for hole, points in zip(holes, sewn):
            if stitches and stitches[-1][2] != 'TRIM':
                stitches.append([*here, 'TRIM'])
            if hole['colour'] != colour:
                stitches.append([*here, 'COLOR_CHANGE'])
                threads.append(dict(threads[-1], color=hole['colour'], description='Buttonholes'))
                colour = hole['colour']
            stitches.append([*points[0], 'JUMP'])
            stitches += [[*p, 'STITCH'] for p in points]
            here = list(points[-1])
            stitches.append([*here, 'TRIM'])
            drawn.append((points, True))
        stitches.append([*here, 'END'])
    return drawn


def band(drawn, scale, origin, shape):
    """(pad, mask): the pixels the basting and buttonholes sew, on the picture's canvas grown
    by `pad` pixels on every side (origin: the plan's centre on the canvas, in mm)."""
    lines = [(np.asarray(points, float)/10+origin)/scale for points, _ in drawn]
    low = min(float(p.min()) for p in lines)
    high_x = max(float(p[:, 0].max()) for p in lines)
    high_y = max(float(p[:, 1].max()) for p in lines)
    pad = max(0, math.ceil(max(-low, high_x-shape[1], high_y-shape[0])))+4
    if (shape[0]+2*pad)*(shape[1]+2*pad) > 16_000_000:
        raise ValueError('The basting or a buttonhole is too far from the design to check. '
                         'Baste around the design, or move the buttonholes closer.')
    mask = np.zeros((shape[0]+2*pad, shape[1]+2*pad), np.uint8)
    for (points, area), line in zip(drawn, lines):
        pixels = np.rint(line+pad).astype(np.int32)
        if area:
            cv2.fillPoly(mask, [cv2.convexHull(pixels)], 1)
        cv2.polylines(mask, [pixels], False, 1, thickness=3)
    return pad, mask.astype(bool)
