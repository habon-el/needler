"""Removed-area routing must use the coordinates a machine file can store."""
import numpy as np
import pyembroidery as emb
from embroiderly.knockout_routing import protect, verify
from embroiderly.machine_files import write_pair, read_pattern


def test_rounding_cannot_turn_safe_float_segment_into_sewn_hole(tmp_path):
    mask = np.ones((40, 40), bool)
    mask[12:25, 12:25] = False
    p = emb.EmbPattern()
    p.add_thread('#000000')
    p.stitches = [[1, 3, emb.JUMP], [1, 3, emb.STITCH],
                  [2.0219616512659027, 3.56127617277589, emb.STITCH],
                  [4.733401472946725, 9.424907368116589, emb.STITCH],
                  [8, 10, emb.STITCH], [8, 10, emb.END]]
    # Float geometry skirts the hole; 0.1 mm serialization moves it into it.
    verify(p, mask, .03, [0, 0])
    protect(p, mask, .03, [0, 0])
    write_pair(p, tmp_path/'design.pes', tmp_path/'design.dst')
    for fmt in ('pes', 'dst'):
        decoded = read_pattern(tmp_path/('design.'+fmt))
        verify(decoded, mask, .03, [0, 0])
        assert decoded.count_stitch_commands(emb.TRIM) >= 1
