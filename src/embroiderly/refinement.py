"""Versioned, bounded local operations and source-versus-written-stitch checks."""
from .knowledge_messages import message as knowledge_message
import copy
import hashlib
import math
import json
from pathlib import Path
import numpy as np
import cv2
from PIL import Image,ImageDraw
from scipy.ndimage import maximum_filter,minimum_filter,distance_transform_edt
from skimage.color import rgb2lab
from .subject_model import mask_runs,unpack_mask

VERSION=1
SHAPE_WIDTH_MM=1.0  # Screening heuristic, not a universal machine minimum.


def bounds(value,w,h):
    if not isinstance(value,list) or len(value)!=4 or any(type(v) is not int for v in value):raise ValueError('Invalid correction bounds.')
    x,y,r,b=value
    if not 0<=x<r<=w or not 0<=y<b<=h:raise ValueError('Correction must be inside the image.')
    return x,y,r,b


def digest(array):return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def replay(source,prepared,operations):
    from .preparation import colour
    if not isinstance(operations,list) or len(operations)>100:raise ValueError('Use up to 100 local corrections.')
    output=np.array(prepared);src=np.array(source.convert('RGBA'));h,w=output.shape[:2];history=[]
    for op in operations:
        if not isinstance(op,dict) or op.get('version')!=VERSION:raise ValueError('Unsupported correction version.')
        if op.get('image_hash')!=digest(src):raise ValueError('Correction belongs to different source pixels; it cannot be replayed safely.')
        kind=op.get('type')
        if kind not in ('add-region','subtract-region','split-region','keep-small-region'):raise ValueError('Unsupported local correction.')
        x,y,r,b=bounds(op.get('bounds'),w,h);selected=unpack_mask(op.get('mask_runs'),(b-y,r-x))
        point=op.get('point')
        if not isinstance(point,list) or len(point)!=2 or any(type(v) is not int for v in point) or not x<=point[0]<r or not y<=point[1]<b:raise ValueError('Correction point must be in its patch.')
        outside=np.ones((h,w),bool);outside[y:b,x:r]=False;before=digest(output[outside]);mask_before=digest(output[:,:,3][outside]);old=output[y:b,x:r].copy()
        region=output[y:b,x:r];selected &= src[y:b,x:r,3]>127
        if kind=='subtract-region':region[selected]=0
        else:
            rgb=colour(op.get('colour'))
            if kind=='add-region':selected &= region[:,:,3]<=127
            else:selected &= region[:,:,3]>127
            region[selected,:3]=rgb;region[selected,3]=255
        assert digest(output[outside])==before
        history.append(dict(type=kind,bounds=[x,y,r,b],point=point,changed_pixels=int(np.any(old!=region,axis=2).sum()),
            outside_rgba_hash_before=before,outside_rgba_hash_after=digest(output[outside]),outside_mask_hash_before=mask_before,outside_mask_hash_after=digest(output[:,:,3][outside])))
    return Image.fromarray(output),history


def prepare_replayed(path,options,mask_directory=None,target_height_mm=None):
    from .preparation import prepare,load_image,components,match_thread
    from .detail_loss import check
    base={k:v for k,v in options.items() if k!='refinement_ops'}
    image,_,report=prepare(path,base,mask_directory,target_height_mm)
    source=load_image(path);output,history=replay(source,image,options['refinement_ops']);pixels=np.array(output);kept=pixels[:,:,3]>127
    if not kept.any():raise ValueError('Corrections removed the entire design; undo or restore the subject.')
    palette,inverse=np.unique(pixels[:,:,:3][kept],axis=0,return_inverse=True)
    limit=12 if options.get('artwork_type')=='portrait' else 8
    if len(palette)>limit:raise ValueError(f'Correction needs {len(palette)} colours; the current engine permits {limit}. No other colours were changed or discarded.')
    swatches=[dict(hex='#%02x%02x%02x'%tuple(v),pixels=int((inverse==i).sum()),locked=False) for i,v in enumerate(palette)]
    for swatch in swatches:swatch['match']=match_thread(swatch['hex'])
    labels=np.full(kept.shape,-1,np.int16);labels[kept]=inverse
    report=copy.deepcopy(report);report['base_detail_loss']=report.get('detail_loss',{})
    report['detail_loss']=check(np.asarray(source)[:,:,:3],pixels,kept,report['height_mm'],floor=report['cleanup_floor_mm2'])
    report.update(colours_after=len(palette),regions_after=len(components(labels)),refinement_history=history,
        refinement_note='Local operations replay after base preparation; outside each patch is byte-identical. Existing global cleanup metrics describe the base pass.')
    from .borders import border_plan
    report['border']=border_plan(kept,report['height_mm'],options)
    return output,swatches,report


