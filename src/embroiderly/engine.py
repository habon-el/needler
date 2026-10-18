"""Native stitch generation: selected colour masks to real fill objects."""
from pathlib import Path
import json
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

@serialize_output
def digitize(source, directory, height_mm=100, colours=None):
    settings={}
    piece_layout=None
    metadata_path=Path(source).with_suffix('.prep.json')
    if metadata_path.is_file():
        metadata=json.loads(metadata_path.read_text());settings=metadata.get('options',{})
        from .piece_layout import geometry_changed
        if geometry_changed(settings):piece_layout=metadata.get('report',{}).get('piece_layout')
        from .cleanup_review import require_review
        require_review(metadata.get('report',{}))
        if settings.get('artwork_type')=='portrait' or metadata.get('report',{}).get('artwork_type')=='portrait':
            if settings.get('border_style','off')!='off':raise ValueError('Borders currently require Logo mode.')
            if settings.get('region_styles'):raise ValueError('Area stitch styles require colour artwork mode, not Portrait.')
            from .photo_stitch import generate
            return generate(source,directory,height_mm,settings)
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
    if not piece_layout and settings.get('ink_only') is not True:
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
    if settings.get("ink_only") is True:
        if settings.get("border_style","off")!="off":raise ValueError("Black lines only requires No border.")
        from .ink_lines import add_running_paths
        objects=add_running_paths(document,exact,alpha,settings)
        palette=[]
    from .region_stitches import assignments, regions, region_id, apply_style
    region_styles=assignments(settings)
    if region_styles and not piece_layout:
        if settings.get('ink_only') is True:raise ValueError('Area styles cannot be applied to Black lines only. Clear area assignments first.')
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
    if len(palette) and not piece_layout:
        present,counts=unique_rows(array[alpha],return_counts=True)
        area={tuple(c):int(n) for c,n in zip(present,counts)}
        palette=sorted(palette,key=lambda c:(-area.get(tuple(c),0),tuple(int(v) for v in c)))
    for colour in ([] if piece_layout else palette):
        key='#%02x%02x%02x'%tuple(colour)
        choice=(colours or {}).get(key,{'include':prepared or not np.all(colour>=245),'thread':key})
        if not choice['include']:
            continue
        mask=(np.all(array==colour,axis=2)&alpha).astype('uint8')
        release_mask |= mask.astype(bool)
        contours,hierarchy=cv2.findContours(mask,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
        if hierarchy is None:continue
        for i,c in enumerate(contours):
            if hierarchy[0,i,3]!=-1 or cv2.contourArea(c)<4:continue
            rings=[c];child=hierarchy[0,i,2]
            while child!=-1:
                rings.append(contours[child]);child=hierarchy[0,child,0]
            parts=[]
            for ring in rings:
                pts=ring[:,0,:]
                if len(pts)<3:continue
                parts.append('M '+' L '.join(f'{x},{y}' for x,y in pts)+' Z')
            if not parts:continue
            node=ET.SubElement(document,'path',id=f'area{objects}',d=' '.join(parts),
                style=f'fill:{choice["thread"]};fill-rule:evenodd;stroke:none')
            apply_style(document,node,rings,scale,region_styles.get(region_id(rings),'tatami'))
            objects+=1
    if not objects:raise ValueError('No filled areas selected. Choose at least one colour.')
    if objects>500:raise ValueError('Over 500 fill objects: simplify artwork before this engine trial.')
    from .borders import border_plan,add_border
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
    key=hashlib.sha256((cache_key(source,svg)+json.dumps(policy,sort_keys=True)+(json.dumps(piece_layout,sort_keys=True) if piece_layout else '')).encode()).hexdigest()
    cached=lookup(directory,key)
    if cached is not None:return cached
    # Both machine files come from one engine plan. PES v6 retains custom RGB.
    from .thread_recolour import reuse
    recoloured=None if border or piece_layout else reuse(directory,svg,policy)
    if recoloured:
        plan_bytes,previous_pes=recoloured
    else:
        try:plan_bytes=generate_plan(svg)
        except (ValueError,TypeError,ArithmeticError) as error:
            raise ValueError('Stitches could not be generated for this design: '+str(error)[:500]) from None
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
    lock_report=repair_locks(lock_candidate,alpha if settings.get('ink_only') else release_mask,scale,origin)
    from .gap_repair import repair as repair_gaps
    gap_report=repair_gaps(lock_candidate,alpha if settings.get('ink_only') else release_mask,scale,origin)
    candidate,repair_report=propose(lock_candidate,alpha if settings.get('ink_only') else release_mask,scale,origin)
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
    if colors != [t['color'] for t in json.loads(plan_bytes)['threadlist']]:
        raise ValueError('PES readback changed the prepared thread palette.')
    types={emb.STITCH:'stitch',emb.JUMP:'jump',emb.TRIM:'trim',emb.COLOR_CHANGE:'color_change',emb.END:'end'}
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
    (directory/'playback.json').write_text(json.dumps(payload))
    from .release_gate import record_context
    record_context(directory,alpha if settings.get('ink_only') else release_mask,scale,origin)
    publish(directory,key,policy)
    return payload
