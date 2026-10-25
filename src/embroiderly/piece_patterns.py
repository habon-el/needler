"""Repeat a selection: a mirrored copy beside it, copies around a circle, or rows and columns.

Every copy is a duplicate piece ({'source', 'matrix', 'rotation', 'name'}, plus the outline of a
cut part), exactly like the Duplicate command, so it can be moved, styled or deleted on its own.
Operations work in millimetres on the hoop (positive Y down) and act on the selection as a group:
its outline bounding box gives the edges, the centre and the step. The selection stays where it
is and counts as the first item of a circle or array.
"""
import hashlib
import math

import numpy as np

COMMANDS = ('mirror_copy', 'circle', 'array')
MAX_CIRCLE = 36       # items around one circle, the selection included
MAX_ROWS = 20         # rows or columns of one array
MAX_RADIUS_MM = 500
MAX_GAP_MM = 100


def whole(value, low, high, message):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(message)
    return value


def number(value, low, high, message):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(message)
    return float(value)


def placements(field, value, box):
    """The copies to add, as (3×3 operation in mm, rotation change in degrees, mirrored)."""
    left, top, right, bottom = box
    cx, cy = (left+right)/2, (top+bottom)/2
    if field == 'mirror_copy':
        # Reflect across the right edge (x) or the bottom edge (y): the copy touches the original,
        # as a half drawing reflected into a whole one.
        if value not in ('x', 'y'):
            raise ValueError('Mirror copy left-right (x) or top-bottom (y).')
        if value == 'x':
            return [(np.array([[-1, 0, 2*right], [0, 1, 0], [0, 0, 1.]]), 0, True)]
        return [(np.array([[1, 0, 0], [0, -1, 2*bottom], [0, 0, 1.]]), 0, True)]
    if field == 'circle':
        if not isinstance(value, dict) or set(value) != {'count', 'radius_mm', 'turn'} or type(value['turn']) is not bool:
            raise ValueError('Enter how many around the circle, its radius and whether to turn them.')
        count = whole(value['count'], 2, MAX_CIRCLE, f'Use 2 to {MAX_CIRCLE} around a circle.')
        radius = number(value['radius_mm'], 1, MAX_RADIUS_MM, f'The circle radius must be 1–{MAX_RADIUS_MM} mm.')
        # The selection sits at the top of the circle; copies follow clockwise, like a clock.
        ox, oy = cx, cy+radius
        result = []
        for k in range(1, count):
            degrees = 360*k/count
            c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
            if value['turn']:
                # Wreath: each copy turns with the circle, so it faces outward like the first.
                op = np.array([[c, -s, ox-c*ox+s*oy], [s, c, oy-s*ox-c*oy], [0, 0, 1.]])
            else:
                # Upright: the copy only moves to its place on the circle.
                dx, dy = cx-ox, cy-oy
                op = np.array([[1, 0, ox+c*dx-s*dy-cx], [0, 1, oy+s*dx+c*dy-cy], [0, 0, 1.]])
            result.append((op, degrees if value['turn'] else 0, False))
        return result
    if field == 'array':
        if not isinstance(value, dict) or set(value) != {'rows', 'columns', 'gap_mm'}:
            raise ValueError('Enter the rows, columns and the gap between them.')
        rows = whole(value['rows'], 1, MAX_ROWS, f'Use 1 to {MAX_ROWS} rows.')
        columns = whole(value['columns'], 1, MAX_ROWS, f'Use 1 to {MAX_ROWS} columns.')
        gap = number(value['gap_mm'], 0, MAX_GAP_MM, f'The gap must be 0–{MAX_GAP_MM} mm.')
        if rows*columns < 2:
            raise ValueError('Use more than one row or column.')
        # Rows go down and columns go right from the selection, one size plus the gap apart.
        step_x, step_y = right-left+gap, bottom-top+gap
        return [(np.array([[1, 0, j*step_x], [0, 1, i*step_y], [0, 0, 1.]]), 0, False)
                for i in range(rows) for j in range(columns) if i or j]
    raise ValueError('Unsupported piece property.')


def repeat(updated, selected, field, value, existing):
    """Add the copies to updated options (a deep copy); `existing` is the count of copies already saved."""
    from .piece_layout import IDENTITY, MAX_COPIES, bounds, matrix, packed
    places = placements(field, value, bounds([r for p in selected for r in p['rings_mm']]))
    added = len(places)*len(selected)
    if existing+added > MAX_COPIES:
        raise ValueError(f'That adds {added} copies; a design holds at most {MAX_COPIES} copied pieces '
                         f'({MAX_COPIES-existing} more). Use fewer, or delete some copies first.')
    stored = updated.setdefault('piece_edits', {})
    styles = updated.get('region_styles', {})
    for p in selected:
        base = stored.get(p['id'], {})
        original = base.get('source', p['id'])
        current = matrix(base.get('matrix', IDENTITY))
        for index, (op, turn, mirrored) in enumerate(places, 1):
            n = 0
            while True:
                key = hashlib.sha256(f'{original}:{n}'.encode()).hexdigest()[:20]
                if key not in stored:
                    break
                n += 1
            rotation = (-p['rotation'] if mirrored else p['rotation']+turn) % 360
            label = ' mirror' if field == 'mirror_copy' else f' {index+1}'
            stored[key] = {'source': original, 'matrix': packed(op @ current), 'rotation': rotation,
                           'name': (p['name']+label)[:100], **({'rings': base['rings']} if 'rings' in base else {})}
            if styles.get(p['id']):
                updated.setdefault('region_styles', {})[key] = styles[p['id']]
    return updated