def aligned_stitches(payload,size):
    """Rasterize only sewn commands at source resolution, without decorative lighting."""
    w,h=size;scale=h/payload['height_mm'];origin=payload['origin_mm']
    image=Image.new('RGBA',size,(232,228,218,0));draw=ImageDraw.Draw(image);previous=(0,0)
    width=max(1,round(payload.get('thread_width_mm',.22)*scale))
    def xy(p):return (round((p[0]+origin[0])*scale),round((p[1]+origin[1])*scale))
    for step in payload['steps']:
        point=(step['x'],step['y'])
        if step['t']=='stitch':draw.line([xy(previous),xy(point)],fill=step['color'],width=width)
        previous=point
    return image


def local_contrast(rgb,window):
    lab=rgb2lab(rgb/255)
    return np.max(maximum_filter(lab,size=(window,window,1))-minimum_filter(lab,size=(window,window,1)),axis=2)


def worklist(source,prepared,payload,report,min_area=.25):
    from .detail_loss import groups,hex_colour,location
    src=np.asarray(source.convert('RGBA'));out=np.asarray(prepared);h,w=out.shape[:2];height=report['height_mm'];scale=height/h
    rendered=aligned_stitches(payload,(w,h));render=np.array(rendered)
    # Compare both images over the same plain backing; no simulated weave or shine.
    src_rgb=src[:,:,:3].copy();src_rgb[src[:,:,3]<=127]=(232,228,218)
    window=max(3,round(2/scale));window+=1-window%2
    a=local_contrast(src_rgb,window);b=local_contrast(render[:,:,:3],window)
    lost=(src[:,:,3]>127)&(a>=10)&(b<=3)
    patches=[];discarded=0;selected=out[:,:,3]>127
    evidence=report.get('base_detail_loss',report.get('detail_loss',{}))
    for region,box,area in groups(lost):
        if area*scale*scale<min_area:discarded+=1;continue
        x,y,r,bot=box;py,px=np.where(region)
        discrepancies=np.linalg.norm(rgb2lab(src[:,:,:3][region][None]/255)[0]-rgb2lab(render[:,:,:3][region][None]/255)[0],axis=1)
        idx=int(np.argmax(discrepancies));point=[int(px[idx]),int(py[idx])]
        def intersects_evidence(item,key):
            if key not in item:return False
            ex,ey,er,eb=item['bounds'];plane=unpack_mask(item[key],(eb-ey,er-ex))
            remaining=np.linalg.norm(rgb2lab(src[ey:eb,ex:er,:3]/255)-rgb2lab(out[ey:eb,ex:er,:3]/255),axis=2)>3
            return bool(np.any(plane&region[ey:eb,ex:er]&remaining))
        width=min(r-x,bot-y)*scale
        diagnosis='unresolved';reason='Contrast loss is measured, but its pipeline cause is not proven. Inspect before changing anything.';remedies=[];pairs=[]
        roi=selected[y:bot,x:r]
        if not roi.all():
            diagnosis='mask-boundary';reason='This patch is outside or crosses the current selection. A bounded add/remove proposal can change the mask.';remedies=['add-region','subtract-region']
        else:
            for finding in evidence.get('findings',[]):
                fx,fy,fr,fb=finding['bounds']
                if fx<r and fr>x and fy<bot and fb>y and intersects_evidence(finding,'causal_mask_runs'):
                    if finding['cause']=='recorded palette merge':
                        diagnosis='colour-merge';pairs=finding['merged_colours'];reason='The preparation audit records a palette merge here. A local split can preserve a source tone.';remedies=['split-region'];break
            if diagnosis=='unresolved':
                for change in evidence.get('pipeline_changes',[]):
                    cx,cy,cr,cb=change['bounds']
                    if change['stage']=='cleanup' and cx<r and cr>x and cy<bot and cb>y and intersects_evidence(change,'mask_runs'):
                        diagnosis='dropped-small';reason='The preparation audit records minimum-area cleanup here. You can explicitly retain a local source tone.';remedies=['keep-small-region'];break
            # A physical warning prevents an artwork correction being sold as a sewability fix.
            target=out[point[1],point[0],:3];original=src[point[1],point[0],:3]
            tone_distance=float(np.linalg.norm(rgb2lab(target[None,None]/255)-rgb2lab(original[None,None]/255)))
            if tone_distance<3:
                colour_region=(np.all(out[:,:,:3]==target,axis=2)&selected).astype(np.uint8)
                _,cc,stats,_=cv2.connectedComponentsWithStats(colour_region,8)
                label=cc[point[1],point[0]]
                if label:width=min(int(stats[label,cv2.CC_STAT_WIDTH]),int(stats[label,cv2.CC_STAT_HEIGHT]))*scale
            if diagnosis=='unresolved' and tone_distance<3 and width<SHAPE_WIDTH_MM:
                diagnosis='physical-limit';reason=knowledge_message('refinement.10', v0=width);remedies=[]
        colours=np.unique(src[y:bot,x:r,:3].reshape(-1,3),axis=0)
        representative=src[point[1],point[0],:3];target=out[point[1],point[0],:3]
        delta=float(np.linalg.norm(rgb2lab(representative[None,None]/255)-rgb2lab(target[None,None]/255)))
        patches.append(dict(id=hashlib.sha256(json.dumps(box).encode()).hexdigest()[:12],bounds=box,point=point,position=location(box,w,h),
            pixels=area,area_mm2=round(area*scale*scale,4),width_mm=round(width,3),canvas_height_for_shape_mm=round(height*SHAPE_WIDTH_MM/max(width,1e-9),2),
            source_contrast=round(float(a[region].max()),3),stitch_contrast=round(float(b[region].max()),3),score=round(float((a-b)[region].mean()*area*scale*scale),4),
            diagnosis=diagnosis,reason=reason,remedies=remedies,source_tone=hex_colour(representative),result_tone=hex_colour(target),delta_e76=round(delta,3),
            recorded_merge_pairs=pairs,source_colours=len(colours)))
    patches.sort(key=lambda p:(-p['score'],p['bounds']))
    return dict(patches=patches,total_lost_area_mm2=round(sum(p['area_mm2'] for p in patches),4),total_lost_contrast_score=round(sum(p['score'] for p in patches),4),discarded_noise_patches=discarded,window_px=window,window_mm=round(window*scale,3),minimum_area_mm2=min_area,
        method='Full-grid Lab contrast on source and actual sewn-command raster; no decorative lighting, sampling or model.',
        note='Screening only. Warning-box width is not an anatomical measurement. Counts can rise when one large lost patch splits. Stitch routing and physical sew-out still need review.'),rendered


