"""Reversible CIELab colour removal; no model, image writes or stitch generation.

Background topology is computed on the source, not the selection silhouette.
Only explicitly accepted options affect preparation. Defaults are cited seeds.
"""
import hashlib
import math
import re
import cv2
import numpy as np
from scipy.ndimage import distance_transform_edt
from skimage.color import rgb2lab
from .knowledge_store import load_knowledge


def defaults():
    table=load_knowledge()['knockout.json']
    row=next(r for r in table['rows'] if r['id']=='brush.cleanup')
    return {**row,'citation':f"knockout.json#brush.cleanup v{table['version']}"}


def hex_rgb(value):
    if not isinstance(value,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',value):
        raise ValueError('Choose a six-digit removal colour.')
    return np.array([int(value[i:i+2],16) for i in (1,3,5)],np.uint8)


def bounded(value,low,high,label):
    if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:
        raise ValueError(f'{label} must be between {low} and {high}.')
    return float(value)


def validate(operation,shape):
    if not isinstance(operation,dict) or set(operation)-{'colour','scope','point','tolerance','cleanup','restore_parts','fill_parts','minimum_area_mm2','close_radius_mm'}:
        raise ValueError('Invalid colour removal operation.')
    seed=defaults();result=dict(operation)
    hex_rgb(result.get('colour'))
    result['colour']=result['colour'].lower()
    if result.get('scope') not in ('everywhere','this area'):
        raise ValueError('Choose everywhere or this area.')
    result['tolerance']=bounded(result.get('tolerance',seed['default_delta_e']),0,100,'Delta-E tolerance')
    result['minimum_area_mm2']=bounded(result.get('minimum_area_mm2',seed['minimum_area_mm2']),0,25,'Brush speck area')
    result['close_radius_mm']=bounded(result.get('close_radius_mm',seed['close_radius_mm']),0,seed['maximum_close_radius_mm'],'Closing radius (mm)')
    result['cleanup']=result.get('cleanup',True)
    if type(result['cleanup']) is not bool:raise ValueError('Brush cleanup must be true or false.')
    parts=result.get('restore_parts',[])
    if not isinstance(parts,list) or len(parts)>256 or any(not isinstance(p,str) or not re.fullmatch(r'[0-9a-f]{20}',p) for p in parts):
        raise ValueError('Invalid restored parts.')
    result['restore_parts']=list(dict.fromkeys(parts))
    fills=result.get('fill_parts',[])
    if not isinstance(fills,list) or len(fills)>256 or any(not isinstance(p,str) or not re.fullmatch(r'[0-9a-f]{20}',p) for p in fills):
        raise ValueError('Invalid filled parts.')
    result['fill_parts']=list(dict.fromkeys(fills))
    if set(fills)&set(parts):raise ValueError('A part cannot be restored and filled at the same time.')
    if result['scope']=='this area':
        point=result.get('point');h,w=shape
        if not isinstance(point,list) or len(point)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in point) or not (0<=point[0]<w and 0<=point[1]<h):
            raise ValueError('Click a point inside the colour area.')
        result['point']=[int(point[0]),int(point[1])]
    return result


