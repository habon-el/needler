"""Bounded repair of our configured four-penetration start lock on the file grid.

Require the recognisable A-B-A prefix after a jump and initial penetration.
Keep the jump, initial position, fourth lock position, stitch count and following
path unchanged. All new spans are checked in both directions against the mask.
This is only a proposal; the shared written-file release gate remains mandatory.
"""
import math
import pyembroidery as emb
from .knockout_routing import RemovedPixels


def repair(pattern, alpha, scale, origin):
    mask = RemovedPixels(alpha, scale, origin)
    points = pattern.stitches
    count = 0
    largest = 0.0
    for i in range(1, len(points)-4):
        if points[i-1][2] != emb.JUMP:
            continue
        block = points[i:i+5]
        if any(p[2] != emb.STITCH for p in block):
            continue
        start, a, b, c, end = [p[:2] for p in block]
        if points[i-1][:2] != start or a != c or b != start:
            continue
        if not 0 < math.dist(start, a) < 3-1e-8:
            continue
        distance = math.dist(start, end)
        if not 6 <= distance <= 70:
            continue
        anchor = [round(start[k]+(end[k]-start[k])*min(.5, 6/distance)) for k in (0, 1)]
        proposed = [start, anchor, start, anchor, end]
        move = max(math.dist(old[:2], new)/10 for old, new in zip(block, proposed))
        if move > .45+1e-8:
            continue
        if any(not 3-1e-8 <= math.dist(x, y) <= 70+1e-8 or
               mask.crosses(x, y) or mask.crosses(y, x)
               for x, y in zip(proposed, proposed[1:])):
            continue
        points[i:i+5] = [[*p, emb.STITCH] for p in proposed]
        count += 1
        largest = max(largest, move)
    return dict(start_locks_rebuilt=count, largest_needle_movement_mm=largest)
