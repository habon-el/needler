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
    return sorted(problems, key=lambda p: order[p['code']])
