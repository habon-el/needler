"""Native stitch generation: selected colour masks to real fill objects."""
from pathlib import Path
import json
import math
import xml.etree.ElementTree as ET
import cv2
import numpy as np
from .colour_rows import unique_rows
from PIL import Image
import pyembroidery as emb
from .regions import artwork_rgb, _quantize

SVG='http://www.w3.org/2000/svg'

from .engine_cache import serialize_output
from .machine_files import write_pair
from .stitch_engine import generate_plan, NAME as ENGINE_NAME

PUFF_TO_MM=6.0   # widest point of an area that can puff (largest inscribed circle); the narrowest depends on the foam
SMALL_SATIN_MM=4.5   # areas no thicker than this are sewn as satin columns
SATIN_PULL_MM=.1     # per side: satin pulls the fabric in by about this much


GRID_ROUNDING_MM=.05  # machine files store 0.1 mm steps: up to 0.05 mm rounding per axis


def grid_allowance(mask,scale):
    """On very small designs one pixel is finer than machine-file rounding;
    widen the stitched area's edge by the rounding (the gate allows one pixel).
    Not used with colour removal, whose holes must stay exact."""
    extra=math.ceil(GRID_ROUNDING_MM/scale-1e-9)-1
    if extra<=0:return mask
    kernel=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(2*extra+1,2*extra+1))
    return cv2.dilate(mask.astype(np.uint8),kernel).astype(bool)


def thickness_mm(rings,scale):
    """Widest point of an area (largest inscribed circle diameter) in mm."""
    x,y,w,h=cv2.boundingRect(np.vstack(rings))
    plane=np.zeros((h+2,w+2),np.uint8)
    cv2.drawContours(plane,[r-[x-1,y-1] for r in rings],-1,1,-1)
    for ring in rings[1:]:cv2.drawContours(plane,[ring-[x-1,y-1]],-1,0,-1)
    return 2*float(cv2.distanceTransform(plane,cv2.DIST_L2,5).max())*scale


def add_line_art(document, exact, alpha, scale, colours=None, retrace_mm=6.0, layers=None):
    """Prepared line art -> one running-stitch element per continuous route.
    layers: [(thread, mask)] to trace instead of the prepared colours (mixed mode)."""
    from .line_art import digitize_lines
    given=layers is not None
    layers=list(layers or [])
    for colour in ([] if given else unique_rows(exact[alpha])):
        key='#%02x%02x%02x'%tuple(colour)
        choice=(colours or {}).get(key,{'include':True,'thread':key})
        if not choice.get('include',True):continue
        layers.append((choice.get('thread',key),np.all(exact==colour,axis=2)&alpha))
    # Darker threads first, so the light lines finish on top.
    layers.sort(key=lambda item:sum(int(item[0][i:i+2],16) for i in (1,3,5)))
    # Small pictures: trace smooth-upscaled strokes for cleaner centre lines.
    factor=2 if max(alpha.shape)<1200 else 1
    if factor>1:
        size=(alpha.shape[1]*factor,alpha.shape[0]*factor)
        layers=[(thread,cv2.resize(mask.astype(np.float32),size,interpolation=cv2.INTER_CUBIC)>.5) for thread,mask in layers]
    drawn=np.zeros(alpha.shape,np.uint8);objects=0
    # Longer retrace travels back over sewn lines instead of cutting the thread.
    for thread,paths in digitize_lines(layers,scale/factor,retrace_mm=retrace_mm):
        for path in paths:
            points=[(x/scale,y/scale) for x,y in path]
            ET.SubElement(document,'path',id=f'{"detail" if given else "line"}{objects}',d='M '+' L '.join(f'{x:.3f},{y:.3f}' for x,y in points),
                style=f'fill:none;stroke:{thread};stroke-width:1',
                attrib={'{http://inkstitch.org/namespace}stroke_method':'running_stitch',
                        '{http://inkstitch.org/namespace}running_stitch_length_mm':'1.6',
                        '{http://inkstitch.org/namespace}running_stitch_tolerance_mm':'0.12'})
            cv2.polylines(drawn,[np.rint(points).astype(np.int32)],False,1,thickness=3)
            objects+=1
    if not objects:raise ValueError('No drawn lines were found. Line art needs light strokes on a dark background.')
    return objects,drawn.astype(bool)


