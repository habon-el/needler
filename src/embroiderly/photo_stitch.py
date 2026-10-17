"""Experimental deterministic long/short fill with bounded boundary interlocking.

No neural geometry. Portrait files are published only after PES and DST readback
passes the specified stitch-length limits. This does not certify tension/density.
"""
from .knowledge_messages import message as knowledge_message
import json
import math
import tempfile
from pathlib import Path
import cv2
import numpy as np
import pyembroidery as emb
from PIL import Image,ImageDraw
from skimage.color import rgb2lab
from scipy.spatial import cKDTree
from scipy.ndimage import distance_transform_edt, map_coordinates
from .portrait import (MIN_STITCH_MM,MAX_STITCH_MM,PHOTO_ROW_SPACING_MM,
    PHOTO_BLEND_MM,PHOTO_BLEND_MAX_MM,PHOTO_SEED,PHOTO_SHORT_MM,PHOTO_LONG_MM,
    THREAD_WIDTH_MM,feature_boxes)
from .preparation import number,points

SAMPLE_MM = .1
SNAP_MARGIN_MM = .15
MAX_COMMANDS = 600000


def verify_file(path):
    pattern=emb.EmbPattern(str(path));prior=(0,0);lengths=[];violations=[]
    for i,(x,y,flag) in enumerate(pattern.stitches):
        command=flag&emb.COMMAND_MASK
        if command==emb.STITCH:
            length=math.dist(prior,(x,y))/10;lengths.append(length)
            if length<MIN_STITCH_MM-1e-8 or length>MAX_STITCH_MM+1e-8:
                violations.append({'command':i,'length_mm':length})
        prior=(x,y)
    if not lengths:raise ValueError('No sewable portrait stitches remain.')
    if violations:raise ValueError(f'Portrait export blocked: {len(violations)} stitch-length violations in {path.name}.')
    return dict(stitch_count=len(lengths),shortest_stitch_mm=min(lengths),longest_stitch_mm=max(lengths),violations=0)


