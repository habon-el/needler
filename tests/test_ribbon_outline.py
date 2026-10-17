from shapely.geometry import Point
from embroiderly.ribbon_outline import winding_interior


def test_overlap_is_retained_without_filling_the_bounding_box():
    # Two overlapping, equally directed squares joined by a retraced segment.
    path = [(0,0),(2,0),(2,2),(0,2),(0,0),
            (1,1),(3,1),(3,3),(1,3),(1,1),(0,0)]
    shape = winding_interior(path)
    assert shape.is_valid and shape.area == 7
    assert shape.covers(Point(1.5,1.5))
    assert not shape.covers(Point(2.5,.5))


def test_counter_stays_open_and_orientation_does_not_change_coverage():
    path = [(0,0),(4,0),(4,4),(0,4),(0,0),
            (1,1),(1,3),(3,3),(3,1),(1,1),(0,0)]
    shape = winding_interior(path)
    assert shape.is_valid and shape.area == 12
    assert not shape.covers(Point(2,2))
    assert shape.equals(winding_interior(path[::-1]))
