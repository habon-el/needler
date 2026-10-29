"""Measured, reversible decisions for automatic cleanup; source data stays immutable."""
import hashlib
import json
import cv2
import numpy as np


# Changes no larger than about half a thread width cannot be seen in stitches.
# They are recorded as 'auto' (still reversible with 'keep'), not asked about.
AUTO_ACCEPT_MM=.25
# One choice covers every cleanup change. Automatic lets specks under two thread
# widths go and keeps anything larger as drawn; 'review' asks about each one.
AUTO_DROP_MM=.8
CHOICES=('auto','keep','drop','review')


def cleanup_choice(options):
    """The one cleanup choice; designs saved with per-detail decisions map to the nearest."""
    choice=options.get('cleanup_choice')
    if choice is not None:
        if choice not in CHOICES:raise ValueError('Invalid cleanup choice.')
        return choice
    values=set((options.get('cleanup_decisions') or {}).values()) if isinstance(options.get('cleanup_decisions'),dict) else set()
    return values.pop() if len(values)==1 else 'auto'


def review_changes(before, after, options, scale, stage):
    decisions=options.get('cleanup_decisions',{})
    if not isinstance(decisions,dict) or len(decisions)>10000 or any(
        not isinstance(k,str) or v not in ('keep','drop') for k,v in decisions.items()):
        raise ValueError('Invalid cleanup decisions.')
    choice=cleanup_choice(options)
    changed=before!=after
    if changed.ndim==3:changed=np.any(changed,axis=2)
    n,labels,stats,_=cv2.connectedComponentsWithStats(changed.astype('uint8'),8)
    output=after.copy();records=[]
    for i in range(1,n):
        x,y,w,h,area=map(int,stats[i]);region=labels==i
        identity=hashlib.sha256(json.dumps([stage,x,y,w,h,scale],sort_keys=True).encode()+
                                np.packbits(region[y:y+h,x:x+w]).tobytes()+
                                before[region].tobytes()+after[region].tobytes()).hexdigest()[:24]
        size=max(w,h)*scale
        if identity in decisions:decision=decisions[identity]
        elif size<=AUTO_ACCEPT_MM+1e-9:decision='auto'
        elif choice=='auto':decision='auto' if size<AUTO_DROP_MM else 'keep'
        else:decision='pending' if choice=='review' else choice
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
