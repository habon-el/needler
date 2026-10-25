"""Deterministic local subject selection and perceptual artwork reduction."""
from .knowledge_messages import message as knowledge_message
from .preparation_identity import preparation_key
import base64
import io
import json
import hashlib
import math
import threading
import subprocess
from pathlib import Path
import cv2
import numpy as np
from .colour_rows import unique_rows
from PIL import Image, ImageDraw, ImageEnhance, ImageOps
from scipy.ndimage import distance_transform_edt
from skimage.color import rgb2lab, lab2rgb

LOCK = threading.Lock()

def load_image(path):
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGBA")
        image.thumbnail((768, 768), Image.Resampling.LANCZOS)
    image.info["source_sha256"]=hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return image

def number(o, key, default, low, high):
    v = float(o.get(key, default))
    if not math.isfinite(v) or not low <= v <= high:
        raise ValueError(f"{key} must be between {low} and {high}.")
    return v

def colour(value):
    if not isinstance(value,str) or len(value)!=7 or value[0]!="#":
        raise ValueError("Use a six-digit hexadecimal colour.")
    return tuple(int(value[i:i+2],16) for i in (1,3,5))

def points(value,w,h,minimum=1):
    if not isinstance(value,list) or not minimum<=len(value)<=10000:
        raise ValueError("Invalid selection points.")
    result=[]
    for p in value:
        if len(p)!=2: raise ValueError("Invalid point.")
        x,y=map(float,p)
        if not math.isfinite(x+y) or not 0<=x<w or not 0<=y<h:
            raise ValueError("Selection must be inside the artwork.")
        result.append((min(w-1,round(x)),min(h-1,round(y))))
    return result

def edit_brush(edit, w, h):
    """One image-space footprint shared by prepared and source-colour previews."""
    pts = points(edit["points"], w, h, 3 if edit.get("shape") == "polygon" else 1)
    brush = np.zeros((h, w), np.uint8)
    radius = int(number(edit, "radius", 8, 1, 80))
    if edit.get("shape") == "polygon":
        cv2.fillPoly(brush, [np.array(pts, np.int32)], 1)
        # A clicked area can have holes (the circle around a star): they are kept.
        holes = edit.get("holes") or []
        if not isinstance(holes, list) or len(holes) > 200: raise ValueError("Invalid area holes.")
        for hole in holes:
            cv2.fillPoly(brush, [np.array(points(hole, w, h, 3), np.int32)], 0)
    else:
        cv2.polylines(brush, [np.array(pts, np.int32)], False, 1, radius * 2)
        for p in (pts[0], pts[-1]):
            cv2.circle(brush, p, radius, 1, -1)
    return brush > 0


def selection(image,o):
    image=image.convert('RGBA')
    rgb=np.asarray(image.convert("RGB"));h,w=rgb.shape[:2]
    mask=np.asarray(image.getchannel("A"))>127
    mode=o.get("selection","full")
    if mode=="assisted":
        from .subject_model import unpack_mask
        mask &= unpack_mask(o.get("mask_runs"), (h,w))
    elif mode=="lasso":
        plane=Image.new("L",(w,h))
        ImageDraw.Draw(plane).polygon(points(o.get("outline"),w,h,3),fill=255)
        mask &= np.asarray(plane)>0
    elif mode=="grabcut":
        rect=o.get("rect",[])
        if not isinstance(rect,(list,tuple)) or len(rect)!=4:
            raise ValueError("Click and drag a rectangle around the subject, or choose Use full image.")
        coordinates=list(map(float,rect))
        if not all(math.isfinite(v) for v in coordinates):
            raise ValueError("Draw the rectangle inside the image.")
        if not 0<=coordinates[0]<=coordinates[2]<=w or not 0<=coordinates[1]<=coordinates[3]<=h:
            raise ValueError("Draw the rectangle inside the image.")
        x,y,r,b=map(int,coordinates)
        if x>=r or y>=b:
            raise ValueError("Click and drag to give the rectangle width and height, or choose Use full image.")
        labels=np.zeros((h,w),np.uint8);labels[y:b,x:r]=cv2.GC_PR_FGD
        hints=o.get("hints",[])
        if len(hints)>500: raise ValueError("Too many selection strokes.")
        for hint in hints:
            pts=points(hint["points"],w,h)
            radius=int(number(hint,"radius",8,1,80))
            val=cv2.GC_FGD if hint.get("kind")=="keep" else cv2.GC_BGD
            cv2.polylines(labels,[np.array(pts,np.int32)],False,val,radius*2)
            for p in (pts[0],pts[-1]): cv2.circle(labels,p,radius,val,-1)
        labels[~mask]=cv2.GC_BGD
        if not np.any((labels==3)|(labels==1)):
            raise ValueError("The rectangle contains no visible subject. Draw around the letters or choose Use full image.")
        # Existing transparency is a cutout, not training data for colour-based
        # segmentation. Transparent RGB may equal the ink RGB exactly. Preserve
        # visible pixels/counters inside the rectangle and explicit brush hints.
        if np.all(mask):
            if not np.any(labels==0):
                raise ValueError("Leave some background outside the rectangle, or choose Use full image to keep everything.")
            with LOCK:
                cv2.setRNGSeed(0)
                cv2.grabCut(rgb,labels,None,np.zeros((1,65)),np.zeros((1,65)),3,cv2.GC_INIT_WITH_MASK)
        mask &= (labels==1)|(labels==3)
    elif mode!="full": raise ValueError("Unknown selection method.")
    edge=int(number(o,"edge",0,-8,8))
    if edge:
        kernel=np.ones((abs(edge)*2+1,)*2,np.uint8)
        mask=(cv2.dilate if edge>0 else cv2.erode)(mask.astype(np.uint8),kernel)>0
        mask &= np.asarray(image.getchannel("A"))>127
    return mask