def make_operation(source,prepared,patch,kind,options,point=None):
    from .subject_model import propose_mask
    from .preparation import colour
    if kind not in patch['remedies']:raise ValueError('That remedy is not supported by the measured diagnosis.')
    src=np.array(source.convert('RGBA'));out=np.array(prepared);h,w=out.shape[:2]
    x,y,r,b=bounds(patch['bounds'],w,h);point=point or patch['point']
    if not isinstance(point,list) or len(point)!=2 or any(type(v) is not int for v in point) or not x<=point[0]<r or not y<=point[1]<b:raise ValueError('Click inside the selected patch.')
    timing=None
    if kind in ('add-region','subtract-region'):
        candidate,timing=propose_mask(source,[dict(point=point,label=1)],None)
        local=candidate[y:b,x:r]
    else:
        tone=src[point[1],point[0],:3];target=out[point[1],point[0],:3]
        lab=rgb2lab(src[y:b,x:r,:3]/255);tone_lab=rgb2lab(tone[None,None]/255)[0,0];target_lab=rgb2lab(target[None,None]/255)[0,0]
        delta=float(np.linalg.norm(tone_lab-target_lab));threshold=max(0,delta*.45)
        local=np.linalg.norm(lab-tone_lab,axis=2)<=max(.1,threshold)
        _,components=cv2.connectedComponents(local.astype(np.uint8),8)
        component=components[point[1]-y,point[0]-x]
        local=components==component if component else np.zeros_like(local)
    tone=src[point[1],point[0],:3]
    if kind=='add-region':
        palette=np.unique(out[:,:,:3][out[:,:,3]>127],axis=0)
        if len(palette):tone=palette[np.argmin(np.linalg.norm(rgb2lab(palette[None]/255)[0]-rgb2lab(tone[None,None]/255)[0,0],axis=1))]
    op=dict(version=VERSION,type=kind,bounds=[x,y,r,b],point=point,mask_runs=mask_runs(local),colour='#%02x%02x%02x'%tuple(tone),
        image_hash=digest(src),diagnosis=patch['diagnosis'])
    if kind=='split-region':op.update(local_threshold_delta_e76=round(threshold,4),measured_delta_e76=round(delta,4))
    return op,timing


