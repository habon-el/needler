"""Bounded, deterministic machine-grid proposals; no unsafe partial auto-apply.

First five/final four ordinary stitches around events are reserved for our
configured four-point lock plus initial penetration. Unknown event patterns
are protected conservatively. A rule cannot delete command boundaries.
"""
import math
import pyembroidery as emb
from .knockout_routing import RemovedPixels

RULES=({'id':'short-span','fixes':'short sewn segments','max_move_mm':.45,
        'max_outline_deviation_mm':.2,'passes':32,
        'ask_when':'locked piece, remaining violation, or tolerance exceeded'},)


def propose(pattern,alpha,scale,origin,locked=False):
    from .export_findings import inspect
    rule=RULES[0];candidate=pattern.copy()
    source=[[round(x),round(y),c] for x,y,c in pattern.stitches]
    points=[(i,s) for i,s in enumerate(source)]
    protected=set();start=0
    for end in range(len(source)+1):
        if end==len(source) or source[end][2]!=emb.STITCH:
            ids=list(range(start,end))
            protected.update(ids[:5]);protected.update(ids[-4:]);start=end+1
    mask=RemovedPixels(alpha,scale,origin);changes=[]
    if not locked:
        for _ in range(rule['passes']):
            changed=False
            for j in range(1,len(points)-1):
                index,b=points[j];a=points[j-1][1];c=points[j+1][1]
                if index in protected or any(s[2]!=emb.STITCH for s in (a,b,c)):continue
                ab=math.dist(a[:2],b[:2]);bc=math.dist(b[:2],c[:2])
                if not (0<ab<3-1e-8 or 0<bc<3-1e-8):continue
                ac=math.dist(a[:2],c[:2])
                if not 3-1e-8<=ac<=70+1e-8:continue
                t=max(0,min(1,sum((b[k]-a[k])*(c[k]-a[k]) for k in (0,1))/(ac*ac)))
                deviation=math.dist(b[:2],[a[k]+t*(c[k]-a[k]) for k in (0,1)])/10
                move=min(ab,bc)/10
                if deviation>.2+1e-8 or move>.45+1e-8 or mask.crosses(a[:2],c[:2]):continue
                changes.append(dict(command=index,point=b[:2],move_mm=move,deviation_mm=deviation))
                del points[j];changed=True;break
            if not changed:break
    candidate.stitches=[s for _,s in points]
    issues=inspect(candidate,alpha,scale,origin)
    automatic=not locked and not issues
    return candidate,dict(rule='short-span',automatic=automatic,needs_approval=not automatic,
                         changes=changes,issues=issues,
                         largest_move_mm=max((c['move_mm'] for c in changes),default=0),
                         locked=locked)
