"""Collect all machine-path violations without altering the audited commands."""
import json
import math
from collections import Counter
import pyembroidery as emb
from .knockout_routing import RemovedPixels


def inspect(pattern, alpha, scale, origin):
    from .release_gate import MIN_STITCH_MM, MAX_STITCH_MM, MAX_UNCUT_TRAVEL_MM
    mask=RemovedPixels(alpha,scale,origin)
    previous=[0.,0.];needle=None;attached=False;travel=0.;sewn=0;issues=[]
    # Mask checks are collected and answered in one batch (crosses_many);
    # an issue waiting on them keeps its place in the list.
    segments=[]
    def add(code,reason,point,index,checks=(),always=True):
        location=None if point is None else dict(x_mm=round(point[0]/10,3),y_mm=round(point[1]/10,3),command=index)
        issues.append((dict(code=code,reason=reason,location=location),range(len(segments),len(segments)+len(checks)),always))
        segments.extend(checks)
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
            add('crossing','a stitch crosses a removed area',point,index,
                [(point,point)]+([(start,point)] if length>1e-8 and attached else []),False)
            attached=True;needle=point;travel=0.;sewn+=1
        elif kind==emb.JUMP and attached:
            travel+=length
            add('travel','an uncut travel thread crosses empty fabric or exceeds 6 mm',point,index,
                [(needle,point),(previous,point)],travel>MAX_UNCUT_TRAVEL_MM+1e-8)
        elif kind in (emb.TRIM,emb.COLOR_CHANGE,emb.NEEDLE_SET,emb.END):
            attached=False;needle=None;travel=0.
        elif kind not in (emb.JUMP,emb.STOP):
            add('unsupported','unsupported machine command',point,index)
        previous=point
    if not sewn:add('empty','the file contains no stitches',None,None)
    hits=mask.crosses_many(segments)
    return [issue for issue,checks,always in issues if always or any(hits[i] for i in checks)]


def summary(issues):
    labels={'short':'stitches too short','long':'stitches too long',
            'missing_piece':'font strokes or marks missing',
            'crossing':'stitches cross empty areas','travel':'unsafe uncut travels',
            'invalid':'invalid coordinates','unsupported':'unsupported commands','empty':'empty files'}
    counts=Counter(i['code'] for i in issues)
    return ' · '.join(f'{count} {labels.get(code,code)}' for code,count in counts.items())


EDGE_MM=1.0   # a finding this close to the picture's edge counts as "on the edge"


def explain(issues, pattern, shape, scale, origin):
    """The findings grouped by cause, for the person and for Claude: which thread, and
    whether on the picture's edge or inside it. One coordinate says where the first bad
    stitch is; the groups say what to change. signature is the same for the same failure
    on the next attempt (auto_claude stops retrying one that comes back unchanged)."""
    threads=[t.hex_color() for t in pattern.threadlist]
    block=[];colour=0
    for x,y,flags in pattern.stitches:
        block.append(colour)
        if flags&emb.COMMAND_MASK==emb.COLOR_CHANGE:colour+=1
    # Picture frame in machine millimetres (inspect() maps mm to pixels as (mm+origin)/scale).
    left,top=-origin[0],-origin[1]
    right,bottom=(shape[1]-1)*scale-origin[0],(shape[0]-1)*scale-origin[1]
    groups=Counter()
    for issue in issues:
        location=issue['location']
        if issue['code'] not in ('crossing','travel') or location is None:
            groups[(issue['code'],None,None)]+=1;continue
        index=location['command']
        # Both ends: a satin stitch failing at the edge often ends a few millimetres inside.
        ends=[(location['x_mm'],location['y_mm'])]
        if index:ends.append((pattern.stitches[index-1][0]/10,pattern.stitches[index-1][1]/10))
        edge=min(min(x-left,right-x,y-top,bottom-y) for x,y in ends)<=EDGE_MM
        thread=threads[block[index]] if index is not None and block[index]<len(threads) else None
        groups[(issue['code'],thread,'edge' if edge else 'inside')]+=1
    rows=[dict(code=c,thread=t,where=w,count=n) for (c,t,w),n in sorted(groups.items(),key=lambda g:-g[1])]
    placed=[r for r in rows if r['where']]
    on_edge=sum(r['count'] for r in placed if r['where']=='edge');inside=sum(r['count'] for r in placed if r['where']=='inside')
    parts=[f"{r['count']} {r['code']} in thread {r['thread'] or '?'} {'on the picture edge' if r['where']=='edge' else 'inside the picture'}" for r in placed[:6]]
    parts+=[f"{r['count']} {r['code']}" for r in rows if not r['where']]
    if placed and not inside:
        cause='edge'
        hint=('All of them are on the picture\'s edge: stitches reach past the edge of the picture. '
              'Colours, detail and density inside the picture will not change this; change what is sewn along '
              'the edge (border, outline, the areas that touch the edge) or stitch the subject only.')
    elif placed and not on_edge and len({r['thread'] for r in placed})==1:
        cause='one_thread'
        hint=f"All of them are in thread {placed[0]['thread']}, inside the picture: change how that colour is sewn."
    elif placed:
        cause='mixed'
        hint='They are spread over several threads; look at the largest group first.'
    else:
        cause='other';hint=''
    text=summary(issues)+': '+'; '.join(parts)+'.'+(' '+hint if hint else '')
    signature=sorted((r['code'],r['thread'],r['where']) for r in rows)
    return dict(groups=rows,cause=cause,text=text,signature=json.dumps(signature))
