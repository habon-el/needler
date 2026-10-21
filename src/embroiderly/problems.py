"""Problems panel: what blocks or spoils a design, where it is, and a one-click fix.

Reads the same machine-file findings as the release gate (export_findings) for
the generated design, groups nearby findings into one problem, and proposes a
mechanical fix as preparation edits, so the stitches are rebuilt and checked
again rather than patched by hand. Fixes need no AI.
"""
import math
from pathlib import Path

import numpy as np
from PIL import Image

GROUP_MM = 3.0      # findings closer than this are one problem
SPOT_MM = .8        # radius of a fill/remove spot

TITLES = {'crossing': 'Stitches cross bare fabric', 'travel': 'A jump crosses bare fabric',
          'long': 'A stitch is too long', 'short': 'A stitch is too short',
          'cuts': 'Many thread cuts'}

# Plain explanations for the panel: what is wrong, why it matters on the machine.
EXPLAIN = {
    'crossing': ('Some stitches run over a spot that should stay bare fabric.',
                 'The machine would sew a visible thread across that spot.'),
    'travel': ('The needle moves across bare fabric without cutting the thread.',
               'It leaves a loose thread on top that you would have to cut by hand, and it can snag.'),
    'long': ('A stitch is longer than 7 mm.',
             'Long stitches lie loose, snag easily, and many machines refuse them.'),
    'short': ('A stitch is shorter than 0.3 mm.',
              'Very short stitches can break the thread or bunch up.'),
    'cuts': ('The machine will cut the thread {count} times.',
             'Each cut stops the machine and leaves a thread end; many cuts make sewing slow.'),
}
FIX_DOES = {
    'Fill the gap': 'Fills this tiny spot with the colour around it, then remakes and checks the stitches.',
    'Remove the stray stitches': 'Removes the small stitched bit that sits on bare fabric, then remakes and checks the stitches.',
    'Merge small details': 'Merges tiny pieces into the colour next to them, so there are fewer separate parts to cut between.',
}


def explain(problem):
    what, why = EXPLAIN.get(problem['code'], ('', ''))
    fix = problem.get('fix')
    return dict(what=what.format(count=problem.get('count', 0)), why=why,
                fix=FIX_DOES.get(fix['label'], '') if fix else 'No automatic fix: change the size or stitch style, or remove this part.')


def _spot_edit(prepared, px, py, radius):
    """Fill the spot with the colour around it; if it is mostly bare, remove the stray stitching instead."""
    h, w = prepared.shape[:2]
    r = max(2, int(radius * 2))
    x0, x1, y0, y1 = max(0, px - r), min(w, px + r + 1), max(0, py - r), min(h, py + r + 1)
    patch = prepared[y0:y1, x0:x1].reshape(-1, 4)
    solid = patch[patch[:, 3] > 127]
    point = [[min(w - 1, max(0, px)), min(h - 1, max(0, py))]]
    if len(solid) < len(patch) / 2:
        return dict(kind='erase', radius=max(1, int(radius)), points=point, fix=True), 'Remove the stray stitches'
    values, counts = np.unique(solid[:, :3], axis=0, return_counts=True)
    colour = '#%02x%02x%02x' % tuple(int(v) for v in values[counts.argmax()])
    return dict(kind='paint', colour=colour, radius=max(1, int(radius)), points=point, fix=True), 'Fill the gap'


def area_at(prepared_path, x, y):
    """The whole colour area under a click on the prepared picture, as an outline with holes
    (picture pixels), grown by one pixel so its anti-aliased edge goes with it."""
    import cv2
    with Image.open(prepared_path) as image:
        rgba = np.asarray(image.convert('RGBA'))
    h, w = rgba.shape[:2]
    x, y = int(round(x)), int(round(y))
    if not (0 <= x < w and 0 <= y < h) or rgba[y, x, 3] <= 127:
        return None
    same = np.all(rgba == rgba[y, x], axis=2).astype(np.uint8)
    _, labels = cv2.connectedComponents(same, connectivity=8)
    area = (labels == labels[y, x]).astype(np.uint8)
    area = cv2.dilate(area, np.ones((3, 3), np.uint8))
    contours, hierarchy = cv2.findContours(area, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return None
    outer = max((i for i in range(len(contours)) if hierarchy[0, i, 3] == -1), key=lambda i: cv2.contourArea(contours[i]))
    ring = lambda c: [[float(px), float(py)] for px, py in cv2.approxPolyDP(c, .6, True)[:, 0, :]]
    holes, child = [], hierarchy[0, outer, 2]
    while child != -1:
        if cv2.contourArea(contours[child]) >= 4:
            holes.append(ring(contours[child]))
        child = hierarchy[0, child, 0]
    points = ring(contours[outer])
    if len(points) < 3:
        return None
    return dict(points=points, holes=[hole for hole in holes if len(hole) >= 3],
                colour='#%02x%02x%02x' % tuple(int(v) for v in rgba[y, x, :3]))


def collect(directory, prepared_path, options):
    """[{id, title, count, bounds (picture pixels), fix: {label, edits?, set?} | None}] most serious first."""
    from .release_gate import read_context
    from .export_findings import inspect
    from .machine_files import read_pattern
    import json
    directory = Path(directory)
    record, mask = read_context(directory)
    scale, origin = record['scale'], record['origin']
    issues = inspect(read_pattern(directory / 'design.pes'), mask, scale, origin)
    with Image.open(prepared_path) as image:
        prepared = np.asarray(image.convert('RGBA'))
    groups = []
    for issue in issues:
        where = issue.get('location')
        if not where or issue['code'] not in TITLES:
            continue
        x, y = where['x_mm'] + origin[0], where['y_mm'] + origin[1]   # mm in the picture frame
        for g in groups:
            if g['code'] == issue['code'] and math.dist(g['at'], (x, y)) <= GROUP_MM:
                g['count'] += 1
                break
        else:
            groups.append(dict(code=issue['code'], at=(x, y), count=1))
    problems = []
    for i, g in enumerate(groups):
        px, py = int(round(g['at'][0] / scale)), int(round(g['at'][1] / scale))
        span = max(8, int(6 / scale))   # about 12 mm of context around the spot
        fix = None
        if g['code'] in ('crossing', 'travel'):
            edit, label = _spot_edit(prepared, px, py, SPOT_MM / scale)
            fix = dict(label=label, edits=[edit])
        problems.append(dict(id=f'p{i}', code=g['code'], title=TITLES[g['code']], count=g['count'],
                             bounds=[px - span, py - span, px + span, py + span], fix=fix))
    # Too many cuts: not a blocker, but a digitizer would fix it.
    playback = directory / 'playback.json'
    if playback.is_file():
        plan = json.loads(playback.read_text())
        stitches, trims = plan.get('stitch_count', 0), plan.get('trim_count', 0)
        if trims > 15 and trims * 120 > stitches:
            floor = float(options.get('floor_mm2', 1) or 1)
            problems.append(dict(id='cuts', code='cuts', title=TITLES['cuts'], count=trims, bounds=None,
                                 fix=dict(label='Merge small details', set=dict(floor_mm2=round(min(25, max(2.5, floor * 2.5)), 1)))))
    order = {'crossing': 0, 'travel': 1, 'long': 2, 'short': 3, 'cuts': 4}
    for problem in problems:
        problem['explain'] = explain(problem)
    return sorted(problems, key=lambda p: order[p['code']])
