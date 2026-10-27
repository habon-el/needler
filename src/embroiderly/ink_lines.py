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
    if type(repeats) not in (int,float) or repeats not in (0,1,REDWORK):
        raise ValueError("Choose Single running, Reinforced bean or Redwork for black lines.")
    return float(length),int(repeats)


REDWORK=2   # ink_bean_repeats value for Redwork: every line twice, one route per drawing


def redwork_routes(lines):
    """Every line sewn exactly twice, once each way, as one closed route per connected
    drawing: start and end at the same point with no cut inside a drawing. Line ends
    within three pixels of each other (a skeleton junction is a small cluster, and traced
    lines keep every third pixel) count as meeting; so does a line end beside the middle
    of another line, which is split there."""
    near=range(-3,4)
    def cell(p):return round(p[0]),round(p[1])
    ends={cell(p) for pts in lines for p in (pts[0],pts[-1])}
    pieces=[]
    for pts in lines:
        piece=[pts[0]]
        for p in pts[1:-1]:
            piece.append(p)
            x,y=cell(p)
            if any((x+dx,y+dy) in ends for dx in near for dy in near):pieces.append(piece);piece=[p]
        pieces.append(piece+[pts[-1]])
    lines=pieces
    parent={}
    def find(c):
        while parent[c]!=c:parent[c]=parent[parent[c]];c=parent[c]
        return c
    cells=[cell(p) for pts in lines for p in (pts[0],pts[-1])]
    for c in cells:parent.setdefault(c,c)
    for x,y in parent.copy():
        for dx in near:
            for dy in near:
                if (x+dx,y+dy) in parent:parent[find((x+dx,y+dy))]=find((x,y))
    out={}
    for i in range(len(lines)):
        u,v=find(cells[2*i]),find(cells[2*i+1])
        out.setdefault(u,[]).append((v,i,False));out.setdefault(v,[]).append((u,i,True))
    routes=[]
    for start in list(out):
        if not out[start]:continue
        # Hierholzer: walk on, never straight back along the same line while another way exists.
        stack,arcs=[(start,None)],[]
        while stack:
            v,arc=stack[-1]
            if out[v]:
                k=next((k for k,a in enumerate(out[v]) if arc is None or a[1]!=arc[1]),0)
                a=out[v].pop(k);stack.append((a[0],a))
            else:
                stack.pop()
                if arc is not None:arcs.append(arc)
        route=[]
        for _,i,back in reversed(arcs):
            for p in (lines[i][::-1] if back else lines[i]):
                if not route or route[-1]!=p:route.append(p)
        routes.append(route)
    return routes


def add_running_paths(document, rgb, alpha, options=None):
    length,repeats=line_settings(options or {})
    plane=np.full_like(rgb,255);plane[alpha]=0
    paths=_line_art_segments(plane)
    namespace='http://inkstitch.org/namespace'
    if repeats==REDWORK:
        dots=[p for p in paths if len(set(p.points))==1]
        routes=redwork_routes([p.points for p in paths if len(set(p.points))>1])
        for index,pts in enumerate(routes):
            # No simplifying: both passes must keep the same holes.
            ET.SubElement(document,'path',id=f'ink{index}',d='M '+' L '.join(f'{x},{y}' for x,y in pts),
                style='fill:none;stroke:#000000;stroke-width:1',
                attrib={f'{{{namespace}}}stroke_method':'running_stitch',
                        f'{{{namespace}}}running_stitch_length_mm':f'{length:g}',
                        f'{{{namespace}}}running_stitch_tolerance_mm':'0'})
        for index,p in enumerate(dots):
            x,y=p.points[0]
            ET.SubElement(document,'circle',id=f'inkdot{index}',cx=str(x),cy=str(y),r='0.5',style='fill:#000000;stroke:none')
        return len(routes)+len(dots)
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
