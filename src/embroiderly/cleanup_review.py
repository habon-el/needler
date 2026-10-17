"""Measured, reversible decisions for automatic cleanup; source data stays immutable."""
import hashlib
import json
import cv2
import numpy as np


def review_changes(before, after, options, scale, stage):
    decisions=options.get('cleanup_decisions',{})
    if not isinstance(decisions,dict) or len(decisions)>10000 or any(
        not isinstance(k,str) or v not in ('keep','drop') for k,v in decisions.items()):
        raise ValueError('Invalid cleanup decisions.')
    changed=before!=after
    if changed.ndim==3:changed=np.any(changed,axis=2)
    n,labels,stats,_=cv2.connectedComponentsWithStats(changed.astype('uint8'),8)
    output=after.copy();records=[]
    for i in range(1,n):
        x,y,w,h,area=map(int,stats[i]);region=labels==i
        identity=hashlib.sha256(json.dumps([stage,x,y,w,h,scale],sort_keys=True).encode()+
                                np.packbits(region[y:y+h,x:x+w]).tobytes()+
                                before[region].tobytes()+after[region].tobytes()).hexdigest()[:24]
        decision=decisions.get(identity,'pending')
        if decision=='keep':output[region]=before[region]
        records.append(dict(id=identity,stage=stage,bounds=[x,y,x+w,y+h],pixels=area,
                            width_mm=round(w*scale,4),height_mm=round(h*scale,4),
                            area_mm2=round(area*scale*scale,6),decision=decision,
                            removed=decision!='keep'))
    return output,records


def require_review(report):
    pending=[r for r in report.get('cleanup_review',[]) if r['decision']=='pending']
    if pending:
        first=pending[0]
        raise ValueError(f"Review cleanup before approving: {len(pending)} details need Keep it or Let it go; "
                         f"first is {first['width_mm']:g} × {first['height_mm']:g} mm at image bounds {first['bounds']}.")