def cached_selection(path,image,options,directory=None):
    """Persist the binary selection independently of colour/digitizing settings."""
    if directory is None:
        return selection(image,options)
    keys=("selection","rect","outline","hints","edge","mask_runs")
    settings={key:options[key] for key in keys if key in options}
    # 32 hex digits keep cache paths well under Windows' 260-character limit.
    digest=hashlib.sha256(Path(path).read_bytes()+json.dumps(settings,sort_keys=True).encode()+b"selection-v2-alpha").hexdigest()[:32]
    directory.mkdir(parents=True,exist_ok=True)
    target=directory/(digest+".png")
    if target.exists():
        with Image.open(target) as saved:
            pixels=np.asarray(saved)
        if pixels.shape==np.asarray(image.getchannel("A")).shape and np.all((pixels==0)|(pixels==255)):
            return pixels>0
    mask=selection(image,options)
    # Atomic rename prevents a simultaneous preview from reading a partial PNG.
    from uuid import uuid4
    temporary=directory/(digest+"."+uuid4().hex[:12]+".tmp")
    Image.fromarray(mask.astype(np.uint8)*255).save(temporary,format="PNG")
    temporary.replace(target)
    return mask

def clean_selection(mask,image,options,pixel_area_override=None):
    """Clean only the binary mask, and report changes separately from colours."""
    original=mask.copy();h,w=mask.shape
    protected=options.get("protect_selection",False)
    if type(protected) is not bool: raise ValueError("Selection protection must be true or false.")
    floor=0 if protected else number(options,"floor_mm2",1,0,25)
    hole_floor=0 if protected else number(options,"mask_holes_mm2",1,0,25)
    smooth=0 if protected else int(number(options,"mask_smooth",0,0,2))
    pixel_area=pixel_area_override if pixel_area_override is not None else (number(options,"height_mm",100,3,400)/h)**2
    removed=filled=0
    n,cc,stats,_=cv2.connectedComponentsWithStats(mask.astype(np.uint8),8)
    before=n-1
    for i in range(1,n):
        if stats[i,cv2.CC_STAT_AREA]*pixel_area<floor:
            mask[cc==i]=False;removed+=1
    n,cc,stats,_=cv2.connectedComponentsWithStats((~mask).astype(np.uint8),8)
    border=set(np.unique(np.concatenate((cc[0],cc[-1],cc[:,0],cc[:,-1]))))
    for i in range(1,n):
        if i not in border and stats[i,cv2.CC_STAT_AREA]*pixel_area<hole_floor:
            mask[cc==i]=True;filled+=1
    before_smooth=mask.copy()
    if smooth:
        mask=cv2.medianBlur(mask.astype(np.uint8),smooth*2+1)>0
    smooth_pixels=int(np.sum(mask!=before_smooth))
    # Explicit correction strokes win over automatic cleanup.
    if options.get("hints"):
        if len(options["hints"])>500: raise ValueError("Too many selection strokes.")
        for hint in options.get("hints",[]):
            pts=points(hint["points"],w,h)
            radius=int(number(hint,"radius",8,1,80))
            brush=np.zeros((h,w),np.uint8)
            cv2.polylines(brush,[np.array(pts,np.int32)],False,1,radius*2)
            for p in (pts[0],pts[-1]): cv2.circle(brush,p,radius,1,-1)
            mask[brush>0]=hint.get("kind")=="keep"
    mask &= np.asarray(image.getchannel("A"))>127
    from .cleanup_review import review_changes
    mask,cleanup_review=review_changes(original,mask,options,math.sqrt(pixel_area),'selection cleanup')
    n,cc,stats,_=cv2.connectedComponentsWithStats(mask.astype(np.uint8),8)
    report=dict(mask_cleanup_review=cleanup_review,mask_regions_before=before,mask_regions_after=n-1,
        mask_specks_removed=removed,mask_holes_filled=filled,
        mask_boundary_pixels_changed=smooth_pixels,mask_pixels_changed=int(np.sum(mask!=original)),
        mask_below_floor_after=int(sum(stats[i,cv2.CC_STAT_AREA]*pixel_area<floor for i in range(1,n))))
    return mask,report

