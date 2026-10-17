"""Explicit black-ink intent; not semantic subject recognition."""
import math
import numpy as np
import xml.etree.ElementTree as ET
from .simulation import _line_art_segments


def ink_mask(rgb):
    values=rgb.astype(np.int16)
    # Retain dark antialiased neutral strokes, not saturated coloured objects.
    return (values.max(axis=2)<180)&(np.ptp(values,axis=2)<=24)


def line_settings(options):
    """App guardrails, not a promise of sewability on every fabric."""
    length=options.get("ink_length_mm",2)
    repeats=options.get("ink_bean_repeats",0)
    if type(length) not in (int,float) or not math.isfinite(length) or not .8<=length<=4:
        raise ValueError("Black-line stitch length must be between 0.8 and 4 mm.")
    if type(repeats) not in (int,float) or repeats not in (0,1):
        raise ValueError("Choose Single running or Reinforced bean for black lines.")
    return float(length),int(repeats)


def add_running_paths(document, rgb, alpha, options=None):
    length,repeats=line_settings(options or {})
    plane=np.full_like(rgb,255);plane[alpha]=0
    paths=_line_art_segments(plane)
    namespace='http://inkstitch.org/namespace'
    for index,path in enumerate(paths):
        pts=path.points
        if len(set(pts))==1:
            # Preserve isolated ink marks rather than silently dropping them.
            x,y=pts[0]
            ET.SubElement(document,'circle',id=f'ink{index}',cx=str(x),cy=str(y),r='0.5',style='fill:#000000;stroke:none')
        else:
            ET.SubElement(document,'path',id=f'ink{index}',
                d='M '+' L '.join(f'{x},{y}' for x,y in pts),
                style='fill:none;stroke:#000000;stroke-width:1',
                attrib={f'{{{namespace}}}stroke_method':'running_stitch',
                        f'{{{namespace}}}running_stitch_length_mm':f'{length:g}',
                        **({f'{{{namespace}}}bean_stitch_repeats':str(repeats)} if repeats else {})})
    return len(paths)
