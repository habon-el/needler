"""Multi-hooping: a design bigger than the hoop is sewn in several hoopings.

The checked machine pattern is cut along seams into a grid of parts, each small enough to
sit in the hoop with EDGE_MM spare on every side. A seam slides within the room the hoop
allows to where it crosses the fewest stitches, so it falls between objects when it can.
A stitch crossing a seam is cut on it. Where the same run comes back to the seam within
JOIN_MM (fill rows turning), the part keeps sewing along the seam instead of cutting, like
rows turning at an edge; other new thread ends get a tie-off. Each pair of
neighbouring hoopings shares two alignment crosses on their seam, sewn in their own colour
last in the earlier hooping and first in the later one, so the fabric can be lined up after
re-hooping.

Each hooping is written as its own machine file pair, centred on its hoop, and passes the
same release checks as a whole design: its check area is the design's plus the small
squares of its alignment crosses. Coordinates are tenths of a millimetre, as in the pattern."""
import json
import math
from bisect import bisect_left
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pyembroidery as emb

VERSION = 1         # part of the saved plan's key: a new splitter rebuilds the files
EDGE_MM = 5.        # spare hoop room around each part, holding the alignment crosses
MAX_HOOPINGS = 12
MARK_ARM_MM = 3.    # alignment cross: arms 3 mm long, sewn as 1.5 mm running stitches
MARK_COLOUR = '#e5007e'
TIE_MM = .6         # tie-off at a cut thread end: back and forth along the stitch
MIN_PART_MM = 1.    # a cut-off piece shorter than this is left out
JOIN_MM = 3.        # keep sewing along the seam to the run's next part this close
SHORT = 3.1         # stitches shorter than 0.31 mm are merged (release limit 0.3 mm)


def plan(left, top, right, bottom, field):
    """Equal grid for a design box (mm) and hoop field [w, h]: (columns, rows), or (1, 1)
    when it fits. ValueError when the hoop is too small or too many hoopings are needed."""
    width, height = right-left, bottom-top
    if width <= field[0] and height <= field[1]:
        return 1, 1
    usable = field[0]-2*EDGE_MM, field[1]-2*EDGE_MM
    if min(usable) < 20:
        raise ValueError('This hoop is too small to split a design. Choose a bigger hoop.')
    columns, rows = math.ceil(width/usable[0]), math.ceil(height/usable[1])
    if columns*rows > MAX_HOOPINGS:
        raise ValueError(f'This design would need {columns*rows} hoopings. Choose a bigger hoop or make the design smaller.')
    return columns, rows


def _sections(pattern):
    """Sewn runs [(colour index, [(x, y), …])], broken at every jump, cut and colour change."""
    sections, colour, current, previous, last = [], 0, None, (0, 0), None
    for x, y, flags in pattern.stitches:
        kind = flags & emb.COMMAND_MASK
        if kind == emb.STITCH:
            if current is None:
                current = (colour, [previous] if last == emb.JUMP and previous != (x, y) else [])
                sections.append(current)
            current[1].append((x, y))
        else:
            current = None
            if kind == emb.COLOR_CHANGE:
                colour += 1
        previous, last = (x, y), kind
    return [s for s in sections if len(s[1]) > 1]


def _seams(low, high, count, usable, starts, ends):
    """Seam positions between low and high (tenths of mm): each part at most `usable` wide,
    each seam where the fewest stitch segments cross it (sorted segment starts/ends)."""
    seams, previous = [], low
    for k in range(1, count):
        first, last = max(previous, high-(count-k)*usable), min(previous+usable, high)
        candidates = np.arange(first, last+1e-6, 5.)
        crossing = np.searchsorted(starts, candidates, 'left')-np.searchsorted(ends, candidates, 'right')
        # Ties go to the seam nearest an equal split.
        cost = crossing+np.abs(candidates-(low+(high-low)*k/count))*1e-4
        previous = float(candidates[np.argmin(cost)])
        seams.append(previous)
    return seams


