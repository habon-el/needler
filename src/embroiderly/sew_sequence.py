"""Sewing order by hand: the parts named in `sew_sequence` are sewn in that order. A part not
named (a new or redrawn part) keeps its automatic place, right after the part sewn before it.
Shared by the colour generator (engine.py) and the piece path (piece_generation.py)."""
import re

MAX_PARTS = 2000


def choices(options):
    """The saved order: a list of part ids, checked. Empty means automatic."""
    value = options.get('sew_sequence', [])
    if not isinstance(value, list) or len(value) > MAX_PARTS:
        raise ValueError(f'Expected a sewing order of at most {MAX_PARTS} parts.')
    if any(not isinstance(key, str) or not re.fullmatch('[a-f0-9]{20}', key) for key in value) or len(set(value)) != len(value):
        raise ValueError('Invalid sewing order. Choose Automatic order and try again.')
    return value


def arrange(ids, sequence):
    """Positions of `ids` (in automatic order; None for unnamed bits) in the order to sew them."""
    rank = {key: n for n, key in enumerate(sequence)}
    keys, last = [], -1
    for position, key in enumerate(ids):
        if key in rank:
            last = rank[key]
            keys.append((last, 0, position))
        else:
            keys.append((last, 1, position))
    return sorted(range(len(ids)), key=keys.__getitem__)
