"""Cut exposed connectors for explicitly accepted colour-knockout artwork.

This is not a new fill algorithm. Preserve the engine's sewn paths, replacing
only travel across removed pixels with locked, trimmed moves. The boundary
allowance is one pixel: it accommodates contour rasterisation and 0.1 mm file
rounding. The written files are checked again; an unresolved crossing fails closed.
"""
import cv2
import numpy as np
import pyembroidery as emb


class RemovedPixels:
    def __init__(self, alpha, scale, origin):
        self.core = cv2.erode((~alpha).astype('uint8'), np.ones((3, 3), 'uint8')) > 0
        self.scale = scale
        self.origin = np.asarray(origin)

    def crosses(self, a, b):
        # EmbPattern uses tenths of a millimetre, source masks use pixels.
        return self.crosses_many([(a, b)])[0]

    def crosses_many(self, segments):
        """crosses() for many segments in one numpy pass (one call per segment
        spent most of a lettering check in numpy overhead). The samples are
        computed exactly as np.linspace does for each segment, so every
        answer is the same as checking the segments one by one."""
        if not segments:
            return []
        ends = np.asarray(segments, dtype=float).reshape(len(segments), 2, 2)
        a = (ends[:, 0] / 10 + self.origin) / self.scale
        b = (ends[:, 1] / 10 + self.origin) / self.scale
        delta = b - a
        n = np.maximum(2, (np.sqrt((delta * delta).sum(1)) * 4).astype(int) + 1)
        div = (n - 1).astype(float)[:, None]
        step = delta / div
        seg = np.repeat(np.arange(len(n)), n)
        first = np.cumsum(n) - n
        i = (np.arange(int(n.sum())) - first[seg]).astype(float)[:, None]
        # np.linspace: i*step + start, or i/div*delta + start when a step is 0.
        zero = (step == 0).any(1)
        xy = np.where(zero[seg, None], i / div[seg] * delta[seg], i * step[seg]) + a[seg]
        xy[first + n - 1] = b
        xy = np.rint(xy).astype(int)
        h, w = self.core.shape
        outside = (xy[:, 0] < 0) | (xy[:, 0] >= w) | (xy[:, 1] < 0) | (xy[:, 1] >= h)
        hit = outside.copy()
        inside = ~outside
        hit[inside] = self.core[xy[inside, 1], xy[inside, 0]]
        return np.logical_or.reduceat(hit, first).tolist()


def lock(point, anchor, mask):
    """Retrace an already verified ink segment; do not invent a new direction.

    The out-and-back fractions follow pyembroidery's existing lock_stitch
    convention. Physical locking still requires a fabric/machine sew-out.
    """
    if anchor is None or mask.crosses(point, anchor):
        raise ValueError('Cannot secure a thread beside a removed area. Adjust this detail before exporting.')
    a, b = np.asarray(point), np.asarray(anchor)
    # Thirds of a short segment are shorter than the 0.3 mm minimum stitch:
    # below 0.9 mm retrace the whole segment instead (still the same verified line).
    fractions = (.33, .66, .33, 0) if np.linalg.norm(b-a) >= 9 else (1, 0, 1, 0)
    points = [np.rint(a + (b-a)*t).astype(int).tolist() for t in fractions]
    previous = point
    for target in points:
        if mask.crosses(previous, target):
            raise ValueError('Cannot secure a thread on the machine grid beside a removed area. Review this detail.')
        previous = target
    return [[*target, emb.STITCH] for target in points]


def protect(pattern, alpha, scale, origin):
    mask = RemovedPixels(alpha, scale, origin)
    # Route on the actual 0.1 mm grid, not float paths which may round into holes.
    # Ordinary non-knockout designs do not enter this operation.
    source = [[round(x), round(y), flags] for x, y, flags in pattern.stitches]
    output = []
    prior = [0., 0.]
    anchor = None
    thread = False
    cuts = 0
    restart_lock = False
    for i, (x, y, flags) in enumerate(source):
        point = [x, y]
        kind = flags & emb.COMMAND_MASK
        exposed = kind in (emb.STITCH, emb.JUMP) and thread and mask.crosses(prior, point)
        if exposed:
            output.extend(lock(prior, anchor, mask))
            output.append([*prior, emb.TRIM])
            output.append([*point, emb.JUMP])
            cuts += 1
            thread = False
            restart_lock = kind == emb.JUMP
            if kind == emb.STITCH:
                # Restart at the destination, then lock along its next ink
                # segment. Never stitch the old connecting line across a hole.
                output.append([*point, emb.STITCH])
                following = next((s for s in source[i+1:] if s[:2] != point), None)
                if following is None or following[2] & emb.COMMAND_MASK != emb.STITCH:
                    raise ValueError('A removed area leaves an isolated stitch. Review this detail before exporting.')
                output.extend(lock(point, following[:2], mask))
                thread = True
            anchor = None
        else:
            output.append([x, y, flags])
            if kind == emb.STITCH:
                if mask.crosses(point, point):
                    raise ValueError('A stitch lands inside a removed area. Review the artwork or border before exporting.')
                if restart_lock:
                    following = next((s for s in source[i+1:] if s[:2] != point), None)
                    if following is None or following[2] & emb.COMMAND_MASK != emb.STITCH:
                        raise ValueError('A removed area leaves an isolated stitch. Review this detail before exporting.')
                    output.extend(lock(point, following[:2], mask))
                    restart_lock = False
                if thread and point != prior:
                    anchor = prior
                thread = True
            elif kind in (emb.TRIM, emb.COLOR_CHANGE, emb.END):
                thread = False
                anchor = None
                restart_lock = False
        prior = point
    pattern.stitches = output
    return cuts


def verify(pattern, alpha, scale, origin):
    """Validate decoded machine commands, including untrimmed jump threads."""
    mask = RemovedPixels(alpha, scale, origin)
    prior = [0., 0.]
    thread = False
    for x, y, flags in pattern.stitches:
        point = [x, y]
        kind = flags & emb.COMMAND_MASK
        if kind == emb.STITCH:
            if mask.crosses(point, point) or (thread and mask.crosses(prior, point)):
                raise ValueError('Machine-file verification found a stitch across a removed area. Export was not approved.')
            thread = True
        elif kind == emb.JUMP and thread and mask.crosses(prior, point):
            raise ValueError('Machine-file verification found an uncut travel thread over a removed area. Export was not approved.')
        elif kind in (emb.TRIM, emb.COLOR_CHANGE, emb.END):
            thread = False
        prior = point