def generate(source,directory,height_mm,options):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    with Image.open(source) as im:array=np.array(im.convert('RGBA'))
    h,w=array.shape[:2];scale=height_mm/h;alpha=array[:,:,3]>127
    if not alpha.any():raise ValueError('No selected portrait pixels.')
    palette=np.unique(array[:,:,:3][alpha],axis=0)
    if len(palette)>12:raise ValueError('Prepare the portrait with at most 12 colours.')
    brightness=rgb2lab(palette[None]/255)[0,:,0]
    order=np.argsort(brightness,kind='stable')
    if options.get('photo_order','light_to_dark')=='light_to_dark':order=order[::-1]
    elif options.get('photo_order')!='dark_to_light':raise ValueError('Choose a valid photo-stitch colour order.')
    spacing=number(options,'photo_spacing_mm',PHOTO_ROW_SPACING_MM,.4,1.5)
    blend=number(options,'photo_blend_mm',PHOTO_BLEND_MM,0,PHOTO_BLEND_MAX_MM)
    angle=number(options,'photo_angle',0,-180,180)
    seed=int(number(options,'photo_seed',PHOTO_SEED,0,2147483647))
    labels=np.full((h,w),-1,np.int16);regions=np.zeros((h,w),np.int32);region_count=0
    for i,rgb in enumerate(palette):
        mask=alpha&np.all(array[:,:,:3]==rgb,axis=2);labels[mask]=i
        n,cc=cv2.connectedComponents(mask.astype(np.uint8),8)
        regions[mask]=cc[mask]+region_count;region_count+=n-1
    directions=options.get('direction_lines',[])
    if not isinstance(directions,list) or len(directions)>32:raise ValueError('Use up to 32 direction lines.')
    guided={}
    for line in directions:
        pts=points(line,w,h,2);a,b=pts[0],pts[-1]
        if a==b:raise ValueError('Draw a direction line with distinct endpoints.')
        rid=int(regions[a[1],a[0]])
        if not rid:raise ValueError('Start the direction line inside a prepared colour region.')
        guided[rid]=math.degrees(math.atan2(b[1]-a[1],b[0]-a[0]))
    plan=emb.EmbPattern();plan.extras['name']='Portrait'
    omissions=[];overlaps=[];used=[];previous=(0,0);has_thread=False;covered=np.zeros((h,w),np.uint8)
    rng=np.random.default_rng(seed)
    for label in order:
        rgb=palette[label];colour='#%02x%02x%02x'%tuple(rgb)
        groups=[(angle,(labels==label)&~np.isin(regions,list(guided)))]
        groups.extend((a,regions==rid) for rid,a in sorted(guided.items()) if np.any((regions==rid)&(labels==label)))
        colour_runs=[]
        for degrees,target in groups:
            ys,xs=np.where(target)
            if not len(xs):continue
            theta=math.radians(degrees);uvec=np.array([math.cos(theta),math.sin(theta)]);vvec=np.array([-uvec[1],uvec[0]])
            bounds=np.array([[xs.min(),ys.min()],[xs.max(),ys.min()],[xs.max(),ys.max()],[xs.min(),ys.max()]])*scale
            uv=bounds@np.stack([uvec,vvec],axis=1)
            us=np.arange(math.floor((uv[:,0].min()-blend)/SAMPLE_MM)*SAMPLE_MM,uv[:,0].max()+blend+SAMPLE_MM,SAMPLE_MM)
            vs=np.arange(math.floor(uv[:,1].min()/spacing)*spacing,uv[:,1].max()+spacing/2,spacing)
            for row,v in enumerate(vs):
                xy=us[:,None]*uvec+v*vvec
                ix=np.rint(xy[:,0]/scale).astype(int);iy=np.rint(xy[:,1]/scale).astype(int)
                valid=(ix>=0)&(ix<w)&(iy>=0)&(iy<h)
                inside=np.zeros(len(us),bool);inside[valid]=target[iy[valid],ix[valid]]
                changes=np.flatnonzero(np.diff(np.r_[False,inside,False].astype(np.int8)))
                row_runs=[]
                for start,end in zip(changes[::2],changes[1::2]):
                    left,right=int(start),int(end-1);extensions=[]
                    for direction,index in [(-1,left),(1,right)]:
                        wanted=max(0,blend-SNAP_MARGIN_MM)*float(rng.uniform(.45,1))
                        steps=int(wanted/SAMPLE_MM);moved=0
                        for k in range(1,steps+1):
                            j=index+direction*k
                            if j<0 or j>=len(us) or not valid[j] or not alpha[iy[j],ix[j]] or labels[iy[j],ix[j]]==label:break
                            moved=k
                        extensions.append(moved*SAMPLE_MM)
                        if direction<0:left-=moved
                        else:right+=moved
                    length=us[right]-us[left]
                    if length<MIN_STITCH_MM+SNAP_MARGIN_MM:
                        p=xy[start];omissions.append(dict(colour=colour,point_mm=p.tolist(),length_mm=round(float(length),4),
                            canvas_height_to_retain_mm=round(height_mm*(MIN_STITCH_MM+SNAP_MARGIN_MM)/max(length,SAMPLE_MM),2),reason='Scanline fragment below safe snapped stitch length'))
                        continue
                    distances=[0.0];position=0.0;alternate=row%2
                    while length-position>MAX_STITCH_MM-SNAP_MARGIN_MM or length-position>PHOTO_LONG_MM:
                        target_length=(PHOTO_LONG_MM if alternate%2 else PHOTO_SHORT_MM)*float(rng.uniform(.8,1.2));alternate+=1
                        target_length=min(target_length,length-position-(MIN_STITCH_MM+SNAP_MARGIN_MM))
                        if target_length<MIN_STITCH_MM+SNAP_MARGIN_MM:break
                        position+=target_length;distances.append(position)
                    distances.append(length)
                    coords=[(us[left]+d)*uvec+v*vvec for d in distances]
                    snapped=[tuple(np.rint((p-np.array([w,h])*scale/2)*10).astype(int)) for p in coords]
                    # Post-quantization check precedes all file writes.
                    if any(not MIN_STITCH_MM-1e-8<=math.dist(a,b)/10<=MAX_STITCH_MM+1e-8 for a,b in zip(snapped,snapped[1:])):
                        raise ValueError('Portrait geometry failed snapped stitch limits; export not written.')
                    if row%2:snapped.reverse()
                    # PEC inserts a zero-length command after diagonal jump entries.
                    # Add a short axis-aligned entry, within the selected silhouette.
                    first,second=snapped[:2]
                    if first[0]!=second[0] and first[1]!=second[1]:
                        entry=None
                        for axis in sorted((0,1),key=lambda axis:-abs(second[axis]-first[axis])):
                            for distance in (3,4,5):
                                q=list(first);q[axis]+=distance*(1 if second[axis]>first[axis] else -1);q=tuple(q)
                                if not MIN_STITCH_MM-1e-8<=math.dist(q,second)/10<=MAX_STITCH_MM+1e-8:continue
                                samples=np.vstack([np.linspace(first,q,12),np.linspace(q,second,24)])/10/scale+np.array([w,h])/2
                                indexes=np.rint(samples).astype(int)
                                if np.any(indexes[:,0]<0) or np.any(indexes[:,0]>=w) or np.any(indexes[:,1]<0) or np.any(indexes[:,1]>=h):continue
                                if np.all(alpha[indexes[:,1],indexes[:,0]]):entry=q;break
                            if entry is not None:break
                        if entry is None:
                            omissions.append(dict(colour=colour,point_mm=coords[0].tolist(),length_mm=round(float(length),4),reason='No safe axis-aligned PEC entry within selected silhouette',canvas_height_to_retain_mm=None))
                            continue
                        snapped.insert(1,entry)
                    row_runs.append(snapped)
                    projected=(np.asarray(snapped)/10+np.array([w,h])*scale/2)@uvec
                    written_left=max(0,float(us[start]-projected.min()))
                    written_right=max(0,float(projected.max()-us[end-1]))
                    if any(extensions):overlaps.append(dict(colour=colour,left_mm=round(extensions[0],4),right_mm=round(extensions[1],4),written_left_mm=round(written_left,4),written_right_mm=round(written_right,4),
                        limit_mm=blend,note=knowledge_message('photo_stitch.07')))
                if row%2:row_runs.reverse()
                colour_runs.extend(row_runs)
        if not colour_runs:continue
        if has_thread:plan.add_stitch_absolute(emb.COLOR_CHANGE,*previous)
        plan.add_thread(colour);used.append(colour);has_thread=True
        # Visit nearby runs before travelling to another island; never bridge the background.
        starts=np.asarray([run[0] for run in colour_runs],float);tree=cKDTree(starts)
        remaining=np.ones(len(colour_runs),bool)
        distance_field=distance_transform_edt(labels!=label)*scale
        first_run=True
        for _ in range(len(colour_runs)):
            k=min(16,len(colour_runs))
            while True:
                distances,indexes=tree.query(previous,k=k)
                candidates=[(float(d),int(j)) for d,j in zip(np.atleast_1d(distances),np.atleast_1d(indexes)) if remaining[int(j)]]
                if candidates:break
                k=min(len(colour_runs),k*2)
            _,index=min(candidates);remaining[index]=False;run=colour_runs[index]
            gap=math.dist(previous,run[0])/10
            connected=False
            if not first_run and MIN_STITCH_MM-1e-8<=gap<=MAX_STITCH_MM-SNAP_MARGIN_MM:
                samples=np.linspace(previous,run[0],max(2,math.ceil(gap/SAMPLE_MM)+1))/10/scale+np.array([w,h])/2
                indexes=np.rint(samples).astype(int)
                if np.all((indexes[:,0]>=0)&(indexes[:,0]<w)&(indexes[:,1]>=0)&(indexes[:,1]<h)):
                    boundary_distance=map_coordinates(distance_field,[samples[:,1],samples[:,0]],order=1,mode='constant',cval=float('inf'))-scale/2
                    connected=bool(np.all(alpha[indexes[:,1],indexes[:,0]]) and np.all(boundary_distance<=blend))
            if connected:plan.add_stitch_absolute(emb.STITCH,*run[0])
            elif not first_run and gap==0:pass
            else:
                if plan.stitches:plan.add_stitch_absolute(emb.TRIM,*previous)
                plan.add_stitch_absolute(emb.JUMP,*run[0])
            first_run=False
            for p in run[1:]:plan.add_stitch_absolute(emb.STITCH,*p)
            previous=run[-1]
            if len(plan.stitches)>MAX_COMMANDS:raise ValueError('Portrait exceeds 600,000 commands. Crop or simplify before generating.')
    if not has_thread:raise ValueError('No portrait rows meet the minimum length; enlarge the design.')
    plan.add_stitch_absolute(emb.END,*previous)
    with tempfile.TemporaryDirectory(prefix='portrait-export-',dir=directory) as temporary:
        temp=Path(temporary)
        from .machine_files import write_pair
        write_pair(plan,temp/'design.pes',temp/'design.dst',{'version':6,'tie_on':False,'tie_off':False,'full_jump':False})
        audits={fmt:verify_file(temp/('design.'+fmt)) for fmt in ('pes','dst')}
        written=emb.EmbPattern(str(temp/'design.pes'))
        if [t.hex_color().lower() for t in written.threadlist]!=used:raise ValueError('Portrait export changed thread colours.')
        expected=[(int(x),int(y)) for x,y,flag in plan.stitches if flag&emb.COMMAND_MASK==emb.STITCH]
        for fmt in ('pes','dst'):
            actual=[(x,y) for x,y,flag in emb.EmbPattern(str(temp/('design.'+fmt))).stitches if flag&emb.COMMAND_MASK==emb.STITCH]
            if actual!=expected:raise ValueError('Portrait export changed sewn coordinates; files not published.')
        for fmt in ('pes','dst'):(temp/('design.'+fmt)).replace(directory/('design.'+fmt))
    types={emb.STITCH:'stitch',emb.JUMP:'jump',emb.TRIM:'trim',emb.COLOR_CHANGE:'color_change',emb.END:'end'}
    steps=[];thread=0
    coverage=Image.new('L',(w,h));draw=ImageDraw.Draw(coverage);prior=(0,0)
    colour_coverage=Image.new('RGBA',(w,h));colour_draw=ImageDraw.Draw(colour_coverage)
    for x,y,flag in written.stitches:
        kind=types.get(flag&emb.COMMAND_MASK,'unknown')
        if kind=='color_change':thread+=1
        point=(x/10,y/10)
        if kind=='stitch':
            a=(prior[0]/scale+w/2,prior[1]/scale+h/2);b=(point[0]/scale+w/2,point[1]/scale+h/2)
            draw.line([a,b],fill=255,width=max(1,round(THREAD_WIDTH_MM/scale)))
            colour_draw.line([a,b],fill=used[min(thread,len(used)-1)],width=max(1,round(THREAD_WIDTH_MM/scale)))
        steps.append(dict(x=point[0],y=point[1],t=kind,color=used[min(thread,len(used)-1)]));prior=point
    selected_uncovered=int(np.count_nonzero(alpha&(np.asarray(coverage)==0)))
    feature_coverage=[]
    rendered=np.asarray(colour_coverage)
    for feature in feature_boxes(options,w,h):
        x,y,r,b=feature['bounds'];selected=alpha[y:b,x:r]
        pixels=rendered[y:b,x:r];covered=selected&(pixels[:,:,3]>0)
        feature_coverage.append(dict(kind=feature['kind'],bounds=feature['bounds'],
            selected_pixels=int(selected.sum()),covered_pixels=int(covered.sum()),
            visible_thread_colours=len(np.unique(pixels[:,:,:3][covered],axis=0)),
            note='User-marked box; sampled nominal-width coverage, not anatomical recognition or physical sew-out.'))
    quality=dict(length_audits=audits,omissions=omissions,overlaps=overlaps,
        overlap_count=len(overlaps),max_written_penetration_mm=max((max(v['written_left_mm'],v['written_right_mm']) for v in overlaps),default=0),max_planned_penetration_mm=max((max(v['left_mm'],v['right_mm']) for v in overlaps),default=0),
        selected_pixels_without_thread_coverage=selected_uncovered,selected_pixels=int(alpha.sum()),
        note=knowledge_message('photo_stitch.06'))
    quality['feature_coverage']=feature_coverage
    payload=dict(steps=steps,colors=used,stitch_count=audits['pes']['stitch_count'],trim_count=sum(s['t']=='trim' for s in steps),
        origin_mm=[w*scale/2,h*scale/2],height_mm=height_mm,thread_width_mm=THREAD_WIDTH_MM,engine='Experimental photo-stitch',objects=region_count,
        palette_format='PES v6 custom RGB',portrait_audit=quality)
    (directory/'portrait-audit.json').write_text(json.dumps(quality,sort_keys=True))
    (directory/'playback.json').write_text(json.dumps(payload))
    from .release_gate import record_context
    record_context(directory,alpha,scale,payload['origin_mm'])
    return payload