def register_refinement(app,root):
    from flask import request,jsonify,abort
    from .preparation import prepare,load_image,data_url
    from .saved_plans import matching_plan
    @app.post('/refine-warm/<name>')
    def refine_warm(name):
        from .subject_model import warm_image
        path=root/'work'/'uploads'/Path(name).name
        if not path.is_file():abort(404)
        return jsonify(warm_image(load_image(path)))
    @app.post('/refine/<name>')
    def refine(name):
        path=root/'work'/'uploads'/Path(name).name
        if not path.is_file():abort(404)
        try:
            body=request.get_json(silent=True)
            if not isinstance(body,dict) or not isinstance(body.get('options'),dict):raise ValueError('Expected current settings.')
            options=body['options'];source=load_image(path);prepared,palette,report=prepare(path,options)
            saved=matching_plan(root,path,options);payload=saved.get('playback')
            if not payload:return jsonify(error='Generate stitches for the current settings first. Prepared colours are not a substitute for a stitch-plan comparison.'),409
            audit,rendered=worklist(source,prepared,payload,report)
            result=dict(audit=audit,stitch_image=data_url(rendered),history=report.get('refinement_history',[]),colours=len(palette))
            action=body.get('action','check')
            if action=='propose':
                patch=next((p for p in audit['patches'] if p['id']==body.get('id')),None)
                if patch is None:raise ValueError('Patch changed; refresh the worklist.')
                op,timing=make_operation(source,prepared,patch,body.get('remedy'),options,body.get('point'))
                changes={'refinement_ops':options.get('refinement_ops',[])+[op]}
                after,after_palette,after_report=prepare(path,{**options,**changes})
                # A proposal never saves settings or replaces the existing stitch plan.
                result.update(patch=changes,before_image=data_url(prepared),after_image=data_url(after),after_colours=len(after_palette),timing=timing,
                    operation=op,proof=after_report['refinement_history'][-1],note='Artwork proposal only. Accept, then regenerate stitches to measure the new stitch worklist.')
            elif action!='check':raise ValueError('Choose comparison or a diagnosed proposal.')
            return jsonify(result)
        except (ValueError,TypeError,KeyError,OSError,cv2.error) as error:return jsonify(error=str(error)),400
