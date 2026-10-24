"""Alternative for short, path-following locks on authored font underpaths.

Custom mm locks follow an existing path and can be shortened on a
tiny route. Its documented custom SVG form instead defines an explicit 0.6 mm
retracing pattern; the last segment supplies orientation and is not stitched.
https://inkstitch.org/docs/stitches/lock-stitches/

This only edits our own known lock attributes. Letter outlines, rungs, underlay
and stitch spacing are untouched. A caller MUST regenerate and verify both
written files against the original source envelope before accepting it.
"""
import xml.etree.ElementTree as ET
from .lettering_geometry import INK, SVG

LOCK_PATH = 'M 0,0 L 0.6,0 L 0,0 L 0.6,0 L 0,0 L 0.6,0'


def explicit_locks(svg):
    root = ET.fromstring(svg)
    changes = 0
    for node in root.iter(SVG+'path'):
        for end in ('start', 'end'):
            if (node.get(INK+'lock_'+end) == 'custom' and
                    node.get(INK+'lock_custom_'+end) == '1 -1 1 -1' and
                    node.get(INK+'lock_'+end+'_scale_mm') == '0.6'):
                node.set(INK+'lock_custom_'+end, LOCK_PATH)
                node.set(INK+'lock_'+end+'_scale_percent', '100')
                changes += 1
    return ET.tostring(root, encoding='unicode'), changes
