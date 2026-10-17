"""Regenerate our four-point end locks by retracing the last sewn segment.

Only used with generation_policy's custom 1 -1 1 -1 end lock. No lock is
deleted or exempted from readback checks. Never invent travel into empty fabric.
"""
import math
import pyembroidery as emb
from .knockout_routing import RemovedPixels


def repair(pattern,alpha,scale,origin):
    mask=RemovedPixels(alpha,scale,origin)
    report={'end_locks_rebuilt':0,'largest_endpoint_change_mm':0.0}
    points=pattern.stitches
    for i in range(len(points)-1,5,-1):
        if points[i][2]!=emb.TRIM:continue
        block=points[i-5:i]
        if any(p[2]!=emb.STITCH for p in block) or points[i-6][2]!=emb.STITCH:continue
        if not any(0<math.dist(a[:2],b[:2])<3-1e-8 for a,b in zip(block,block[1:])):continue
        end=block[0][:2];prior=points[i-6][:2];distance=math.dist(end,prior)
        if distance<3 or distance>70:continue
        anchor=[round(end[k]+(prior[k]-end[k])*min(1,6/distance)) for k in (0,1)]
        length=math.dist(end,anchor)
        if not 3<=length<=70 or mask.crosses(end,anchor):continue
        shift=math.dist(points[i][:2],end)/10
        if shift>.45+1e-8:
            original_end=points[i][:2]
            if not 3<=math.dist(end,original_end)<=70 or mask.crosses(end,original_end):continue
            anchor=end;end=original_end;shift=0.0
        points[i-4:i]=[[*anchor,emb.STITCH],[*end,emb.STITCH],
                       [*anchor,emb.STITCH],[*end,emb.STITCH]]
        points[i][:2]=end
        report['end_locks_rebuilt']+=1
        report['largest_endpoint_change_mm']=max(report['largest_endpoint_change_mm'],shift)
    from .start_lock_repair import repair as repair_start
    report.update(repair_start(pattern, alpha, scale, origin))
    return report