@serialize_output
def digitize(source, directory, height_mm=100, colours=None):
    settings={}
    piece_layout=None
    prep_metadata=None
    metadata_path=Path(source).with_suffix('.prep.json')
    if metadata_path.is_file():
        metadata=json.loads(metadata_path.read_text());settings=metadata.get('options',{})
        prep_metadata=metadata
        from .piece_layout import geometry_changed
        if geometry_changed(settings):piece_layout=metadata.get('report',{}).get('piece_layout')
        from .cleanup_review import require_review
        require_review(metadata.get('report',{}))
        if settings.get('artwork_type')=='portrait' or metadata.get('report',{}).get('artwork_type')=='portrait':
            if settings.get('border_style','off')!='off':raise ValueError('Borders currently require Logo mode.')
            if settings.get('region_styles'):raise ValueError('Area stitch styles require colour artwork mode, not Portrait.')
            from .photo_stitch import generate
            return generate(source,directory,height_mm,settings)
        if settings.get('photo_style')=='one_colour':
            # One-colour photo lines (photo_lines.py, after Hatch's PhotoFlash).
            if settings.get('border_style','off')!='off':raise ValueError('One-colour photo lines do not take a border.')
            from .photo_lines import generate as photo_lines
            return photo_lines(source,directory,height_mm,settings,metadata)
    directory.mkdir(parents=True,exist_ok=True)
    with Image.open(source) as image:
        rgb=artwork_rgb(image)
        prepared=Path(source).with_suffix('.prep.json').is_file()
        alpha=np.asarray(image.convert('RGBA').getchannel('A'))>127
        exact=np.asarray(image.convert('RGB'))
    # Preparation already defines the palette. Do not quantize it again or
    # discard selected white stitches as if they were background.
    array=exact if prepared else _quantize(rgb,6)
    if not prepared:
        alpha=np.ones(array.shape[:2],bool)
    height,width=array.shape[:2]
    line_art=settings.get('line_art') is True
    if not piece_layout and settings.get('ink_only') is not True and not line_art:
        from .fill_coverage import missing_boundaries, require_boundaries
        selected=alpha.copy()
        for colour in unique_rows(array[alpha]):
            colour_key='#%02x%02x%02x'%tuple(colour)
            choice=(colours or {}).get(colour_key,{'include':prepared or not np.all(colour>=245)})
            if not choice['include']:
                selected[np.all(array==colour,axis=2)]=False
        # Check before writing files or accepting a cached incomplete plan.
        require_boundaries(missing_boundaries(array,selected,height_mm/height))
    scale=height_mm/height
    document=ET.Element('svg',xmlns=SVG,width=f'{width*scale}mm',height=f'{height_mm}mm',viewBox=f'0 0 {width} {height}')
    # Versioned stitch-parameter document; the generator reads these attributes.
    metadata=ET.SubElement(document,'metadata')
    ET.SubElement(metadata,'{http://inkstitch.org/namespace}inkstitch_svg_version').text='3'
    palette=unique_rows(array.reshape(-1,3))
    objects=0
    release_mask=np.zeros_like(alpha)
    ink_routed=False
    if settings.get("ink_only") is True:
        if settings.get("border_style","off")!="off":raise ValueError("Black lines only requires No border.")
        from .ink_lines import add_running_paths, line_settings
        if line_settings(settings)[1]==0:
            # Same router as line art: lines joined and retraced instead of thousands of
            # separate pieces (detailed ink drawings froze or hit the object limit).
            retrace=min(30.,max(2.,float(settings.get('line_retrace_mm',6.))))
            objects,drawn=add_line_art(document,exact,alpha,scale,None,retrace,layers=[('#000000',alpha.copy())])
            release_mask=alpha|drawn;ink_routed=True
        else:
            objects=add_running_paths(document,exact,alpha,settings)
        palette=[]
    if line_art and not piece_layout:
        if settings.get("border_style","off")!="off":raise ValueError("Line art requires No border.")
        retrace=min(30.,max(2.,float(settings.get('line_retrace_mm',6.))))
        objects,drawn=add_line_art(document,exact,alpha,scale,colours,retrace)
        # Allowed area: the strokes themselves plus the tiny joins between them.
        release_mask=alpha|drawn
        palette=[]
    from .region_stitches import assignments, regions, region_id, apply_style
    region_styles=assignments(settings)
    # 3D puff for every area that can hold foam; others stay flat.
    puff_all=settings.get('puff') is True
    from .stitch_engine import puff_min_mm
    foam_mm=min(5.,max(1.,float(settings.get('puff_foam_mm',3))))
    # Wilcom's puff guide: 0.3-0.5 mm pull compensation by foam thickness. This is the
    # outer edge; the satin sews 0.05 mm inside it (stitch_satin._puff_satin).
    puff_pull='.35' if foam_mm<2.5 else '.45'
    if puff_all and (line_art or settings.get('ink_only') is True):
        raise ValueError('3D puff needs colour artwork with filled areas, not line drawings.')
    if region_styles and not piece_layout:
        if settings.get('ink_only') is True or line_art:raise ValueError('Area styles cannot be applied to line drawings. Clear area assignments first.')
        missing=set(region_styles)-{key for key,_,_ in regions(exact,alpha)}
        if missing:raise ValueError('Artwork areas changed. Clear unmatched stitch assignments and select the new areas.')
    if piece_layout:
        if settings.get('border_style','off')!='off':
            raise ValueError('Piece transforms with a design-wide border are not supported yet. Set No border first.')
        from .piece_generation import append as append_pieces
        objects,release_mask,piece_origin,mask_origin=append_pieces(document,piece_layout,scale,settings,colours)
        alpha=release_mask
    # Sew the largest colour area (usually the background) first and small
    # details last, so detail edges lie on top instead of under the fill.
    knockout=bool(settings.get('colour_knockouts'))
    # Auto Fabric: satin pull compensation follows the chosen fabric (generation_policy).
    from .generation_policy import preset_for
    satin_pull=float(preset_for(settings).get('satin_pull_mm',SATIN_PULL_MM))
    if len(palette) and not piece_layout:
        present,counts=unique_rows(array[alpha],return_counts=True)
        area={tuple(c):int(n) for c,n in zip(present,counts)}
        palette=sorted(palette,key=lambda c:(-area.get(tuple(c),0),tuple(int(v) for v in c)))
    # Pixels of each included colour, in sewing order, so a fill can reach under the
    # colours sewn after it (fill_shaping.OVERLAP_MM).
    from .fill_shaping import grown as overlap_rings, angle as fill_angle
    sewn_masks=[]
    for colour in ([] if piece_layout else palette):
        key='#%02x%02x%02x'%tuple(colour)
        choice=(colours or {}).get(key,{'include':prepared or not np.all(colour>=245),'thread':key})
        if choice['include']:sewn_masks.append(np.all(array==colour,axis=2)&alpha)
    later=np.zeros(alpha.shape,bool)
    for m in sewn_masks:later|=m
    for colour in ([] if piece_layout else palette):
        key='#%02x%02x%02x'%tuple(colour)
        choice=(colours or {}).get(key,{'include':prepared or not np.all(colour>=245),'thread':key})
        if not choice['include']:
            continue
        mask=(np.all(array==colour,axis=2)&alpha).astype('uint8')
        later&=~mask.astype(bool)
        release_mask |= mask.astype(bool)
        contours,hierarchy=cv2.findContours(mask,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
        if hierarchy is None:continue
        for i,c in enumerate(contours):
            if hierarchy[0,i,3]!=-1 or cv2.contourArea(c)<4:continue
            rings=[c];child=hierarchy[0,i,2]
            while child!=-1:
                rings.append(contours[child]);child=hierarchy[0,child,0]
            identity=region_id(rings)
            style=region_styles.get(identity)
            thick=thickness_mm(rings,scale)
            if style is None and puff_all and puff_min_mm(foam_mm)<=thick<=PUFF_TO_MM:
                style='puff'
            # Plain fills overlap the colours sewn after them and run along their long side.
            plain=style is None and thick>SMALL_SATIN_MM and not knockout
            shaped=overlap_rings(rings,later,scale) if plain and later.any() else [rings]
            parts=[]
            for piece in shaped:
                for ring in piece:
                    pts=ring[:,0,:]
                    if len(pts)<3:continue
                    parts.append('M '+' L '.join(f'{x},{y}' for x,y in pts)+' Z')
            if not parts:continue
            node=ET.SubElement(document,'path',id=f'area{objects}',d=' '.join(parts),
                style=f'fill:{choice["thread"]};fill-rule:evenodd;stroke:none')
            if plain:
                node.set('{http://inkstitch.org/namespace}angle',f'{fill_angle(rings):.1f}')
            apply_style(document,node,rings,scale,style or 'tatami')
            if style=='puff':
                node.set('{http://inkstitch.org/namespace}puff_foam_mm',f'{foam_mm:g}')
                node.set('{http://inkstitch.org/namespace}pull_compensation_mm',puff_pull)
            if style=='puff' and knockout:
                # Removed areas stay exact: no outward pull, as for flat satin.
                node.set('{http://inkstitch.org/namespace}pull_compensation_mm','0')
            if style=='puff' and not knockout:
                # Puff satin is pulled past the edge on purpose; that band is sewn, not empty.
                band=np.zeros_like(mask);cv2.drawContours(band,rings,-1,1,-1)
                grow=max(1,int(math.ceil((float(puff_pull)+.05)/scale)))
                release_mask|=cv2.dilate(band,np.ones((2*grow+1,2*grow+1),np.uint8)).astype(bool)
            if style is None and thickness_mm(rings,scale)<=SMALL_SATIN_MM:
                # Narrow or small shapes are satin, as a digitizer would do them:
                # rows of fill turn ragged and gappy below a few millimetres.
                node.set('{http://inkstitch.org/namespace}fill_method','auto_satin')
                if not knockout:
                    node.set('{http://inkstitch.org/namespace}pull_compensation_mm',str(satin_pull))
                    band=np.zeros_like(mask);cv2.drawContours(band,rings,-1,1,-1)
                    grow=max(1,int(math.ceil(satin_pull/scale)))
                    release_mask|=cv2.dilate(band,np.ones((2*grow+1,2*grow+1),np.uint8)).astype(bool)
            if knockout:
                # Removed areas stay exact: keep stitches inside by the file rounding.
                node.set('{http://inkstitch.org/namespace}edge_inset_mm',str(GRID_ROUNDING_MM))
            objects+=1
    detail=settings.get('line_details','off')
    if detail in ('light','all') and prepared and not line_art and not piece_layout and settings.get('ink_only') is not True             and not settings.get('colour_knockouts') and objects:
        # Mixed mode: thin lines the fills lost, sewn on top as running stitches (detail_lines.py).
        from .detail_lines import line_layers, source_pixels
        original=source_pixels(Path(source),prep_metadata,alpha.shape)
        if original is not None:
            layers=[]
            for key,mask in line_layers(original,exact,alpha,detail):
                choice=(colours or {}).get(key,{'include':True,'thread':key})
                if choice.get('include',True):layers.append((choice.get('thread',key),mask))
            if layers:
                before=objects
                retrace=min(30.,max(2.,float(settings.get('line_retrace_mm',6.))))
                try:
                    count,drawn=add_line_art(document,exact,alpha,scale,None,retrace,layers=layers)
                    objects+=count;release_mask|=drawn&alpha
                except ValueError:
                    objects=before
    if not objects:raise ValueError('No filled areas selected. Choose at least one colour.')
    # Running-stitch line modes (line art, black ink, mixed lines) have many cheap separate lines.
    if objects>(3000 if line_art or settings.get('ink_only') is True or detail in ('light','all') else 500):raise ValueError('Too many separate objects: simplify the artwork before generating stitches.')
    from .borders import border_plan,add_border
    if not settings.get('colour_knockouts'):
        release_mask=grid_allowance(release_mask,scale)
    border=border_plan(alpha,height_mm,settings)
    add_border(document,border)
    if border:
        # The border is requested stitching, so its band is not empty fabric.
        from .borders import coverage
        release_mask=release_mask|coverage(border,release_mask.shape)
    # Pin the generator to the same source frame as playback and the safety mask.
    used=np.any(array!=255,axis=2)&alpha if not prepared else alpha
    yy,xx=np.where(used)
    if not len(xx):raise ValueError('No stitchable artwork selected.')
    source_origin=[float((xx.min()+xx.max())*scale/2),float((yy.min()+yy.max())*scale/2)]
    from .engine_origin import set_origin
    set_origin(document, mask_origin if piece_layout else source_origin, scale)
    from .generation_policy import apply as apply_generation_policy
    generation_policy=apply_generation_policy(document,settings)
    svg=directory/'design.svg'
    ET.ElementTree(document).write(svg,encoding='utf-8',xml_declaration=True)
    from .engine_cache import cache_key, lookup, publish
    import hashlib
    from .thread_recolour import routing_policy
    policy=routing_policy(alpha,scale,settings)
    if piece_layout:
        from .engine_cache import digest
        policy['piece_integration']=[digest(Path(__file__).with_name(n)) for n in ('piece_generation.py','piece_layout.py')]
    # Exact stitch removal areas (stitch_cuts.py) change the plan after generation.
    cuts=[] if piece_layout else [c for c in settings.get('stitch_cuts',[]) if isinstance(c,dict) and len(c.get('points',[]))>=3]
    key=hashlib.sha256((cache_key(source,svg)+json.dumps(policy,sort_keys=True)+(json.dumps(piece_layout,sort_keys=True) if piece_layout else '')
                        +(json.dumps(cuts,sort_keys=True) if cuts else '')).encode()).hexdigest()
    cached=lookup(directory,key)
    if cached is not None:return cached
    # Both machine files come from one engine plan. PES v6 retains custom RGB.
    from .thread_recolour import reuse
    recoloured=None if border or piece_layout or cuts else reuse(directory,svg,policy)
    if recoloured:
        plan_bytes,previous_pes=recoloured
    else:
        try:plan_bytes=generate_plan(svg)
        except (ValueError,TypeError,ArithmeticError) as error:
            raise ValueError('Stitches could not be generated for this design: '+str(error)[:500]) from None
    if cuts:
        from shapely.geometry import Polygon
        from .stitch_cuts import apply as cut_stitches
        to_plan=lambda p:((float(p[0])*scale-source_origin[0])*10,(float(p[1])*scale-source_origin[1])*10)
        areas=[Polygon([to_plan(p) for p in c['points']],[[to_plan(p) for p in hole] for hole in c.get('holes',[]) if len(hole)>=3]).buffer(0) for c in cuts]
        plan=json.loads(plan_bytes);plan['stitches'],removed=cut_stitches(plan['stitches'],areas)
        if not any(s[2]=='STITCH' for s in plan['stitches']):raise ValueError('Removing those stitches leaves nothing to sew. Undo the removal.')
        plan.setdefault('extras',{})['stitches_removed']=removed
        plan_bytes=json.dumps(plan).encode()
    raw=directory/'engine-plan.json'
    raw.write_bytes(plan_bytes)
    pattern=emb.EmbPattern(str(raw))
    used=np.any(array!=255,axis=2)&alpha if not prepared else alpha
    yy,xx=np.where(used)
    origin=[float((xx.min()+xx.max())*scale/2),float((yy.min()+yy.max())*scale/2)]
    display_origin=origin
    if piece_layout:
        shift=np.asarray(piece_origin)-np.asarray(piece_layout['origin_mm'])
        pattern.translate(float(shift[0]*10),float(shift[1]*10))
        origin=(np.asarray(mask_origin)-shift).tolist()
        display_origin=piece_layout['origin_mm']

    knockout_cuts=0
    if settings.get('colour_knockouts'):
        from .knockout_routing import protect, verify
        knockout_cuts=protect(pattern,alpha,scale,origin)
    if settings.get('colour_knockouts'):
        from tempfile import TemporaryDirectory
        # Failed validation must not replace a customer's last machine files.
        with TemporaryDirectory(prefix='knockout-check-',dir=directory) as temporary:
            checked=Path(temporary)
            written=write_pair(pattern,checked/'design.pes',checked/'design.dst',{'version':6},repair_spacing=True)
            verify(emb.EmbPattern(str(checked/'design.pes')),alpha,scale,origin)
            verify(emb.EmbPattern(str(checked/'design.dst')),alpha,scale,origin)
            for name in ('design.pes','design.dst'):(checked/name).replace(directory/name)
    else:
        written=write_pair(pattern,directory/'design.pes',directory/'design.dst',{'version':6},repair_spacing=True)
    pattern=emb.EmbPattern(str(directory/'design.pes'))
    from .repair_pipeline import propose
    before_repair=[s[:] for s in pattern.stitches]
    from .lock_repair import repair as repair_locks
    lock_candidate=pattern.copy()
    lock_report=repair_locks(lock_candidate,alpha if settings.get('ink_only') and not ink_routed else release_mask,scale,origin)
    from .gap_repair import repair as repair_gaps
    gap_report=repair_gaps(lock_candidate,alpha if settings.get('ink_only') and not ink_routed else release_mask,scale,origin)
    candidate,repair_report=propose(lock_candidate,alpha if settings.get('ink_only') and not ink_routed else release_mask,scale,origin)
    repair_report['locks']=lock_report
    repair_report['gaps']=gap_report
    if repair_report['automatic'] and (repair_report['changes'] or lock_report['end_locks_rebuilt'] or lock_report['start_locks_rebuilt'] or gap_report['gaps_cut']):
        write_pair(candidate,directory/'design.pes',directory/'design.dst',{'version':6,'encode':False})
        pattern=emb.EmbPattern(str(directory/'design.pes'))
    (directory/'repair-proposal.json').write_text(json.dumps(dict(report=repair_report,before=before_repair,after=candidate.stitches)))
    colors=[t.hex_color() for t in pattern.threadlist]
    if recoloured:
        old_pes=emb.EmbPattern(str(previous_pes))
        old_dst=emb.EmbPattern(str(previous_pes.with_suffix('.dst')))
        new_dst=emb.EmbPattern(str(directory/'design.dst'))
        if pattern.stitches!=old_pes.stitches or new_dst.stitches!=old_dst.stitches:
            raise ValueError('Colour-only export changed stitch commands; refusing this result.')
    planned=[t['color'] for t in json.loads(plan_bytes)['threadlist']]
    # PES lists a colour once when a stop repeats it (the stop for puff foam keeps the
    # thread); the stop itself is still in the file.
    if colors != planned and colors != [c for i,c in enumerate(planned) if not i or c!=planned[i-1]]:
        raise ValueError('PES readback changed the prepared thread palette.')
    colors=planned
    # A stop that keeps the thread (PES writes one before puff foam) counts as a thread change here.
    types={emb.STITCH:'stitch',emb.JUMP:'jump',emb.TRIM:'trim',emb.COLOR_CHANGE:'color_change',emb.STOP:'color_change',emb.END:'end'}
    steps=[];index=0
    for x,y,flags in pattern.stitches:
        kind=types.get(flags & emb.COMMAND_MASK,'unknown')
        if kind=='color_change':index+=1
        if index>=len(colors):raise ValueError('Written thread palette does not match commands.')
        steps.append({'x':x/10,'y':y/10,'t':kind,'color':colors[index]})
    payload={'steps':steps,'colors':colors,'stitch_count':sum(s['t']=='stitch' for s in steps),
        'trim_count':sum(s['t']=='trim' for s in steps),'engine':ENGINE_NAME,'objects':objects,
        'origin_mm':display_origin,'height_mm':height_mm,'palette_format':'PES v6 custom RGB','generation_mode':'verified thread recolour' if recoloured else 'full generation'}
    if settings.get('colour_knockouts'):payload['colour_knockout_routing']={'extra_cuts':knockout_cuts,'machine_files_verified':['PES','DST'],'boundary_allowance_pixels':1}
    payload['spacing_repair']=written.extras.get('spacing_repair',{})
    payload['generation_policy']=generation_policy
    payload['repair_report']=repair_report
    if border:payload['border']={k:v for k,v in border.items() if k!='paths'}
    puff_threads=json.loads(plan_bytes).get('extras',{}).get('puff_threads',[])
    if puff_threads:
        payload['puff']={'threads':puff_threads,'foam_mm':foam_mm}
    (directory/'playback.json').write_text(json.dumps(payload))
    from .release_gate import record_context
    record_context(directory,alpha if settings.get('ink_only') and not ink_routed else release_mask,scale,origin)
    publish(directory,key,policy)
    return payload
