"""Repeatable contrast-loss and boundary warnings; no semantic model required.

Thresholds are screening heuristics, not proof that every photographic texture
is a useful embroidery feature. Causal evidence comes from pipeline snapshots.
"""
from .knowledge_messages import message as knowledge_message
import hashlib
import math
import numpy as np
from .colour_rows import unique_rows
import cv2
from scipy.ndimage import maximum_filter, minimum_filter, binary_erosion, binary_dilation
from skimage.color import rgb2lab
from PIL import Image, ImageDraw
from .subject_model import mask_runs

WINDOW = 7
MIN_CONTRAST = 10.0
RETAINED_RATIO = .45
THREAD_WIDTH_MM = .4


def contrast(rgb):
    lab=rgb2lab(np.asarray(rgb)/255)
    return np.max(maximum_filter(lab,size=(WINDOW,WINDOW,1))-minimum_filter(lab,size=(WINDOW,WINDOW,1)),axis=2)


def groups(mask):
    n,cc,stats,_=cv2.connectedComponentsWithStats(mask.astype(np.uint8),8)
    for i in range(1,n):
        x,y,w,h,area=map(int,stats[i])
        yield cc==i,[x,y,x+w,y+h],area


def cropped_groups(mask):
    """Like groups(), but each mask is cropped to its own bounds. Artwork with
    hundreds of small areas no longer rescans the whole image per area."""
    n,cc,stats,_=cv2.connectedComponentsWithStats(mask.astype(np.uint8),8)
    for i in range(1,n):
        x,y,w,h,area=map(int,stats[i])
        yield cc[y:y+h,x:x+w]==i,[x,y,x+w,y+h],area


def hex_colour(rgb):
    return '#%02x%02x%02x'%tuple(map(int,rgb))


def location(bounds,w,h):
    x,y,r,b=bounds
    return ('top' if (y+b)/2<h/3 else 'bottom' if (y+b)/2>2*h/3 else 'middle')+' '+('left' if (x+r)/2<w/3 else 'right' if (x+r)/2>2*w/3 else 'centre')


