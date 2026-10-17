"""Cut exposed connectors for explicitly accepted colour-knockout artwork.

This is not a new fill algorithm. Preserve the engine's sewn paths, replacing
only travel across removed pixels with locked, trimmed moves. A one-pixel
boundary allowance accommodates contour rasterisation and 0.1 mm file rounding.
The written files are checked again; an unresolved crossing fails closed.
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
        a = (np.asarray(a) / 10 + self.origin) / self.scale
        b = (np.asarray(b) / 10 + self.origin) / self.scale
        xy = np.rint(np.linspace(a, b, max(2, int(np.linalg.norm(b-a)*4)+1))).astype(int)
        h, w = self.core.shape
        if ((xy[:, 0] < 0) | (xy[:, 0] >= w) | (xy[:, 1] < 0) | (xy[:, 1] >= h)).any():
            return True
        return bool(self.core[xy[:, 1], xy[:, 0]].any())


def lock(point, anchor, mask):
    """Retrace an already verified ink segment; do not invent a new direction.

    The out-and-back fractions follow pyembroidery's existing lock_stitch
    convention. Physical locking still requires a fabric/machine sew-out.
    """
    if anchor is None or mask.crosses(point, anchor):
        raise ValueError('Cannot secure a thread beside a removed area. Adjust this detail before exporting.')
    a, b = np.asarray(point), np.asarray(anchor)
    points = [np.rint(a + (b-a)*t).astype(int).tolist() for t in (.33, .66, .33, 0)]
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