def components(labels):
    items=[]
    for label in np.unique(labels[labels>=0]):
        n,cc,stats,_=cv2.connectedComponentsWithStats((labels==label).astype(np.uint8),8)
        for i in range(1,n): items.append((int(label),cc,i,int(stats[i,cv2.CC_STAT_AREA])))
    return items

def match_thread(hexcode):
    """Offer perceptual catalogue matches without changing artwork colours."""
    from .thread_matching import rank_threads
    matches=rank_threads(hexcode)
    return {**matches[0],"alternatives":matches} if matches else None

THREAD_WIDTH_MM=.4

def absorb_edge_specks(labels,mm_per_px,locked=()):
    """Merge antialiasing fragments into the neighbouring colours, in place.

    Only a colour fragment thinner than one thread width everywhere (it cannot
    be sewn as its own colour) that lies on a boundary between two different
    neighbours: two colours, or a colour and transparency. Each pixel takes its
    nearest neighbouring colour. A thin or tiny detail surrounded by a single
    colour (an eye, a dot, a hairline) is never merged and still needs a decision.
    """
    merged=0
    for label in [int(v) for v in np.unique(labels) if v>=0 and v not in locked]:
        plane=(labels==label).astype(np.uint8)
        n,cc,stats,_=cv2.connectedComponentsWithStats(plane,8)
        for i in range(1,n):
            x,y,w,h,_=map(int,stats[i])
            x0,y0=max(0,x-2),max(0,y-2);x1,y1=min(labels.shape[1],x+w+2),min(labels.shape[0],y+h+2)
            piece=(cc[y0:y1,x0:x1]==i)
            thickness=2*cv2.distanceTransform(np.pad(piece,1).astype(np.uint8),cv2.DIST_L2,3).max()
            if thickness*mm_per_px>=THREAD_WIDTH_MM:continue
            window=labels[y0:y1,x0:x1]
            ring=cv2.dilate(piece.astype(np.uint8),np.ones((3,3),np.uint8)).astype(bool)&~piece
            around=window[ring];around=around[around!=label]
            if len(np.unique(around))<2 or not np.any(around>=0):continue
            others=(window>=0)&~piece
            _,nearest=distance_transform_edt(~others,return_indices=True)
            window[piece]=window[nearest[0][piece],nearest[1][piece]];merged+=1
    return merged