def check(source,output,selected,height,stages=None,floor=0):
    source=np.asarray(source)[:,:,:3];output=np.asarray(output);h,w=selected.shape;scale=height/h
    source_contrast=contrast(source);result_contrast=contrast(output[:,:,:3])
    interior=binary_erosion(selected,iterations=WINDOW//2,border_value=0)&(output[:,:,3]>127)
    lost=interior&(source_contrast>=MIN_CONTRAST)&(result_contrast<source_contrast*RETAINED_RATIO)
    stages=stages or {};findings=[]
    stage_changes={key:np.any(before!=after,axis=2) for key,(before,after) in stages.items()}
    for region,bounds,area in cropped_groups(lost):
        x0,y0,r0,b0=x,y,r,b=bounds
        window=(slice(y0,b0),slice(x0,r0))   # every array below is read inside the area's box
        # Representative source tone with the greatest departure from the flat result.
        values=source[window][region];out=output[window][:,:,:3][region]
        delta=np.linalg.norm(rgb2lab(values[None]/255)[0]-rgb2lab(out[None]/255)[0],axis=1)
        index=int(np.argmax(delta));tone=values[index];target=out[index]
        yy,xx=np.where(region);point=[int(xx[index])+x0,int(yy[index])+y0]
        cause='colour quantization or simplification; exact cause not isolated'
        pairs=[];causal_mask=np.zeros_like(region)
        for key,label in [('simplify','image smoothing'),('quantization','colour reduction'),
                          ('merge','recorded palette merge'),('smooth','label smoothing'),
                          ('cleanup','minimum-area cleanup')]:
            if key in stages:
                before,after=stages[key];changed=region&stage_changes[key][window]
                if changed.any():
                    cause=label;causal_mask=changed
                    pair_values=unique_rows(np.concatenate([before[window][changed],after[window][changed]],axis=1))
                    pairs=[dict(source=hex_colour(v[:3]),target=hex_colour(v[3:])) for v in pair_values]
        if cause in ('minimum-area cleanup','colour reduction') and causal_mask.any():
            region=causal_mask;yy,xx=np.where(region)
            x,y,r,b=int(xx.min())+x0,int(yy.min())+y0,int(xx.max()+1)+x0,int(yy.max()+1)+y0
            bounds=[x,y,r,b];area=int(region.sum())
        width=round((r-x)*scale,3);short=min(r-x,b-y)*scale
        findings.append(dict(id=hashlib.sha256(str(bounds).encode()).hexdigest()[:12],bounds=bounds,
            position=location(bounds,w,h),pixels=area,width_mm=width,height_mm=round((b-y)*scale,3),
            source_contrast=round(float(source_contrast[window][region].max()),3),result_contrast=round(float(result_contrast[window][region].max()),3),
            cause=cause,merged_colours=pairs,causal_mask_runs=mask_runs(causal_mask[y-y0:b-y0,x-x0:r-x0]),source_tone=hex_colour(tone),result_tone=hex_colour(target),sample_point=point,
            area_mm2=round(area*scale*scale,4),canvas_height_for_area_mm=round(height*math.sqrt(floor/(area*scale*scale)),2) if floor>area*scale*scale else height,
            below_thread_width=short<THREAD_WIDTH_MM,canvas_height_for_thread_width_mm=round(height*THREAD_WIDTH_MM/max(short,1e-9),2),
            note=knowledge_message('detail_loss.05')))
    findings.sort(key=lambda f:(-f['pixels'],f['bounds']))
    edge=selected&~binary_erosion(selected,border_value=1)
    # Image border and transparent source edges are not inferred segmentation cuts.
    unsupported=edge&~binary_dilation(source_contrast>=MIN_CONTRAST,iterations=2)
    boundary=[]
    for region,bounds,area in groups(unsupported):
        if area<3:continue
        boundary.append(dict(bounds=bounds,pixels=area,position=location(bounds,w,h),
            span_mm=round(max(bounds[2]-bounds[0],bounds[3]-bounds[1])*scale,3),
            note='Boundary lacks strong nearby image contrast; inspect for clipping. Soft edges and intentional cuts can also trigger this warning.'))
    changes=[]
    for stage,(before,after) in stages.items():
        changed=selected&stage_changes[stage]
        for region,bounds,area in cropped_groups(changed):
            changes.append(dict(stage=stage,bounds=bounds,mask_runs=mask_runs(region),pixels=area,area_mm2=round(area*scale*scale,4),width_mm=round((bounds[2]-bounds[0])*scale,3),height_mm=round((bounds[3]-bounds[1])*scale,3),canvas_height_for_area_mm=round(height*math.sqrt(floor/(area*scale*scale)),2) if stage=='cleanup' and floor>area*scale*scale else None))
    return dict(version=1,findings=findings,boundary=boundary,pipeline_changes=changes,thresholds=dict(window_px=WINDOW,source_contrast=MIN_CONTRAST,retained_ratio=RETAINED_RATIO),
        note='Deterministic screening, not proof of every lost feature. No small-colour-cluster fraction is used by this reducer. Texture can be flagged as detail.')


def recover(output,source,options):
    """Explicit local colour locks, never enabled by a warning alone."""
    from .preparation import colour,number
    values=options.get('detail_recoveries',[])
    if not isinstance(values,list) or len(values)>40:raise ValueError('Use up to 40 local detail recoveries.')
    h,w=output.shape[:2];lab=rgb2lab(source/255)
    for value in values:
        if not isinstance(value,dict):raise ValueError('Invalid detail recovery.')
        bounds=value.get('bounds')
        if not isinstance(bounds,list) or len(bounds)!=4 or any(type(v) is not int for v in bounds):raise ValueError('Invalid recovery bounds.')
        x,y,r,b=bounds
        if not 0<=x<r<=w or not 0<=y<b<=h:raise ValueError('Recovery must be inside the artwork.')
        tone=np.array(colour(value.get('colour')));distance=number(value,'distance',8,0,20)
        selected=np.linalg.norm(lab[y:b,x:r]-rgb2lab(tone[None,None]/255)[0,0],axis=2)<=distance
        selected &= output[y:b,x:r,3]>127
        output[y:b,x:r,:3][selected]=tone
    limit=12 if options.get('artwork_type')=='portrait' else 8
    if values and len(unique_rows(output[:,:,:3][output[:,:,3]>127]))>limit:
        raise ValueError(f'Local recovery exceeds {limit} thread colours. Free a palette slot first; no colours were removed automatically.')
    return output


def overlay(image,audit):
    image=image.convert('RGB').copy();draw=ImageDraw.Draw(image)
    for item in audit['findings']:draw.rectangle(item['bounds'],outline='#d7006f',width=2)
    for item in audit['boundary']:draw.rectangle(item['bounds'],outline='#007fca',width=2)
    return image


def register_details(app,root):
    from flask import request,jsonify,abort
    from pathlib import Path
    from .design_review import register_design_review
    register_design_review(app, root)
    from .preparation import prepare,load_image,data_url
    @app.post('/details/<name>')
    def details(name):
        path=root/'work'/'uploads'/Path(name).name
        if not path.is_file():abort(404)
        try:
            body=request.get_json(silent=True)
            if not isinstance(body,dict) or not isinstance(body.get('options'),dict):raise ValueError('Expected artwork settings.')
            options=body['options'];image,palette,report=prepare(path,options)
            audit=report['detail_loss'];source=load_image(path)
            result=dict(audit=audit,overlay=data_url(overlay(source,audit)),image=data_url(image),colours=len(palette))
            if body.get('action')=='recover':
                finding=next((v for v in audit['findings'] if v['id']==body.get('id')),None)
                if finding is None:raise ValueError('Finding changed; review the latest checks.')
                if finding['below_thread_width']:raise ValueError('This marked area is below the nominal thread-width screen. Enlarge the design instead of promising colour recovery.')
                patch={'detail_recoveries':options.get('detail_recoveries',[])+[dict(bounds=finding['bounds'],colour=finding['source_tone'],distance=8)]}
                if body.get('strategy')=='merge_threshold':
                    if options.get('artwork_type')!='portrait' or finding['cause']!='recorded palette merge':raise ValueError('No adjustable portrait merge is evidenced for this finding.')
                    patch={'portrait_merge_delta_e':0}
                after,after_palette,after_report=prepare(path,{**options,**patch})
                result.update(patch=patch,after_image=data_url(after),after_colours=len(after_palette),after_audit=after_report['detail_loss'],
                    explanation=('Disable automatic near-colour merging for this portrait; this affects the entire palette. Review before applying.' if 'portrait_merge_delta_e' in patch else 'Local source-tone lock inside this marked box. The rest of the artwork is unchanged. Review the result; no settings are applied yet.'))
            elif body.get('action','check')!='check':raise ValueError('Choose detail check or recovery.')
            return jsonify(result)
        except (ValueError,TypeError,KeyError,OSError,cv2.error) as error:return jsonify(error=str(error)),400
