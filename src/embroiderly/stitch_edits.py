"""Stitch edits: a machine stop or a thread cut added at one point of the sewing
order, and single stitches deleted or moved a little.

Kept as a recipe like the exact stitch removal (stitch_cuts.py): the edits are
saved with the design and applied to the engine plan whenever stitches are
rebuilt. Each edit is anchored to the stitch it was made on by its position
(x, y in mm, as playback shows it) and its place in the sewing order (n, the
how-many-th sewn stitch). When the design changes and no stitch is there any
more, the edit is left out and the result says so. An edit that would make a
stitch shorter than 0.3 mm, longer than 7 mm or cross empty fabric is refused.
"""
import math

from .stitch_cuts import LOCK, _toward

KINDS = {'stop': 'Stop', 'trim': 'Cut', 'delete': 'Deleted stitch', 'move': 'Moved stitch'}
MAX_EDITS = 200
MAX_MOVE_MM = 3.0
MATCH = 1.5           # a stitch within 0.15 mm (plan units are 0.1 mm) is the same stitch
MIN_MM, MAX_MM = .3, 7.


def _number(value, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) \
            or not low <= value <= high:
        raise ValueError('A stitch edit has an invalid position. Remove it and add it again.')
    return float(value)


def choices(settings):
    """The saved `stitch_edits`, checked: [{kind, x, y, n[, to]}] in the order they were added."""
    raw = settings.get('stitch_edits') or []
    if not isinstance(raw, list):
        raise ValueError('Stitch edits must be a list.')
    if len(raw) > MAX_EDITS:
        raise ValueError(f'Too many stitch edits (at most {MAX_EDITS}). Remove some first.')
    edits = []
    for edit in raw:
        if not isinstance(edit, dict) or edit.get('kind') not in KINDS:
            raise ValueError('Choose a listed stitch edit: stop, cut, delete or move.')
        n = edit.get('n')
        if isinstance(n, bool) or not isinstance(n, int) or not 0 < n <= 10**7:
            raise ValueError('A stitch edit has an invalid position. Remove it and add it again.')
        item = dict(kind=edit['kind'], x=round(_number(edit.get('x'), -5000, 5000), 2),
                    y=round(_number(edit.get('y'), -5000, 5000), 2), n=n)
        if edit['kind'] == 'move':
            to = edit.get('to')
            if not isinstance(to, (list, tuple)) or len(to) != 2:
                raise ValueError('Say where the stitch should move to.')
            item['to'] = [round(_number(v, -5000, 5000), 2) for v in to]
            if math.dist(item['to'], (item['x'], item['y'])) > MAX_MOVE_MM + 1e-6:
                raise ValueError(f'A stitch can move at most {MAX_MOVE_MM:g} mm. Delete it instead, or redraw the part.')
        edits.append(item)
    return edits


def _match(stitches, point, n):
    """Index of the sewn stitch at point (plan units) closest to the n-th in sewing order."""
    best, count = None, 0
    for i, (x, y, command) in enumerate(stitches):
        if command != 'STITCH':
            continue
        count += 1
        if abs(x-point[0]) <= MATCH and abs(y-point[1]) <= MATCH and math.dist((x, y), point) <= MATCH:
            if best is None or abs(count-n) < best[0]:
                best = (abs(count-n), i)
    return None if best is None else best[1]


def _segment(a, b, crosses, what):
    length = math.dist(a, b)/10
    if length < MIN_MM-1e-6:
        raise ValueError(f'{what} would leave a stitch {length:.2f} mm long; the shortest allowed is 0.3 mm.')
    if length > MAX_MM+1e-6:
        raise ValueError(f'{what} would leave a stitch {length:.1f} mm long; the longest allowed is 7 mm.')
    if crosses is not None and crosses(a, b):
        raise ValueError(f'{what} would make the thread cross empty fabric.')