def prepare(path,o,mask_directory=None,target_height_mm=None):
    requested_options=o
    knockout=bool(o.get("colour_knockouts"))
    if knockout:
        if o.get('artwork_type','logo')!='logo':
            raise ValueError('Colour removal currently requires colour artwork mode, not Portrait. Switch modes before previewing removal.')
        if o.get('refinement_ops'):
            raise ValueError('Colour removal cannot be combined with saved local recovery patches yet. Undo those patches or work on a copy before removing a colour.')
        # Colour removal is authoritative: generic cleanup must not refill its holes
        # or drop disconnected punctuation. Stored cleanup settings remain unchanged.
        o={**o,"floor_mm2":0,"smooth":0,"simplify":0,"protect_selection":True}
    ink_only=o.get("ink_only") is True
    if ink_only:
        from .ink_lines import line_settings
        line_settings(o)
        if o.get("artwork_type","logo")!="logo" or o.get("border_style","off")!="off" or o.get("refinement_ops"):
            raise ValueError("Black lines only requires Logo mode, No border, and no local recovery operations.")
        # Effective overrides only: turning the mode off restores the saved cleanup choices.
        o={**o,"smooth":0,"simplify":0,"floor_mm2":0,"protect_selection":True,"locks":["#000000"],"merges":{}}
    line_art=o.get("line_art") is True
    if line_art:
        if ink_only or o.get("artwork_type","logo")!="logo" or o.get("border_style","off")!="off" or o.get("refinement_ops") or o.get("colour_knockouts"):
            raise ValueError("Line art needs Logo mode, No border, Black lines only off and no colour removal; the dark background is left out automatically.")
        # Thin strokes are the design: no smoothing, cleanup or speck merging.
        o={**o,"smooth":0,"simplify":0,"floor_mm2":0,"protect_selection":True,"merges":{}}
    if o.get("refinement_ops"):
        from .refinement import prepare_replayed
        return prepare_replayed(path,o,mask_directory,target_height_mm)
    portrait_mode=o.get('artwork_type','logo')=='portrait'
    if o.get('artwork_type','logo') not in {'logo','portrait'}:raise ValueError('Choose logo or portrait artwork mode.')
    if portrait_mode:
        from . import portrait as profile
        o={**profile.proposal(),**o}
        if float(o.get('floor_mm2',0))<profile.PORTRAIT_MIN_REGION_AREA_MM2:raise ValueError(knowledge_message('preparation.09'))
    image=load_image(path);w,h=image.size
    physical_height=number(o,"height_mm",100,3,400) if target_height_mm is None else float(target_height_mm)
    if not math.isfinite(physical_height) or not 1<=physical_height<=10000:
        raise ValueError(knowledge_message('preparation.08'))
    mask=cached_selection(path,image,o,mask_directory)
    detail_original_mask=mask.copy()
    if portrait_mode:original_mask=mask.copy()
    mask,mask_report=clean_selection(mask,image,o,(physical_height/h)**2)
    detail_cleaned_mask=mask.copy()
    rgb=np.array(ImageEnhance.Contrast(ImageEnhance.Brightness(image.convert("RGB")).enhance(number(o,"brightness",1,.3,2))).enhance(number(o,"contrast",1,.3,3)))
    edits=o.get("edits",[])
    if len(edits)>500: raise ValueError("Too many paint strokes.")
    for edit in edits:
        brush=edit_brush(edit,w,h)
        if edit.get("kind")=="erase": mask[brush]=False
        else: rgb[brush&mask]=colour(edit["colour"])
    from .colour_knockout import apply_operations, propose_background
    rgb,mask,knockout_reports=apply_operations(rgb,mask,o,physical_height,np.asarray(image.getchannel("A"))>127)
    if ink_only and any(r["restored_pixels"] for r in knockout_reports):
        raise ValueError("Turn off Black lines only before keeping intentional white parts.")
    if ink_only:
        from .ink_lines import ink_mask
        mask &= ink_mask(rgb)
        rgb[mask]=0
    if line_art:
        # Light strokes on a dark background: each stroke pixel takes its
        # thread colour; the background is not stitched.
        from .line_art import colour_layers
        strokes=np.zeros(mask.shape,bool);tones=[]
        for tone,layer in colour_layers(rgb):
            layer=layer&mask
            if layer.any():rgb[layer]=colour(tone);strokes|=layer;tones.append(tone)
        mask&=strokes
        o={**o,"locks":tones,"count":max(2,len(tones))}
    if np.count_nonzero(mask)<5: raise ValueError("The selection is empty. Restore or enlarge the subject.")
    k=int(number(o,"count",profile.PORTRAIT_COLOUR_DEFAULT if portrait_mode else 4,8 if portrait_mode else 2,profile.PORTRAIT_COLOUR_MAX if portrait_mode else 8))
    locks=list(dict.fromkeys(o.get("locks",[])))
    if len(locks)>k: raise ValueError("Unlock colours or increase the colour count.")
    locked_rgb=[colour(c) for c in locks]
    floor=number(o,"floor_mm2",1,0,25);height=physical_height
    simplify=number(o,"simplify",0,0,100);smooth=int(number(o,"smooth",1,0,3))
    source_colours=unique_rows(rgb[mask])
    before_colours=len(source_colours)
    detail_source=rgb.copy()
    detail_selected=mask.copy()
    detail_stages={}
    def detail_rgb():
        plane=np.zeros((h,w,3),np.uint8);valid=labels>=0;plane[valid]=palette[labels[valid]];return plane
    if simplify:
        rgb=cv2.bilateralFilter(rgb,5,5+simplify*.6,3)
        detail_stages["simplify"]=(detail_source,rgb)
    pixels=rgb2lab(rgb/255)[mask];sample=pixels[::max(1,len(pixels)//15000)]
    # A sampling stride can miss an entire eye, dot or thin outline. When all
    # source colours fit the requested palette, retain each exactly. Portraits
    # and explicit simplification retain their existing reduction policy.
    exact_colours=np.unique(np.concatenate((source_colours,
        np.array(locked_rgb,dtype=np.uint8).reshape(-1,3))),axis=0)
    exact_flat=not portrait_mode and not simplify and len(exact_colours)<=k
    if exact_flat:
        sample=rgb2lab(exact_colours[None]/255)[0]
    if portrait_mode:
        for feature in profile.feature_boxes(o,w,h):
            x,y,r,b=feature['bounds'];roi=rgb[y:b,x:r][mask[y:b,x:r]]
            if len(roi):
                weighted=rgb2lab(roi[None]/255)[0][::max(1,len(roi)//1000)]
                sample=np.concatenate([sample,np.tile(weighted,(profile.PORTRAIT_FEATURE_SAMPLE_WEIGHT,1))])
    centers=list(rgb2lab(np.array(locked_rgb,dtype=float)[None]/255)[0]) if locks else [sample[len(sample)//2]]
    while len(centers)<k:
        d=np.min(np.sum((sample[:,None]-np.array(centers)[None])**2,axis=2),axis=1)
        if d.max()<1e-10: break
        centers.append(sample[np.argmax(d)])
    centers=np.array(centers)
    for _ in range(12):
        assigned=np.argmin(np.sum((sample[:,None]-centers[None])**2,axis=2),axis=1)
        for i in range(len(locks),len(centers)):
            if np.any(assigned==i): centers[i]=sample[assigned==i].mean(axis=0)
    palette=np.clip(np.rint(lab2rgb(centers[None])[0]*255),0,255).astype(np.uint8)
    for i,v in enumerate(locked_rgb): palette[i]=v
    assigned=np.concatenate([np.argmin(np.sum((pixels[start:start+20000,None]-centers[None])**2,axis=2),axis=1) for start in range(0,len(pixels),20000)])
    labels=np.full((h,w),-1,np.int16);labels[mask]=assigned
    detail_stages["quantization"]=(rgb,detail_rgb())
    detail_premerge=detail_rgb()
    portrait_merges=[]
    if portrait_mode:
        lab_palette=rgb2lab(palette[None]/255)[0]
        for i in range(len(palette)):
            if i<len(locks):continue
            for j in range(i):
                distance=float(np.linalg.norm(lab_palette[i]-lab_palette[j]))
                if distance<number(o,"portrait_merge_delta_e",profile.PORTRAIT_MERGE_DELTA_E,0,100):
                    portrait_merges.append(dict(source='#%02x%02x%02x'%tuple(palette[i]),target='#%02x%02x%02x'%tuple(palette[j]),delta_e=distance,pixels=int(np.sum(labels==i))))
                    palette[i]=palette[j];break
    for a,b in o.get("merges",{}).items():
        if a in locks: raise ValueError("Unlock a colour before merging it.")
        # Exact match first; otherwise the palette colour within a small distance, because
        # other settings (smoothing, colour count) shift the palette slightly between runs.
        hit=np.all(palette==colour(a),axis=1)
        if not hit.any() and len(palette):
            gap=np.abs(palette.astype(int)-np.array(colour(a),int)).sum(1)
            hit=(gap==gap.min())&(gap<=36)
        palette[hit]=colour(b)
    palette,remap=unique_rows(palette,return_inverse=True)
    labels[mask]=remap[labels[mask]]
    detail_stages["merge"]=(detail_premerge,detail_rgb())
    locked_ids={i for i,p in enumerate(palette) if tuple(p) in locked_rgb}
    # Before cleanup review: antialiasing fragments are not decisions for the user.
    edge_specks=0 if portrait_mode or line_art else absorb_edge_specks(labels,height/h,locked_ids)
    before=components(labels);px_mm2=(height/h)**2
    if portrait_mode:portrait_original_labels=labels.copy()
    small_before=sum(area*px_mm2<floor for _,_,_,area in before)
    detail_presmooth=detail_rgb()
    review_before_labels=labels.copy()
    smoothing_pixels=0
    if smooth:
        original_labels=labels.copy()
        labels=cv2.medianBlur((labels+1).astype(np.uint8),smooth*2+1).astype(np.int16)-1
        labels[~mask]=-1
        missing=mask&(labels<0);labels[missing]=original_labels[missing]
        # Locked colour pixels are preserved, including fine details.
        for i in locked_ids: labels[original_labels==i]=i
        smoothing_pixels=int(np.sum(labels!=original_labels))
    detail_stages["smooth"]=(detail_presmooth,detail_rgb())
    detail_preclean=detail_rgb()
    threshold=floor*(1+simplify/25)
    removable=np.zeros((h,w),bool);cleaned=0
    for label,cc,i,area in components(labels):
        if area*px_mm2<threshold and label not in locked_ids:
            removable |= cc==i;cleaned+=1
    survivors=(labels>=0)&~removable
    # A tiny disconnected subject island cannot be merged across transparency.
    # Delete it explicitly rather than recolouring it into another tiny island.
    deleted_islands=0
    n,subject_cc,_,_=cv2.connectedComponentsWithStats((labels>=0).astype(np.uint8),8)
    for i in range(1,n):
        island=subject_cc==i
        if not np.any(survivors & island):
            removable[island]=False
            if o.get("protect_selection") is not True:
                labels[island]=-1;deleted_islands+=1
    if np.any(survivors):
        nearest=distance_transform_edt(~survivors,return_distances=False,return_indices=True)
        labels[removable]=labels[tuple(nearest[:,removable])]
    elif o.get("protect_selection") is not True: labels[removable]=-1
    from .cleanup_review import review_changes
    labels,colour_cleanup_review=review_changes(review_before_labels,labels,o,height/h,'colour cleanup')
    after=components(labels);kept=labels>=0
    output=np.zeros((h,w,4),np.uint8);output[kept,:3]=palette[labels[kept]];output[kept,3]=255
    detail_stages["cleanup"]=(detail_preclean,detail_rgb())
    from .detail_loss import check as check_details,recover as recover_details
    if portrait_mode:detail_cleanup_records=profile.removal_records(portrait_original_labels,labels,palette,height/h,height)
    if o.get("detail_recoveries"):
        output=recover_details(output,detail_source,o)
        palette,inverse=unique_rows(output[kept,:3],return_inverse=True)
        labels[kept]=inverse
        after=components(labels)
        locked_ids={i for i,p in enumerate(palette) if tuple(p) in locked_rgb}
    detail_audit=check_details(detail_source,output,detail_selected,height,detail_stages,threshold)
    from .detail_loss import groups as detail_groups
    detail_audit["mask_cleanup_changes"]=[dict(bounds=bounds,pixels=area,area_mm2=round(area*(height/h)**2,4)) for _,bounds,area in detail_groups(detail_original_mask!=detail_cleaned_mask)]
    swatches=[dict(hex="#%02x%02x%02x"%tuple(palette[i]),pixels=int(np.sum(labels==i)),locked=i in locked_ids) for i in np.unique(labels[kept])]
    for swatch in swatches:
        swatch["match"]=match_thread(swatch["hex"])
    report=dict(colours_before=before_colours,colours_after=len(swatches),regions_before=len(before),regions_after=len(after),
        below_floor_before=small_before,below_floor_after=sum(area*px_mm2<floor for _,_,_,area in after),
        boundary_pixels_changed=smoothing_pixels,specks_reassigned=cleaned,edge_specks_merged=edge_specks,isolated_subject_islands_removed=deleted_islands,floor_mm2=floor,cleanup_floor_mm2=threshold,
        width_px=w,height_px=h,height_mm=height,interactions=int(number(o,"interactions",0,0,100000)),
        note="Area heuristic only: narrow features, fabric and stitch type still require review.")
    report["minimum_region_area_before_mm2"]=min((area*px_mm2 for _,_,_,area in before),default=0)
    report["small_features"]=[]
    for label,cc,i,area in after:
        if area*px_mm2<floor and len(report["small_features"])<100:
            ys,xs=np.where(cc==i)
            report["small_features"].append(dict(colour="#%02x%02x%02x"%tuple(palette[label]),
                area_mm2=float(area*px_mm2),bounds=[int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)]))
    # Report the final prepared pixels, including any explicit thread recolouring,
    # not just the intermediate knockout mask.
    if knockout_reports:
        from .colour_knockout import hex_rgb
        final_lab=rgb2lab(output[:,:,:3]/255)
        for removal in knockout_reports:
            target=rgb2lab(hex_rgb(removal['operation']['colour'])[None,None]/255)[0,0]
            remaining=(np.linalg.norm(final_lab-target,axis=2)<=removal['operation']['tolerance'])&kept
            removal['remaining_colour_area_mm2']=float(remaining.sum()*px_mm2)
    report["colour_knockouts"]=knockout_reports
    report["background_proposal"]=None if knockout else propose_background(image)
    report["ink_only"]=ink_only
    report["line_art"]=line_art
    if line_art:report["note"]="Line art: strokes are sewn as continuous running-stitch lines in their own colours; the dark background is not stitched. Review fine hatching and physical sewability."
    if ink_only:report["note"]="Black ink only: white is transparent and receives no stitches. Cleanup is bypassed to retain thin ink. Review faint marks and physical sewability."
    report['cleanup_review']=mask_report.get('mask_cleanup_review',[])+colour_cleanup_review
    report['automatic_changes']=bool(any(r['removed'] for r in report['cleanup_review']) or detail_audit['pipeline_changes'] or detail_audit['mask_cleanup_changes'])
    report["detail_loss"]=detail_audit
    report.update(mask_report)
    if portrait_mode:
        report['artwork_type']='portrait'
        report['portrait_features']=profile.feature_report(Image.fromarray(output),o,height)
        report['portrait_removals']=detail_cleanup_records
        report['portrait_mask_removals']=profile.removal_records(np.where(original_mask,0,-1),np.where(mask,0,-1),np.array([[0,0,0]],np.uint8),height/h,height)
        report['portrait_merges']=portrait_merges
        report['portrait_policy']=dict(colour_max=profile.PORTRAIT_COLOUR_MAX,merge_delta_e=number(o,"portrait_merge_delta_e",profile.PORTRAIT_MERGE_DELTA_E,0,100),small_cluster_fraction=profile.PORTRAIT_SMALL_CLUSTER_FRACTION,min_region_area_mm2=profile.PORTRAIT_MIN_REGION_AREA_MM2)
    from .borders import border_plan
    report['border']=border_plan(output[:,:,3]>127,physical_height,o)
    from .fill_coverage import missing_boundaries
    report['generation_blockers']=([] if ink_only or line_art or portrait_mode else
        missing_boundaries(output[:,:,:3],output[:,:,3]>127,physical_height/h))
    from .region_stitches import inventory
    report['stitch_regions']=inventory(output[:,:,:3],output[:,:,3]>127,physical_height/h,o)
    from .piece_layout import inventory as piece_inventory, render as render_pieces, geometry_changed
    report['piece_layout']=piece_inventory(report['stitch_regions'],{**o,'floor_mm2':requested_options.get('floor_mm2',1)},w,h,physical_height/h)
    for piece in report['piece_layout']['pieces']:
        piece['thread_name']=next(((s.get('match') or {}).get('name',piece['colour']) for s in swatches if s['hex']==piece['colour']),piece['colour'])
    if geometry_changed(o):
        return render_pieces(Image.fromarray(output),report['piece_layout']),swatches,report
    return Image.fromarray(output),swatches,report

def data_url(image):
    stream=io.BytesIO();image.save(stream,format="PNG")
    return "data:image/png;base64,"+base64.b64encode(stream.getvalue()).decode()

def register_preparation(app,root):
    from flask import abort,jsonify,render_template,request
    from .detail_loss import register_details
    register_details(app,root)
    from .refinement import register_refinement
    register_refinement(app,root)
    uploads,decisions=root/"work"/"uploads",root/"work"/"decisions"
    from .saved_plans import matching_plan
    @app.route("/artwork/<name>",methods=["GET","POST"])
    def artwork_prepare(name):
        path=uploads/Path(name).name
        if request.method == 'GET' and request.args.get('native_text'):
            from flask import redirect, url_for
            return redirect(url_for('workspace', key=request.args['native_text']))
        if not path.is_file(): abort(404)
        metadata=path.with_suffix(".prep.json")
        if request.method=="GET" and metadata.exists():
            from flask import redirect, url_for
            source=json.loads(metadata.read_text()).get("source")
            if source and (uploads/Path(source).name).is_file():
                return redirect(url_for("artwork_prepare",name=Path(source).name,**({"view":"stitched"} if request.args.get("view")=="stitched" else {})))
        saved=decisions/(path.name+".preparation.json")
        if request.method=="GET":
            options=json.loads(saved.read_text()) if saved.exists() else {}
            fingerprint=preparation_key(path.read_bytes(),options)
            restored=matching_plan(root,path,options)
            previous=restored.get("playback")
            from .colour_knockout import defaults as knockout_defaults
            from .lettering_size import saved_metrics
            return render_template("artwork.html",knockout_seed=knockout_defaults(),name=path.name,options=options,original=data_url(load_image(path)),
                lettering_metrics=saved_metrics(decisions,path.name),
                previous=previous,simulation=restored.get("simulation","/engine/prepared_"+fingerprint+".png?view=1"))

        try:
            body=request.get_json()
            if not isinstance(body,dict) or not isinstance(body.get("options"),dict): raise ValueError("Expected preparation settings.")
            if body.get('digitize') and (decisions/(path.name+'.lettering.json')).is_file():
                raise ValueError('This saved text is picture-based. Open Text, choose an embroidery font, then Build & check stitches. Your original font and picture are unchanged.')
            options=body["options"]
            from .piece_layout import guard as guard_pieces, change as change_pieces
            previous_options=json.loads(saved.read_text()) if saved.exists() else {}
            guard_pieces(previous_options,options)
            piece_command=body.get('piece_command')
            if piece_command or body.get('piece_undo'):
                expected=hashlib.sha256(saved.read_bytes()).hexdigest() if saved.exists() else None
                if body.get('piece_revision')!=expected:
                    return jsonify(error='This design changed in another window. Reload before editing pieces.'),409
            if piece_command:
                prepared_image,_,current_report=prepare(path,options,decisions/(path.name+'.masks'))
                options=change_pieces(options,current_report['piece_layout'],piece_command,
                                      image=prepared_image.convert('RGBA') if piece_command.get('field')=='click_fill' else None)
                body['save']=True
                if piece_command['field'] in ('position','x_mm','y_mm','width_mm','height_mm','rotation','style','visible','outline'):
                    body['digitize']=True
            if body.get('piece_undo'):
                body['save']=True
                body['digitize']=True
            if body.get("digitize") and body.get("subject_confirmed") is not True:
                raise ValueError("Confirm the isolated subject before generating stitches.")
            image,palette,report=prepare(path,options,decisions/(path.name+".masks"))
            pieces=report['piece_layout']['pieces']
            piece_blocked=bool(options.get('piece_edits')) and (not any(p['visible'] for p in pieces) or any(p['visible'] and p['audit']['level']=='red' for p in pieces))
            if piece_blocked and body.get('digitize'):
                if piece_command or body.get('piece_undo'):body['digitize']=False
                else:raise ValueError('Check the red pieces or show a piece before generating stitches. Nothing was removed.')
            isolated=load_image(path)
            subject_mask=cached_selection(path,isolated,options,decisions/(path.name+".masks"))
            subject_mask,_=clean_selection(subject_mask,isolated,{**options,"protect_selection":True} if options.get("colour_knockouts") else options)
            for edit in options.get("edits", []):
                if edit.get("kind") == "erase":
                    subject_mask[edit_brush(edit, *isolated.size)] = False
            if options.get("colour_knockouts"):
                # Subject and Thread plan must agree about holes. Keep source colours
                # except for explicitly accepted knockout/brush-texture correction.
                from .colour_knockout import apply_operations
                source_rgb,subject_mask,_=apply_operations(np.array(isolated.convert("RGB")),subject_mask,options,
                    report["height_mm"],np.asarray(isolated.getchannel("A"))>127)
                isolated=Image.fromarray(source_rgb).convert("RGBA")
            isolated.putalpha(Image.fromarray(subject_mask.astype(np.uint8)*255))
            response=dict(image=data_url(image),isolated=data_url(isolated),palette=palette,report=report)
            if piece_command or body.get('piece_undo'):response['options']=options
            response['piece_blocked']=piece_blocked
            if not body.get("digitize"):
                response.update(matching_plan(root,path,options))
            if body.get("save") or body.get("digitize"):
                pending = [item for item in report['cleanup_review'] if item['decision'] == 'pending']
                if pending:
                    # Return the review, without saving files or approving any changes.
                    return jsonify(**response, code='cleanup_review_required',
                        error=f'Review cleanup before approving: {len(pending)} small areas may change. '
                              'Choose Keep all pending details or review them individually.'), 400
                if body.get('digitize'):
                    from .fill_coverage import require_boundaries
                    require_boundaries(report['generation_blockers'])
                if not palette: raise ValueError("Cleanup removed the entire subject. Lower the size floor.")
                fingerprint=preparation_key(path.read_bytes(),options)
                prepared_name="prepared_"+fingerprint+".png";target=uploads/prepared_name
                image.save(target)
                image.getchannel("A").save(decisions/(prepared_name+".mask.png"))
                target.with_suffix(".prep.json").write_text(json.dumps(dict(source=path.name,options=options,report=report,version=2),sort_keys=True))
                response.update(prepared_name=prepared_name,review="/review/"+prepared_name)
                if body.get("digitize"):
                    from .engine import digitize
                    payload=digitize(target,root/"work"/"inkstitch-preview"/target.stem,report["height_mm"])
                    response.update(playback=payload,simulation="/engine/"+prepared_name+"?view=1")
                temporary=saved.with_suffix('.pending.json')
                temporary.write_text(json.dumps(options,sort_keys=True));temporary.replace(saved)
            if piece_blocked:response.pop('playback',None)
            response['piece_revision']=hashlib.sha256(saved.read_bytes()).hexdigest() if saved.exists() else None
            return jsonify(response)
        except subprocess.TimeoutExpired:
            return jsonify(error='Stitch generation exceeded its time limit. No new stitch plan or settings were saved. Try a smaller target size or fewer complex regions; review any detail changes before applying.'),504
        except (ValueError,TypeError,KeyError,cv2.error,OSError) as error:
            return jsonify(error=str(error)),400
