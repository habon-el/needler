"""Line up several pieces: align their edges or centres, space them evenly, give them one size.

Pieces are measured by their outline bounding box in mm, like the Width and Height fields.
Each piece gets its own move or resize matrix on top of its saved one, exactly as a position
or width edit would, so stitches rebuild from the moved outline.
"""
import numpy as np

from .piece_layout import IDENTITY, bounds, edits, matrix, packed

ALIGN = ('left', 'centre', 'right', 'top', 'middle', 'bottom')
DISTRIBUTE = ('across', 'down')
MATCH = ('width', 'height', 'both')
SMALLEST_MM = .1   # a piece thinner than this (a straight line) has no width or height to match


def box(piece):
    return bounds(piece['rings_mm'])


def move(dx, dy):
    return np.array([[1, 0, dx], [0, 1, dy], [0, 0, 1.]])


def resize(sx, sy, cx, cy):
    # Grows or shrinks around the piece's own centre, so it stays where it was.
    return np.array([[sx, 0, cx*(1-sx)], [0, sy, cy*(1-sy)], [0, 0, 1.]])


def align(pieces, value):
    left, top, right, bottom = bounds([r for p in pieces for r in p['rings_mm']])
    ops = {}
    for p in pieces:
        l, t, r, b = box(p)
        dx = {'left': left-l, 'right': right-r, 'centre': (left+right-l-r)/2}.get(value, 0)
        dy = {'top': top-t, 'bottom': bottom-b, 'middle': (top+bottom-t-b)/2}.get(value, 0)
        ops[p['id']] = move(dx, dy)
    return ops


def distribute(pieces, value):
    # The two outer pieces stay put; the ones between move so every gap is the same.
    axis = 0 if value == 'across' else 1
    order = sorted(pieces, key=lambda p: (box(p)[axis]+box(p)[axis+2])/2)
    start, end = box(order[0])[axis], box(order[-1])[axis+2]
    sizes = [box(p)[axis+2]-box(p)[axis] for p in order]
    gap = (end-start-sum(sizes))/(len(order)-1)
    ops, at = {}, start
    for p, size in zip(order, sizes):
        shift = at-box(p)[axis]
        ops[p['id']] = move(shift, 0) if axis == 0 else move(0, shift)
        at += size+gap
    return ops


def match_size(pieces, value):
    # The first piece picked sets the size. Same width or height keeps each piece's proportions;
    # Same size gives every piece exactly the first one's width and height.
    l, t, r, b = box(pieces[0])
    width, height = r-l, b-t
    ops = {}
    for p in pieces[1:]:
        l, t, r, b = box(p)
        w, h = r-l, b-t
        if (value != 'height' and min(w, width) < SMALLEST_MM) or (value != 'width' and min(h, height) < SMALLEST_MM):
            raise ValueError('A straight line has no width or height to match. Leave it out of the selection.')
        sx = width/w if value != 'height' else height/h
        sy = height/h if value != 'width' else width/w
        if max(w*sx, h*sy) > 1000:
            raise ValueError('Size must be between 0.1 and 1000 mm.')
        ops[p['id']] = resize(sx, sy, (l+r)/2, (t+b)/2)
    return ops


def arrange(updated, pieces, field, value):
    """Apply align / distribute / match_size to the selected pieces, given in the order they were picked."""
    choices = {'align': ALIGN, 'distribute': DISTRIBUTE, 'match_size': MATCH}[field]
    if value not in choices:
        raise ValueError('Choose ' + ', '.join(choices) + '.')
    if len(pieces) < (3 if field == 'distribute' else 2):
        raise ValueError('Select at least three pieces to space them evenly.' if field == 'distribute'
                         else 'Select at least two pieces.')
    ops = {'align': align, 'distribute': distribute, 'match_size': match_size}[field](pieces, value)
    stored = updated.setdefault('piece_edits', {})
    for key, op in ops.items():
        item = stored.setdefault(key, {})
        item['matrix'] = packed(op @ matrix(item.get('matrix', IDENTITY)))
    edits(updated)
    return updated
