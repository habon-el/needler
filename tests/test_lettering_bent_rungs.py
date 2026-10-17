"""Authored satin rungs may be polylines, not just two-point segments."""
import pytest
from embroiderly.lettering_rails import column_shape


def test_bent_rung_keeps_original_rails_and_area():
    left = [(0, 0), (0, 1), (.1, 2)]
    right = [(2, 0), (2, 1), (2.1, 2)]
    rung = [(-.2, .8), (-.1, 1), (2.2, 1)]
    expected = column_shape([left, right])
    assert column_shape([rung, left, right]).equals(expected)
    assert column_shape([right, rung, left]).equals(expected)


def test_nonconnecting_bent_rung_still_fails_closed():
    with pytest.raises(ValueError, match='ambiguous'):
        column_shape([[(0, 0), (0, 2)], [(2, 0), (2, 2)],
                      [(-1, 3), (1, 4), (3, 3)]])
