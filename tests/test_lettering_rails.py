import pyembroidery as emb
from embroiderly.lettering_rails import column_shape
from embroiderly.lettering_coverage import missing_columns


def test_rung_before_curved_rails_is_not_mistaken_for_a_rail():
    rung = [(-1, 1), (3, 1)]
    left = [(0, 0), (0, 1), (.1, 2)]
    right = [(2, 0), (2, 1), (2.1, 2)]
    assert column_shape([rung, left, right]).equals(column_shape([left, right, rung]))


def test_short_crossbar_kept_even_when_rung_is_longer_than_rails():
    shape = column_shape([[(.2,-.2),(.2,1.2)],[(0,0),(.4,0)],[(0,1),(.4,1)]])
    assert abs(shape.area-.4)<1e-10


def test_written_file_missing_dot_is_reported():
    from test_lettering_native import FONT_SVG
    pattern = emb.EmbPattern()
    pattern.stitches = [[0,-20,emb.JUMP],[0,-20,0],[0,-10,0],[0,-10,emb.END]]
    issues = missing_columns(FONT_SVG, pattern)
    assert len(issues)==1 and issues[0]['column']==1
    assert issues[0]['code']=='missing_piece'
