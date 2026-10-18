"""Collect all machine-path violations without altering the audited commands."""
import math
from collections import Counter
import pyembroidery as emb
from .knockout_routing import RemovedPixels


def inspect(pattern, alpha, scale, origin):
    from .release_gate import MIN_STITCH_MM, MAX_STITCH_MM, MAX_UNCUT_TRAVEL_MM
    mask=RemovedPixels(alpha,scale,origin)
    previous=[0.,0.];needle=None;attached=False;travel=0.;sewn=0;issues=[]
    def add(code,reason,point,index):
        location=None if point is None else dict(x_mm=round(point[0]/10,3),y_mm=round(point[1]/10,3),command=index)
        issues.append(dict(code=code,reason=reason,location=location))
    for index,(x,y,flags) in enumerate(pattern.stitches):
        point=[x,y];kind=flags&emb.COMMAND_MASK
        if not all(math.isfinite(v) for v in point):
            add('invalid','invalid machine coordinates',None,index)
            attached=False;needle=None;travel=0.;continue
        length=math.dist(previous,point)/10
        if kind==emb.STITCH:
            start=needle if attached else previous
            length=math.dist(start,point)/10
            if length>1e-8 and not MIN_STITCH_MM-1e-8<=length<=MAX_STITCH_MM+1e-8:
                add('short' if length<MIN_STITCH_MM else 'long',f'stitch length {length:.2f} mm is outside 0.3–7 mm',point,index)
            if mask.crosses(point,point) or (length>1e-8 and attached and mask.crosses(start,point)):
                add('crossing','a stitch crosses a removed area',point,index)
            attached=True;needle=point;travel=0.;sewn+=1
        elif kind==emb.JUMP and attached:
            travel+=length
            if mask.crosses(needle,point) or mask.crosses(previous,point) or travel>MAX_UNCUT_TRAVEL_MM+1e-8:
                add('travel','an uncut travel thread crosses empty fabric or exceeds 6 mm',point,index)
        elif kind in (emb.TRIM,emb.COLOR_CHANGE,emb.NEEDLE_SET,emb.END):
            attached=False;needle=None;travel=0.
        elif kind not in (emb.JUMP,emb.STOP):
            add('unsupported','unsupported machine command',point,index)
        previous=point
    if not sewn:add('empty','the file contains no stitches',None,None)
    return issues


def summary(issues):
    labels={'short':'stitches too short','long':'stitches too long',
            'missing_piece':'font strokes or marks missing',
            'crossing':'stitches cross empty areas','travel':'unsafe uncut travels',
            'invalid':'invalid coordinates','unsupported':'unsupported commands','empty':'empty files'}
    counts=Counter(i['code'] for i in issues)
    return ' · '.join(f'{count} {labels.get(code,code)}' for code,count in counts.items())
