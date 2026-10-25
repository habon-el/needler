"""Translate edited outlines into the existing generator's SVG input.

No stitch coordinates are resized. The opt-in branch leaves legacy SVG output
untouched when piece_edits is absent. Overflow is retained in the generation
mask, rather than clipped to the original photograph's rectangle.
"""
import xml.etree.ElementTree as ET
import cv2
import numpy as np
from .region_stitches import apply_style, path_data, NS


def append(document, layout, scale, settings, colours=None):
    selected = [p for p in layout['pieces'] if p['visible'] and
                (colours or {}).get(p['colour'], {}).get('include', True)]
    if not selected:
        raise ValueError('No visible pieces. Show at least one piece before generating stitches.')
    # Optimize colour changes: copies and cut parts are listed last, so group each thread's
    # pieces together (stable, in first-seen colour order) instead of switching back and forth.
    first = {}
    for p in selected:
        first.setdefault(p['colour'], len(first))
    selected = sorted(selected, key=lambda p: first[p['colour']])
    points = np.concatenate([np.asarray(r) for p in selected for r in p['rings']])
    low, high = points.min(axis=0), points.max(axis=0)
    # An appliqué cover (and its mitred corners) sews up to ~4.5 mm past the outline: keep it on the canvas.
    pad = 2+(int(np.ceil(5/scale)) if any(p['style'] == 'applique' for p in selected) else 0)
    start = np.floor(low)-pad
    size = np.ceil(high-start).astype(int)+pad+1
    if size.max() > 10000 or int(size[0])*int(size[1]) > 16000000:
        raise ValueError('The piece layout is too large. Move pieces closer together or reduce their size.')
    document.set('width', f'{size[0]*scale}mm')
    document.set('height', f'{size[1]*scale}mm')
    document.set('viewBox', f'0 0 {size[0]} {size[1]}')
    mask = np.zeros((size[1], size[0]), np.uint8)
    from .region_stitches import angle_choices, hole_choices
    filled_holes = hole_choices(settings)
    chosen_angles = angle_choices(settings)
    for p in selected:
        # Remove / fill holes: only the outer outline, so stitches run across the holes.
        rings = [np.asarray(r, float)-start for r in (p['rings'][:1] if filled_holes.get(p['id']) == 'fill' else p['rings'])]
        local = np.zeros_like(mask)
        cv2.fillPoly(local, [np.rint(r).astype(np.int32) for r in rings], 1)
        if p['style'] == 'applique':
            # The appliqué satin cover is centred on the cut edge: half of it, and its mitred corners, lie outside.
            from .stitch_engine import applique_coverage
            local |= applique_coverage(rings, scale, mask.shape).astype(np.uint8)
        mask |= local
        thread = (colours or {}).get(p['colour'], {}).get('thread', p['colour'])
        node = ET.SubElement(document, 'path', id='piece-'+p['id'],
                             d=' '.join(path_data(r)+' Z' for r in rings),
                             style=f'fill:{thread};fill-rule:evenodd;stroke:none')
        # The generator's fill angle is counter-clockwise, whereas our screen
        # rotation is clockwise (positive Y down). Default fill angle is zero.
        if p['rotation']:
            node.set(NS+'angle', str(-p['rotation']))
        apply_style(document, node, rings, scale, p['style'])
        if p['id'] in chosen_angles:
            # A chosen stitch direction is absolute on the hoop, whatever the piece's rotation.
            node.set(NS+'angle', f"{float(chosen_angles[p['id']]):g}")
    display_origin = ((low+high)*scale/2).tolist()
    mask_origin = ((low+high-2*start)*scale/2).tolist()
    return len(selected), mask.astype(bool), display_origin, mask_origin