def classify_flat(rgb,visible):
    pixels=rgb[visible]
    if not len(pixels):return False
    neutral=np.mean(np.ptp(pixels.astype(float),axis=1)<20)
    extreme=np.mean((pixels.mean(1)<65)|(pixels.mean(1)>210))
    return bool((neutral>.94 and extreme>.80) or len(np.unique(pixels//32,axis=0))<=35)


def propose_background(image):
    rgba=np.asarray(image.convert('RGBA'));rgb=rgba[:,:,:3];visible=rgba[:,:,3]>127
    if not classify_flat(rgb,visible):return None
    border=np.zeros(visible.shape,bool);border[[0,-1],:]=True;border[:,[0,-1]]=True
    samples=rgb[border&visible]
    if len(samples)<.5*np.count_nonzero(border):return None
    bins,count=np.unique(samples//16,axis=0,return_counts=True);dominant=bins[np.argmax(count)]
    value=np.rint(np.median(samples[np.all(samples//16==dominant,axis=1)],axis=0)).astype(np.uint8)
    lab=rgb2lab(samples[None]/255)[0];target=rgb2lab(value[None,None]/255)[0,0]
    seed=defaults();coverage=float(np.mean(np.linalg.norm(lab-target,axis=1)<=seed['default_delta_e']))
    if coverage<.75:return None
    # Do not offer to remove an empty/uniform upload.
    if not np.any(np.linalg.norm(rgb2lab(rgb/255)-target,axis=2)[visible]>seed['default_delta_e']):return None
    return dict(colour='#%02x%02x%02x'%tuple(value),scope='everywhere',tolerance=seed['default_delta_e'],cleanup=True,
                minimum_area_mm2=seed['minimum_area_mm2'],close_radius_mm=seed['close_radius_mm'],restore_parts=[])


def colour_match(rgb,visible,colour,tolerance):
    """CIE76 matching, then local antialias assignment to the nearer Lab side.

Only flat-art boundary mixtures are reassigned. Significant grey/coloured areas
get their own foreground representative rather than being assumed to be ink.
"""
    lab=rgb2lab(rgb/255);target=rgb2lab(colour[None,None]/255)[0,0]
    distance=np.linalg.norm(lab-target,axis=2);matched=(distance<=tolerance)&visible
    corrected=rgb.copy();edge_pixels=0
    if classify_flat(rgb,visible) and matched.any():
        core=cv2.erode((visible&~matched).astype(np.uint8),np.ones((5,5),np.uint8),borderType=cv2.BORDER_CONSTANT,borderValue=0)>0
        pixels=rgb[core] if core.any() else rgb[visible&~matched]
        if len(pixels):
            bins,counts=np.unique(pixels//16,axis=0,return_counts=True)
            ids=np.flatnonzero(counts>=max(8,len(pixels)*.02))
            ids=ids[np.argsort(-counts[ids],kind='stable')][:16]
            representatives=np.array([np.rint(np.median(pixels[np.all(pixels//16==bins[i],axis=1)],axis=0)) for i in ids],np.uint8)
            if len(representatives):
                foreground=rgb2lab(representatives[None]/255)[0]
                near=cv2.dilate(matched.astype(np.uint8),np.ones((5,5),np.uint8)).astype(bool)&visible&~matched
                # Monochrome line art has a single ink endpoint: classify its
                # grey mixtures even inside a stroke (distressed brush texture).
                if len(representatives)==1 and np.ptp(colour)<20 and np.ptp(representatives[0])<20:
                    near=visible&~matched
                yy,xx=np.where(near)
                if len(yy):
                    values=lab[yy,xx];d=np.linalg.norm(values[:,None]-foreground[None],axis=2)
                    nearest=np.argmin(d,axis=1);fg=foreground[nearest];axis=fg-target
                    amount=np.clip(np.sum((values-target)*axis,axis=1)/np.maximum(np.sum(axis*axis,axis=1),1e-8),0,1)
                    residual=np.linalg.norm(values-(target+amount[:,None]*axis),axis=1)
                    mixture=residual<=max(2,tolerance)
                    to_bg=mixture&(distance[yy,xx]<=d[np.arange(len(yy)),nearest])
                    to_fg=mixture&~to_bg
                    matched[yy[to_bg],xx[to_bg]]=True
                    corrected[yy[to_fg],xx[to_fg]]=representatives[nearest[to_fg]]
                    edge_pixels=int(np.count_nonzero(to_bg|to_fg))
    return matched,corrected,edge_pixels


def remove_colour(rgb,mask,operation,physical_height,visible=None):
    """Return RGB/mask + complete recovery/cleanup report without mutating inputs."""
    h,w=mask.shape;op=validate(operation,(h,w));seed=defaults()
    if visible is None:visible=np.ones(mask.shape,bool)
    target=hex_rgb(op['colour']);matched,corrected,edge_pixels=colour_match(rgb,visible,target,op['tolerance'])
    n,cc,stats,_=cv2.connectedComponentsWithStats(matched.astype(np.uint8),connectivity=8)
    if op['scope']=='this area':
        x,y=op['point'];label=cc[y,x]
        if label==0:raise ValueError('That point does not match the selected colour. Pick the area again or adjust tolerance.')
        removed=(cc==label)&mask
    else:removed=matched&mask
    result=mask&~removed
    # Only edge pixels actually retained by this operation may be decontaminated.
    output=rgb.copy()
    correction=result if op['scope']=='everywhere' else result&cv2.dilate((cc==label).astype(np.uint8),np.ones((5,5),np.uint8)).astype(bool)
    output[correction]=corrected[correction]
    boundary=np.zeros(mask.shape,bool);boundary[[0,-1],:]=True;boundary[:,[0,-1]]=True
    boundary|=cv2.dilate((~visible).astype(np.uint8),np.ones((3,3),np.uint8)).astype(bool)
    outside=set(np.unique(cc[boundary]));scale=physical_height/h;pixel_area=scale**2
    parts=[];tiny=[];approved_fills=[];protected=np.zeros_like(mask);known=set();restored_pixels=0
    for i in range(1,n):
        if i in outside:continue
        x,y,bw,bh,area=map(int,stats[i]);region=cc[y:y+bh,x:x+bw]==i
        active=removed[y:y+bh,x:x+bw]&region
        if not active.any():continue
        # A clipped selection is not an ink-surrounded speck.
        ring=cv2.dilate((cc[max(0,y-1):min(h,y+bh+1),max(0,x-1):min(w,x+bw+1)]==i).astype(np.uint8),np.ones((3,3),np.uint8)).astype(bool)
        boxmask=mask[max(0,y-1):min(h,y+bh+1),max(0,x-1):min(w,x+bw+1)]
        surrounded=bool(np.all(boxmask[ring]))
        identity=hashlib.sha256((str((x,y,bw,bh))+op['colour']).encode()+np.packbits(region).tobytes()).hexdigest()[:20]
        known.add(identity);area_mm2=area*pixel_area
        keep=identity in op['restore_parts']
        small=area_mm2<op['minimum_area_mm2'] and surrounded
        if small:tiny.append(i)
        # Shape is a review hint, never proof that a small hole is brush texture.
        contours,_=cv2.findContours(region.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        contour=max(contours,key=cv2.contourArea)
        perimeter=cv2.arcLength(contour,True);surface=cv2.contourArea(contour)
        circularity=4*math.pi*surface/(perimeter*perimeter) if perimeter else 0
        hull=cv2.contourArea(cv2.convexHull(contour))
        solidity=surface/hull if hull else 0
        likely_counter=small and circularity>=.35 and solidity>=.65 and min(bw,bh)/max(bw,bh)>=.2
        classification='Possible letter hole' if likely_counter else ('Uncertain small hole / texture' if small else 'Enclosed part')
        fill=identity in op['fill_parts']
        if fill and not small:raise ValueError('Only reviewed small holes can be filled as specks.')
        if len(parts)>=256:raise ValueError('More than 256 enclosed parts. Use Only this area or crop closer before colour removal.')
        parts.append(dict(id=identity,bounds=[x,y,x+bw,y+bh],area_mm2=round(area_mm2,6),pixels=area,keep=keep,
                          width_mm=round(bw*scale,4),height_mm=round(bh*scale,4),review_hole=small,filled=fill and op['cleanup'],
                          circularity=round(circularity,3),solidity=round(solidity,3),
                          colour=op['colour'],label=f'{classification} {len(parts)+1}'))
        protected[y:y+bh,x:x+bw]|=region
        if fill:approved_fills.append(i)
        if keep:
            result[y:y+bh,x:x+bw]|=active;restored_pixels+=int(active.sum())
            output[y:y+bh,x:x+bw][active]=rgb[y:y+bh,x:x+bw][active]
    if (set(op['restore_parts'])|set(op['fill_parts']))-known:
        raise ValueError('Restored parts no longer match this colour/tolerance. Review the new parts before applying.')
    before_cleanup=result.copy();filled_count=0
    if op['cleanup'] and approved_fills:
        selected=np.isin(cc,approved_fills)&removed
        result|=selected;filled_count=len(approved_fills)
    radius=int(math.floor(op['close_radius_mm']/scale+1e-9)) if op['cleanup'] and not tiny else 0
    closed_pixels=0
    if radius:
        kernel=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(radius*2+1,)*2)
        # Close each ink component separately, never bridge two letters.
        count,labels,component_stats,_=cv2.connectedComponentsWithStats(result.astype(np.uint8),connectivity=8)
        closed=result.copy()
        for i in range(1,count):
            x,y,bw,bh,_=map(int,component_stats[i]);x0=max(0,x-radius);y0=max(0,y-radius);x1=min(w,x+bw+radius);y1=min(h,y+bh+radius)
            local=(labels[y0:y1,x0:x1]==i).astype(np.uint8)
            filled=cv2.morphologyEx(local,cv2.MORPH_CLOSE,kernel,borderType=cv2.BORDER_CONSTANT,borderValue=0)>0
            closed[y0:y1,x0:x1]|=filled
        additions=closed&~result&~protected&mask&visible
        closed_pixels=int(additions.sum());result|=additions
    added=result&~before_cleanup
    if added.any() and before_cleanup.any():
        # Restoring alpha alone would create WHITE stitches. Copy nearest ink RGB.
        ink=before_cleanup&~matched
        if ink.any():
            nearest=distance_transform_edt(~ink,return_distances=False,return_indices=True)
            output[added]=output[tuple(nearest[:,added])]
    remaining=np.linalg.norm(rgb2lab(output/255)-rgb2lab(target[None,None]/255)[0,0],axis=2)<=op['tolerance']
    report=dict(operation=op,parts=parts,filled_specks=filled_count,tiny_specks=len(tiny),closing_pixels=closed_pixels,
                effective_close_radius_mm=radius*scale,removed_pixels=int(np.count_nonzero(mask&~result)),
                remaining_colour_area_mm2=float(np.count_nonzero(remaining&result)*pixel_area),restored_pixels=restored_pixels,
                antialias_pixels=edge_pixels,seed_citation=seed['citation'],seed_verified=seed['verified_by_user'],
                cleanup_note=f'Filled {filled_count} small holes you explicitly selected. {len(tiny)-filled_count} small enclosed areas were not filled; possible letter holes and uncertain texture stay open for review. Shape hints are not letter recognition. Edge smoothing pauses when small holes are present.')
    return output,result,report


def apply_operations(rgb,mask,options,physical_height,visible=None):
    operations=options.get('colour_knockouts',[])
    if not isinstance(operations,list) or len(operations)>16:raise ValueError('Use at most 16 colour removal operations.')
    reports=[]
    for operation in operations:
        rgb,mask,report=remove_colour(rgb,mask,operation,physical_height,visible);reports.append(report)
    return rgb,mask,reports


def proposal_patch(image,options,operation=None):
    operation=operation or propose_background(image)
    if operation is None:return None
    operation=validate(operation,(image.height,image.width))
    return {'colour_knockouts':[*options.get('colour_knockouts',[]),operation]}


def command(text):
    phrase=re.sub(r'[.!?]+$','',text.strip().lower())
    return phrase in ('remove the white','remove white','keep only the black','keep only black')
