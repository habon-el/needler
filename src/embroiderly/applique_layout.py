"""Appliqué across pieces, after the colour generator (engine.py) has made every part.

- Partial (applique_partial): the fabric runs on under the parts sewn on top of it; their
  stitches hide that edge, so it gets no satin cover there.
- Shared stops (applique_combine): the pieces of one colour pass are placed, tacked down
  and covered together, so the machine stops twice for all of them.
- No double edges (applique_join): where two pieces meet, only the later piece's cover
  sews the join, and in partial appliqué a piece does not run on under another piece.

Document units are pixels of `scale` mm."""
import cv2
import numpy as np

UNDER_MM = 1.5   # how far partial appliqué fabric runs on under a part sewn on top
INSIDE_MM = .8   # and how far its edge stays inside that part's far edge
KEYS = ('applique_partial', 'applique_combine', 'applique_join')


def choices(settings):
    """{key: bool} for the three appliqué options, checked."""
    for key in KEYS:
        if settings.get(key) not in (None, True, False):
            raise ValueError('Appliqué options are on or off.')
    return {key: settings.get(key) is True for key in KEYS}


def _filled(rings, shape):
    area = np.zeros(shape, np.uint8)
    cv2.drawContours(area, rings[:1], -1, 1, -1)
    if len(rings) > 1:
        cv2.drawContours(area, rings[1:], -1, 0, -1)
        # A hole's contour runs on the area's own pixels: put them back.
        cv2.drawContours(area, rings[1:], -1, 1, 1)
    return area


def _tucked(rings, under, scale):
    """The piece grown up to UNDER_MM into `under` (pixels of parts sewn on top), keeping
    INSIDE_MM clear of their far edge. Returns contour rings like the input."""
    area = _filled(rings, under.shape)
    solid = (area.astype(bool) | under).astype(np.uint8)
    deep = cv2.distanceTransform(solid, cv2.DIST_L2, 3) >= INSIDE_MM/scale
    steps = max(1, int(round(UNDER_MM/scale)))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*steps+1, 2*steps+1))
    grown = (cv2.dilate(area, kernel).astype(bool) & (area.astype(bool) | under & deep)).astype(np.uint8)
    contours, hierarchy = cv2.findContours(grown, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return rings
    outer = max((i for i in range(len(contours)) if hierarchy[0, i, 3] == -1), key=lambda i: cv2.contourArea(contours[i]))
    out, child = [contours[outer]], hierarchy[0, outer, 2]
    while child != -1:
        out.append(contours[child])
        child = hierarchy[0, child, 0]
    return out


def _path(mask):
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    return ' '.join('M '+' L '.join(f'{x},{y}' for x, y in c[:, 0, :])+' Z' for c in contours if len(c) >= 3)


def finish(document, pieces, pass_masks, scale, settings):
    """pieces: [(rings, node, pass index)] in sewing order; pass_masks: each colour pass's
    pixels. Sets each piece's outline and the edges it leaves without cover (applique_bare)
    and merges the pieces of one pass when they share stops. Returns [(rings, bare path)]
    per piece, for the cutting file and the release check."""
    options = choices(settings)
    shape = pass_masks[0].shape
    made = []
    for k, (rings, node, step) in enumerate(pieces):
        later = np.zeros(shape, bool)
        for mask in pass_masks[step+1:]:
            later |= mask.astype(bool)
        on_top = np.zeros(shape, np.uint8)
        for other, _, at in pieces[k+1:]:
            if at > step:
                on_top |= _filled(other, shape)
        bare = np.zeros(shape, bool)
        if options['applique_partial']:
            under = later & ~on_top.astype(bool) if options['applique_join'] else later
            rings = _tucked(rings, under, scale)
            bare |= under
        if options['applique_join'] and on_top.any():
            # The join's pixels on this side are next to the later piece.
            bare |= cv2.dilate(on_top, np.ones((3, 3), np.uint8)).astype(bool)
        # Only the bare region along this piece is kept, so the file stays small.
        near = cv2.dilate(_filled(rings, shape), np.ones((7, 7), np.uint8)).astype(bool)
        made.append((rings, node, step, bare & near))
    groups = {}
    for item in made:
        groups.setdefault(item[2] if options['applique_combine'] else id(item), []).append(item)
    result = []
    for group in groups.values():
        first = group[0][1]
        parts, bare = [], np.zeros(shape, bool)
        for rings, node, _, own in group:
            parts += ['M '+' L '.join(f'{x},{y}' for x, y in r[:, 0, :])+' Z' for r in rings if len(r) >= 3]
            bare |= own
            if node is not first:
                document.remove(node)
        first.set('d', ' '.join(parts))
        d = _path(bare) if bare.any() else ''
        if d:
            first.set('{http://inkstitch.org/namespace}applique_bare', d)
        result += [(rings, d or None) for rings, *_ in group]
    return result
