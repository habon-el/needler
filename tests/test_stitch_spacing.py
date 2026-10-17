import math
import pyembroidery as emb
from embroiderly.stitch_spacing import repair


def pattern(points):
    p=emb.EmbPattern();p.stitches=[[x,y,emb.STITCH] for x,y in points];return p


def test_short_remainder_redistributes_on_identical_line():
    p=pattern([(17,-68),(17,-98),(17,-100),(10,-100)])
    report=repair(p,.3,7)
    assert p.stitches==[[17,-68,0],[17,-84,0],[17,-100,0],[10,-100,0]]
    assert report['straight_runs']==1 and report['removed_penetrations']==0
    assert repair(p,.3,7)['straight_runs']==0


def test_small_collinear_points_merge_but_corners_never_move():
    p=pattern([(0,0),(1,1),(2,2),(3,3),(3,4),(8,4)])
    repair(p,.3,7)
    assert p.stitches==[[0,0,0],[3,3,0],[3,4,0],[8,4,0]]
    # Genuine 0.1 mm corner remains; caller must still apply the release gate.
    assert math.dist(p.stitches[1][:2],p.stitches[2][:2])==1


def test_locks_events_duplicates_and_good_runs_are_preserved():
    p=pattern([(0,0),(2,0),(0,0),(0,0),(30,0),(60,0)])
    p.stitches.insert(4,[0,0,emb.TRIM]);before=[s[:] for s in p.stitches]
    assert repair(p,.3,7)['straight_runs']==0
    assert p.stitches==before


def test_impossible_lattice_span_is_not_changed():
    p=pattern([(0,0),(1,0),(2,0)]);before=[s[:] for s in p.stitches]
    assert repair(p,.3,7)['straight_runs']==0 and p.stitches==before