def _cut(points, xs, ys):
    """Split one sewn run at the seams: [(column, row, points, starts on seam, ends on seam)]."""
    cell = lambda p: (bisect_left(xs, p[0]), bisect_left(ys, p[1]))
    parts, chain, at, cut = [], [points[0]], None, False
    for a, b in zip(points, points[1:]):
        ts = sorted({(s-a[i])/(b[i]-a[i]) for i, seams in ((0, xs), (1, ys)) for s in seams
                     if (a[i]-s)*(b[i]-s) < 0})
        for t0, t1 in zip([0.]+ts, ts+[1.]):
            middle = (a[0]+(b[0]-a[0])*(t0+t1)/2, a[1]+(b[1]-a[1])*(t0+t1)/2)
            here = cell(middle)
            end = (a[0]+(b[0]-a[0])*t1, a[1]+(b[1]-a[1])*t1)
            if at is None:
                at = here
            elif here != at:
                parts.append((*at, chain, cut, True))
                chain, at, cut = [chain[-1]], here, True
            chain.append(end)
    parts.append((*at, chain, cut, False))
    return parts


def _tidy(chain, tie_start, tie_end):
    """Merge too-short stitches and tie off the ends cut on a seam; None when too short to sew."""
    kept = [chain[0]]
    for p in chain[1:]:
        if math.dist(kept[-1], p) >= SHORT:
            kept.append(p)
    if len(kept) < 2 or sum(math.dist(a, b) for a, b in zip(kept, kept[1:])) < MIN_PART_MM*10:
        return None
    def tie(end, toward):
        length = math.dist(end, toward)
        if length < 2*SHORT:
            return []
        step = min(TIE_MM*10, length/2)/length
        return [(end[0]+(toward[0]-end[0])*step, end[1]+(toward[1]-end[1])*step), end]
    if tie_start:
        kept = [kept[0]]+tie(kept[0], kept[1])+kept[1:]
    if tie_end:
        kept = kept+tie(kept[-1], kept[-2])
    return kept


def _cross(centre):
    """Running-stitch cross: left to right, back to the middle, top to bottom."""
    x, y = centre
    arm, step = MARK_ARM_MM*10, MARK_ARM_MM*5
    across = [(x+d, y) for d in np.arange(-arm, arm+1, step)]
    return across+[(x+step, y), (x, y)]+[(x, y+d) for d in np.arange(-arm, arm+1, step)]


def split(pattern, field, crosses=None):
    """The hoopings for a hoop field [w, h] mm: [{n, column, row, centre, cell, runs, marks_first,
    marks_last}] in sewing order (rows top to bottom, left to right), coordinates in tenths of mm.
    runs = [(colour index, points)]. A design that fits gives []. crosses(a, b) tells whether a
    stitch would cross an empty area; such a join along a seam is cut instead."""
    sections = _sections(pattern)
    every = np.array([p for _, points in sections for p in points], float)
    left, top = every.min(0)
    right, bottom = every.max(0)
    columns, rows = plan(left/10, top/10, right/10, bottom/10, field)
    if columns*rows == 1:
        return []
    segments = np.array([(a, b) for _, points in sections for a, b in zip(points, points[1:])], float)
    seams = []
    for axis, low, high, count, size in ((0, left, right, columns, field[0]), (1, top, bottom, rows, field[1])):
        lo, hi = np.minimum(segments[:, 0, axis], segments[:, 1, axis]), np.maximum(segments[:, 0, axis], segments[:, 1, axis])
        seams.append(_seams(low, high, count, (size-2*EDGE_MM)*10, np.sort(lo), np.sort(hi)))
    xs, ys = seams
    edges_x, edges_y = [left]+xs+[right], [top]+ys+[bottom]
    hoopings = []
    for row in range(rows):
        for column in range(columns):
            cell = [edges_x[column], edges_y[row], edges_x[column+1], edges_y[row+1]]
            hoopings.append(dict(n=len(hoopings)+1, column=column, row=row, cell=cell,
                                 centre=[(cell[0]+cell[2])/2, (cell[1]+cell[3])/2], runs=[], marks_first=[], marks_last=[]))
    at = {(h['column'], h['row']): h for h in hoopings}
    for colour, points in sections:
        # Parts of this run still open per hooping: [points, starts on seam, ends on seam].
        open_parts = {}
        def close(key):
            chain = _tidy(*open_parts.pop(key))
            if chain:
                at[key]['runs'].append((colour, chain))
        for column, row, chain, cut_start, cut_end in _cut(points, xs, ys):
            key, last = (column, row), open_parts.get((column, row))
            if last and last[2] and cut_start and math.dist(last[0][-1], chain[0]) <= JOIN_MM*10                     and not (crosses and crosses(last[0][-1], chain[0])):
                last[0].extend(chain)
                last[2] = cut_end
                continue
            if last:
                close(key)
            open_parts[key] = [list(chain), cut_start, cut_end]
        for key in list(open_parts):
            close(key)
    # Alignment crosses at a quarter and three quarters along each shared seam.
    for h in hoopings:
        c, r, (l, t, rt, b) = h['column'], h['row'], h['cell']
        for later, marks in (((c+1, r), [(rt, t+(b-t)/4), (rt, t+3*(b-t)/4)]), ((c, r+1), [(l+(rt-l)/4, b), (l+3*(rt-l)/4, b)])):
            if later in at:
                h['marks_last'] += marks
                at[later]['marks_first'] += marks
    return hoopings


