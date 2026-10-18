"""Fast unique colours: identical results to np.unique(rows, axis=0).

Rows of up to three 0–255 values are packed into one integer, which keeps the
same lexicographic order. Anything else falls back to numpy's row unique.
"""
import numpy as np


def unique_rows(rows, return_inverse=False, return_counts=False):
    rows = np.asarray(rows)
    packable = (rows.ndim == 2 and 1 <= rows.shape[1] <= 3 and rows.dtype.kind in 'iu'
                and (rows.size == 0 or (rows.min() >= 0 and rows.max() <= 255)))
    if not packable:
        return np.unique(rows, axis=0, return_inverse=return_inverse, return_counts=return_counts)
    width = rows.shape[1]
    keys = np.zeros(len(rows), np.uint32)
    for column in range(width):
        keys = (keys << np.uint32(8)) | rows[:, column].astype(np.uint32)
    result = np.unique(keys, return_inverse=return_inverse, return_counts=return_counts)
    packed = result[0] if isinstance(result, tuple) else result
    values = np.empty((len(packed), width), rows.dtype)
    for column in range(width):
        values[:, column] = (packed >> np.uint32(8*(width-1-column))) & np.uint32(255)
    if not isinstance(result, tuple):
        return values
    extra = list(result[1:])
    if return_inverse:
        extra[0] = extra[0].reshape(-1)
    return (values, *extra)
