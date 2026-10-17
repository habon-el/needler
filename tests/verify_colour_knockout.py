"""Actual Big thanks artwork and PES readback, not a synthetic sew-out claim."""
import hashlib
import json
import time
from pathlib import Path
import cv2
import numpy as np
from embroiderly.preparation import prepare,load_image
from embroiderly.colour_knockout import proposal_patch
from embroiderly.engine import digitize

ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'work/uploads/e2742318856746e2b8a749b2dcecdf15.webp'
out=ROOT/'outputs/colour-knockout';out.mkdir(exist_ok=True)
before=hashlib.sha256(source.read_bytes()).hexdigest()
options={'height_mm':100,'count':2,**proposal_patch(load_image(source),{})}
image,palette,report=prepare(source,options)
repeated,_,_=prepare(source,options)
assert image.tobytes()==repeated.tobytes()
image.save(out/'big-thanks-prepared.png')
(out/'big-thanks-prepared.prep.json').write_text(json.dumps({'options':options,'report':report}))
t=time.perf_counter();payload=digitize(out/'big-thanks-prepared.png',out/'export',100);elapsed=time.perf_counter()-t
alpha=np.asarray(image)[:,:,3]>127
core=cv2.erode((~alpha).astype(np.uint8),np.ones((3,3),np.uint8))>0
scale=100/image.height;origin=np.array(payload['origin_mm'])
sewn=[];loose=[];prior=np.zeros(2);thread=False
for index,step in enumerate(payload['steps']):
    point=np.array([step['x'],step['y']]);kind=step['t']
    a=(prior+origin)/scale;b=(point+origin)/scale
    fractions=np.linspace(0,1,max(2,int(np.linalg.norm(b-a)*4)+1))
    xy=np.rint(a[None]+fractions[:,None]*(b-a)).astype(int)
    xy[:,0]=np.clip(xy[:,0],0,image.width-1);xy[:,1]=np.clip(xy[:,1],0,image.height-1)
    crosses=bool(core[xy[:,1],xy[:,0]].any())
    if kind=='stitch':
        if crosses:sewn.append(index)
        thread=True
    elif kind=='jump' and thread and crosses:loose.append(index)
    elif kind in ('trim','color_change','end'):thread=False
    prior=point
summary={'source':source.name,'source_sha256':before,'source_unchanged':before==hashlib.sha256(source.read_bytes()).hexdigest(),
         'height_mm':100,'deterministic':True,'knockout':report['colour_knockouts'][0],
         'palette':[c['hex'] for c in palette],'stitch_count':payload['stitch_count'],'trim_count':payload['trim_count'],
         'sewn_crossings_of_transparent_core':sewn,'untrimmed_jumps_over_transparent_core':loose,
         'generation_seconds':elapsed,'physical_sew_out':'Not performed'}
(out/'verification.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='knockout'},indent=2))
print('Remaining colour area:',summary['knockout']['remaining_colour_area_mm2'],'mm²; brush specks:',summary['knockout']['filled_specks'])