def _pattern(hooping, threads):
    """One hooping as a pattern centred on its hoop: marks to line up, the design, marks for the next."""
    out = emb.EmbPattern()
    blocks = [(None, _cross(m)) for m in hooping['marks_first']]+hooping['runs']+[(None, _cross(m)) for m in hooping['marks_last']]
    cx, cy = hooping['centre']
    colour, here = object(), (0, 0)
    for which, points in blocks:
        points = [(round(x-cx), round(y-cy)) for x, y in points]
        if which != colour:
            thread = emb.EmbThread()
            if which is None:
                thread.set_hex_color(MARK_COLOUR)
                thread.description = 'Alignment marks'
            else:
                original = threads[which]
                thread.set_hex_color(original.hex_color())
                thread.description, thread.catalog_number = original.description, original.catalog_number
            if out.stitches:
                out.add_stitch_absolute(emb.TRIM, *here)
                out.add_stitch_absolute(emb.COLOR_CHANGE, *here)
            out.add_thread(thread)
            colour = which
        elif out.stitches:
            out.add_stitch_absolute(emb.TRIM, *here)
        out.add_stitch_absolute(emb.JUMP, *points[0])
        for p in points:
            out.add_stitch_absolute(emb.STITCH, *p)
        here = points[-1]
    out.add_stitch_absolute(emb.TRIM, *here)
    out.add_stitch_absolute(emb.END, *here)
    return out


def build(directory, field):
    """Write every hooping of the checked design in `directory` for hoop field [w, h] mm, under
    directory/hoopings/<w>x<h>/hooping-<n>; return the summary (also saved as plan.json)."""
    from .machine_files import write_pair
    from .release_gate import checked_bytes, read_context, record_context, digest
    directory = Path(directory)
    source = checked_bytes(directory, 'pes')
    target = directory/'hoopings'/f'{field[0]:g}x{field[1]:g}'
    try:
        summary = json.loads((target/'plan.json').read_text())
        if summary['source'] == digest(source) and summary['version'] == VERSION:
            return summary
    except (OSError, ValueError, KeyError):
        pass
    record, mask = read_context(directory)
    scale, origin = record['scale'], np.asarray(record['origin'])
    with TemporaryDirectory(prefix='needlora-hooping-') as temp:
        (Path(temp)/'design.pes').write_bytes(source)
        pattern = emb.EmbPattern(str(Path(temp)/'design.pes'))
    from .knockout_routing import RemovedPixels
    removed = RemovedPixels(mask, scale, origin)
    hoopings = split(pattern, field, removed.crosses)
    pad = math.ceil((MARK_ARM_MM+EDGE_MM)/scale)+2
    for h in hoopings:
        part = target/f'hooping-{h["n"]}'
        part.mkdir(parents=True, exist_ok=True)
        write_pair(_pattern(h, pattern.threadlist), part/'design.pes', part/'design.dst', {'version': 6})
        # Check area: the design's, widened to hold the crosses, plus a square around each cross.
        area = np.pad(mask, pad)
        for x, y in h['marks_first']+h['marks_last']:
            reach = (MARK_ARM_MM+1)/scale
            px, py = (x/10+origin[0])/scale+pad, (y/10+origin[1])/scale+pad
            area[max(0, math.floor(py-reach)):math.ceil(py+reach)+1, max(0, math.floor(px-reach)):math.ceil(px+reach)+1] = True
        record_context(part, area, scale, (origin+np.asarray(h['centre'])/10+pad*scale).tolist())
        checked_bytes(part, 'pes')
    summary = dict(source=digest(source), version=VERSION, field_mm=list(field), hoopings=[
        dict(n=h['n'], centre_mm=[round(float(v)/10, 2) for v in h['centre']], cell_mm=[round(float(v)/10, 2) for v in h['cell']],
             stitches=sum(len(points) for _, points in h['runs']), marks=len(h['marks_first'])+len(h['marks_last']))
        for h in hoopings])
    target.mkdir(parents=True, exist_ok=True)
    (target/'plan.json').write_text(json.dumps(summary))
    return summary
