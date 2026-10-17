"""Explain source pieces the existing pixel-contour fill converter cannot sew.

This is a converter limitation, not a physical minimum-size rule. Keep the
selected pixels unchanged; never pretend that an omitted piece was digitized.
The threshold matches the existing engine/region inventory (4 pixel-square
contour area). Raising canvas size cannot recover missing raster geometry.
"""
import cv2
import numpy as np


def missing_boundaries(rgb, alpha, scale):
    issues = []
    for colour in np.unique(rgb[alpha], axis=0):
        mask = (np.all(rgb == colour, axis=2) & alpha).astype('uint8')
        contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if hierarchy is None:
            continue
        _, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        seen = set()
        for index, contour in enumerate(contours):
            if hierarchy[0, index, 3] != -1 or cv2.contourArea(contour) >= 4:
                continue
            px, py = contour[0, 0]
            component = int(labels[py, px])
            if component in seen:
                continue
            seen.add(component)
            x, y, width, height, pixels = map(int, stats[component])
            issues.append(dict(code='missing_boundary', colour='#%02x%02x%02x' % tuple(colour),
                bounds=[x, y, x + width, y + height], pixels=pixels,
                width_mm=round(width * scale, 4), height_mm=round(height * scale, 4),
                area_mm2=round(pixels * scale * scale, 6),
                reason='This detail has too few image pixels for the current fill converter. '
                       'Use a higher-resolution original, or explicitly edit this detail; nothing was removed.'))
    return issues


def require_boundaries(issues):
    if issues:
        first = issues[0]
        raise ValueError(f"Stitching would leave out {len(issues)} selected detail(s); "
                         f"first is {first['width_mm']:g} × {first['height_mm']:g} mm "
                         f"at image bounds {first['bounds']}. {first['reason']}")
