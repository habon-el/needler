"""Replace exposed sewn connectors with secured cuts on the machine grid.

Original needle positions are retained. Locks retrace adjacent, mask-checked
sewn segments, never an invented direction across fabric. An unsafe endpoint
or unavailable anchor is left untouched for the normal release gate to report.
This is a proposal rule; the caller only publishes a fully verified candidate.
"""
import math

import pyembroidery as emb

from .knockout_routing import RemovedPixels


def _anchor(point, neighbour, mask):
    distance = math.dist(point, neighbour)
    if not 3 <= distance <= 70 or mask.crosses(point, neighbour):
        return None
    anchor = [round(point[k] + (neighbour[k] - point[k]) * min(1, 6 / distance))
              for k in (0, 1)]
    if not 3 <= math.dist(point, anchor) <= 70 or mask.crosses(point, anchor):
        return None
    return anchor


def repair(pattern, alpha, scale, origin):
    mask = RemovedPixels(alpha, scale, origin)
    source = pattern.stitches
    # Reserve the same start/end locks as the short-span repair rule.
    protected = set()
    start = 0
    for end in range(len(source) + 1):
        if end == len(source) or source[end][2] != emb.STITCH:
            ids = list(range(start, end))
            protected.update(ids[:5])
            protected.update(ids[-4:])
            start = end + 1
    output = []
    changes = []
    for i, stitch in enumerate(source):
        # Only ordinary adjacent stitches, not events or unknown command flags.
        if (2 <= i < len(source) - 1 and i not in protected
                and i-1 not in protected) and all(
                s[2] == emb.STITCH for s in source[i-2:i+2]):
            before, start, finish, after = [s[:2] for s in source[i-2:i+2]]
            if (mask.crosses(start, finish)
                    and not mask.crosses(start, start)
                    and not mask.crosses(finish, finish)):
                end_anchor = _anchor(start, before, mask)
                start_anchor = _anchor(finish, after, mask)
                if end_anchor is not None and start_anchor is not None:
                    # Four penetrations per lock, same as the configured style.
                    output.extend([[*p, emb.STITCH] for p in
                                   (end_anchor, start, end_anchor, start)])
                    output.extend([[*start, emb.TRIM], [*finish, emb.JUMP],
                                   list(stitch)])
                    output.extend([[*p, emb.STITCH] for p in
                                   (start_anchor, finish, start_anchor, finish)])
                    changes.append(dict(command=i, start_mm=[v/10 for v in start],
                                        end_mm=[v/10 for v in finish]))
                    continue
        output.append(list(stitch))
    pattern.stitches = output
    return dict(gaps_cut=len(changes), changes=changes,
                original_needle_movement_mm=0,
                added_lock_stitches=8*len(changes))