def apply(plan, edits, to_plan=lambda x, y: (x*10, y*10), crosses=None):
    """Apply edits to an engine plan ({'stitches': [[x, y, command]], 'threadlist', 'extras'}) in place.
    to_plan maps playback millimetres to plan units; crosses(a, b) says whether a sewn segment
    (plan units) leaves the sewn area. Returns a report: applied, dropped messages and the
    thread numbers (0-based) that start after an added stop."""
    out = plan['stitches']
    stops, dropped, applied = [], [], 0
    for number, edit in enumerate(edits, 1):
        name = f"{KINDS[edit['kind']]} {number}"
        i = _match(out, to_plan(edit['x'], edit['y']), edit['n'])
        if i is None:
            dropped.append(f'{name} no longer matches a stitch (the design changed), so it was left out. Remove it from the list.')
            continue
        p = out[i][:2]
        after = out[i+1][2] if i+1 < len(out) else 'END'
        if edit['kind'] == 'stop':
            j = i+2 if after == 'TRIM' else i+1
            if j >= len(out) or out[j][2] in ('COLOR_CHANGE', 'END'):
                raise ValueError(f'{name}: the machine already stops here for the next thread. Remove this stop.')
            # A stop is a change to the same thread; the machine pauses and keeps the thread.
            marker = [*p, 'COLOR_CHANGE']
            out.insert(j, marker); stops.append(marker)
        elif edit['kind'] == 'trim':
            if after in ('TRIM', 'COLOR_CHANGE', 'END'):
                raise ValueError(f'{name}: the thread is already cut here. Remove this cut.')
            # Tie off on this stitch (as stitch_cuts does), cut, then resume with a tie-in.
            back = None
            for k in range(i-1, -1, -1):
                if out[k][2] != 'STITCH':
                    break
                if math.dist(out[k][:2], p) >= 4.5:
                    back = out[k]; break
            lock = [[*_toward(p, back[:2], LOCK), 'STITCH'], [*p, 'STITCH']] if back is not None else []
            resume = [[*p, 'JUMP'], [*p, 'STITCH']] if after == 'STITCH' else []
            out[i+1:i+1] = lock+[[*p, 'TRIM']]+resume
            k = i+1+len(lock)+1
            while k < len(out) and out[k][2] == 'JUMP':
                k += 1
            if k+1 < len(out) and out[k][2] == 'STITCH' and out[k+1][2] == 'STITCH' \
                    and math.dist(out[k][:2], out[k+1][:2]) >= LOCK:
                start = out[k][:2]
                out[k+1:k+1] = [[*_toward(start, out[k+1][:2], LOCK), 'STITCH'], [*start, 'STITCH']]
        elif edit['kind'] == 'delete':
            if i == 0 or out[i-1][2] != 'STITCH':
                raise ValueError(f'{name}: this stitch starts a run of stitches and cannot be deleted. Delete the next stitch instead.')
            if after == 'STITCH':
                _segment(out[i-1][:2], out[i+1][:2], crosses, 'Deleting this stitch')
            del out[i]
            if not any(s[2] == 'STITCH' for s in out):
                raise ValueError('Deleting that stitch leaves nothing to sew. Remove the edit.')
        else:
            q = list(to_plan(*edit['to']))
            before = out[i-1] if i else None
            if before is None or before[2] not in ('STITCH', 'JUMP'):
                raise ValueError(f'{name}: this stitch cannot be moved. Move the stitch after it instead.')
            if crosses is not None and crosses(q, q):
                raise ValueError(f'{name}: the new place is on empty fabric. Move it onto the stitched part.')
            if before[2] == 'STITCH':
                _segment(before[:2], q, crosses, 'Moving this stitch')
            if after == 'STITCH':
                _segment(q, out[i+1][:2], crosses, 'Moving this stitch')
            if before[2] == 'JUMP' and math.dist(before[:2], p) <= MATCH:
                # A run starts with a jump onto its first stitch: the jump goes along.
                out[i-1] = [*q, 'JUMP']
            out[i] = [*q, 'STITCH']
        applied += 1
    # Thread numbers after each added stop; the stop repeats the thread in the thread list.
    marks = {id(m) for m in stops}
    thread, starts = 0, []
    for s in out:
        if s[2] == 'COLOR_CHANGE':
            thread += 1
            if id(s) in marks:
                starts.append(thread)
    threads = plan.get('threadlist', [])
    for start in starts:
        threads.insert(start, dict(threads[start-1]))
    puff = plan.get('extras', {}).get('puff_threads')
    if puff:
        final = [f for f in range(len(threads)) if f not in starts]   # original thread -> its new number
        plan['extras']['puff_threads'] = [final[t] for t in puff]
    return dict(applied=applied, dropped=dropped, stops=starts)
