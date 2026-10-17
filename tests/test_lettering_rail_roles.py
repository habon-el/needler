from embroiderly.lettering_rails import column_shape


def test_curved_rails_are_not_misread_as_bent_rungs():
    outer = [(3, 0), (0, 0), (0, 4), (3, 4)]
    inner = [(3, 1), (1, 1), (1, 3), (3, 3)]
    top = [(2, -.2), (2, 1.2)]
    bottom = [(2, 2.8), (2, 4.2)]
    assert column_shape([outer, inner, top, bottom]).equals(column_shape([outer, inner]))
