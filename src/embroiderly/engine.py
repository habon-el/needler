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



def edge_pull(bands,pad,shape):
    """(pixels, mask) for satin pull reaching past the picture's edge: the checked canvas
    (shape, already padded by pad) grows by that many pixels and the mask is the pulled
    band in the grown frame. (0, None) when no pulled area touches the edge."""
    grow=max([g for band,g in bands if band[0].any() or band[-1].any() or band[:,0].any() or band[:,-1].any()],default=0)
    if not grow:return 0,None
    out=np.zeros((shape[0]+2*grow,shape[1]+2*grow),bool)
    for band,g in bands:
        out|=cv2.dilate(np.pad(band,pad+grow),np.ones((2*g+1,2*g+1),np.uint8)).astype(bool)
    return grow,out

def thickness_mm(rings,scale):
    """Widest point of an area (largest inscribed circle diameter) in mm."""
    x,y,w,h=cv2.boundingRect(np.vstack(rings))
    plane=np.zeros((h+2,w+2),np.uint8)
    cv2.drawContours(plane,[r-[x-1,y-1] for r in rings],-1,1,-1)
    for ring in rings[1:]:cv2.drawContours(plane,[ring-[x-1,y-1]],-1,0,-1)
    return 2*float(cv2.distanceTransform(plane,cv2.DIST_L2,5).max())*scale


HAIRLINE_MM=.45   # areas thinner than about one thread are sewn as a run, not satin
STROKE_SATIN_MM=6.5  # long stroke-like areas up to this wide are satin too (a stem, a swirl, a letter stroke)
LIMB_MIN_MM2=1.5     # thin parts of a larger area (claws, tips, stems) at least this big become satin
LIMB_OVERLAP_MM=.4   # a limb's satin and the body's fill overlap this much, so no gap opens between them


def area_mm2(rings,scale):
    return (cv2.contourArea(rings[0])-sum(cv2.contourArea(r) for r in rings[1:]))*scale*scale


def stroke_like(rings,scale,thick):
    """A long band (its length at least four times its width): satin follows it better than rows of fill."""
    return area_mm2(rings,scale)/max(thick,.1)>=4*thick


def _plane(rings):
    x,y,w,h=cv2.boundingRect(np.vstack(rings))
    plane=np.zeros((h+4,w+4),np.uint8)
    cv2.drawContours(plane,[rings[0]-[x-2,y-2]],-1,1,-1)
    for ring in rings[1:]:cv2.drawContours(plane,[ring-[x-2,y-2]],-1,0,-1)
    return plane,np.array([x-2,y-2])


def _rings_of(mask,offset):
    contours,hierarchy=cv2.findContours(mask.astype(np.uint8),cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:return []
    out=[]
    for i,c in enumerate(contours):
        if hierarchy[0,i,3]!=-1 or cv2.contourArea(c)<4:continue
        rings=[c+offset];child=hierarchy[0,i,2]
        while child!=-1:
            rings.append(contours[child]+offset);child=hierarchy[0,child,0]
        out.append(rings)
    return out


def thin_limbs(rings,scale):
    """Split thin parts (claws, stems, feather tips, swirl ends) off a thick area: the body keeps its
    fill and each limb becomes satin that follows and tapers with it, as a digitizer would split them.
    The two overlap by LIMB_OVERLAP_MM. Returns (body rings, [limb rings]); no limbs leaves the area whole."""
    plane,offset=_plane(rings)
    r=max(1,int(round(SMALL_SATIN_MM/2/scale)))
    body=cv2.morphologyEx(plane,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(2*r+1,2*r+1)))
    count,labels,stats,_=cv2.connectedComponentsWithStats((plane&(1-body)).astype(np.uint8),connectivity=8)
    limbs=np.zeros_like(plane)
    for i in range(1,count):
        part=(labels==i).astype(np.uint8)
        size=stats[i,cv2.CC_STAT_AREA]*scale*scale
        if size<LIMB_MIN_MM2:continue
        width=2*float(cv2.distanceTransform(np.pad(part,1),cv2.DIST_L2,5).max())*scale
        if size/max(width,.1)<2*width:continue   # a bump on the edge, not a limb: it stays in the fill
        limbs|=part
    if not limbs.any():return rings,[]
    grow=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(2*max(1,int(math.ceil(LIMB_OVERLAP_MM/scale)))+1,)*2)
    kept=_rings_of(cv2.dilate(plane&(1-limbs),grow)&plane,offset)
    if len(kept)!=1:return rings,[]   # the body would fall apart into pieces: keep it whole
    count,labels=cv2.connectedComponents(limbs,connectivity=8)
    parts=[]
    for i in range(1,count):
        parts+=_rings_of(cv2.dilate((labels==i).astype(np.uint8),grow)&plane,offset)
    return kept[0],parts


LAYER_AREAS_MAX=400   # more separate parts than this: keep the colour order (layering them is slow)


def layer_passes(passes):
    """Back-to-front order: each part's depth is how many parts of other threads enclose it
    (it sits in their hole). Parts are sewn by depth, then in the usual colour order; parts of
    one thread at one depth stay together. Returns [(colour, choice, mask)], a thread may repeat."""
    parts=[]
    for rank,(colour,choice,mask) in enumerate(passes):
        count,labels=cv2.connectedComponents(mask,connectivity=8)
        for i in range(1,count):
            part=(labels==i).astype(np.uint8)
            outer,_=cv2.findContours(part,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            ys,xs=np.nonzero(part)
            parts.append(dict(rank=rank,mask=part,outer=max(outer,key=cv2.contourArea),point=(float(xs[0]),float(ys[0]))))
            if len(parts)>LAYER_AREAS_MAX:return passes
    for a in parts:
        a['depth']=sum(1 for b in parts if b['rank']!=a['rank'] and cv2.pointPolygonTest(b['outer'],a['point'],False)>0)
    out=[]
    for a in sorted(parts,key=lambda a:(a['depth'],a['rank'])):
        colour,choice,_=passes[a['rank']]
        if out and out[-1][3]==(a['depth'],a['rank']):
            out[-1][2]|=a['mask']
        else:
            out.append([colour,choice,a['mask'].copy(),(a['depth'],a['rank'])])
    return [(colour,choice,mask) for colour,choice,mask,_ in out]


def hand_passes(passes,sequence):
    """Sewing order by hand (sew_sequence.py): one pass per part, in the chosen order. Specks
    too small to be a part stay right after the last part of their thread."""
    from .region_stitches import region_id
    from .sew_sequence import arrange
    parts=[];here=np.zeros(2)
    for colour,choice,mask in passes:
        contours,hierarchy=cv2.findContours(mask,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
        if hierarchy is None:continue
        rest=mask.copy()
        outer=[i for i,c in enumerate(contours) if hierarchy[0,i,3]==-1 and cv2.contourArea(c)>=4]
        for i in closest_join(outer,contours,here):
            here=contours[i][:,0,:].mean(axis=0)
            rings=[contours[i]];child=hierarchy[0,i,2]
            while child!=-1:
                rings.append(contours[child]);child=hierarchy[0,child,0]
            part=np.zeros_like(mask);cv2.drawContours(part,rings[:1],-1,1,-1)
            if len(rings)>1:cv2.drawContours(part,rings[1:],-1,0,-1);cv2.drawContours(part,rings[1:],-1,1,1)
            part&=mask;rest&=~part
            parts.append((region_id(rings),(colour,choice,part)))
        if rest.any():parts.append((None,(colour,choice,rest)))
    return [parts[i][1] for i in arrange([key for key,_ in parts],sequence)]


def add_satin_area(document,rings,thread,index,spacing,pull,knockout):
    """An area sewn as satin columns that follow its centre line (stitch_engine._satin_area)."""
    d=' '.join('M '+' L '.join(f'{x},{y}' for x,y in ring[:,0,:])+' Z' for ring in rings)
    node=ET.SubElement(document,'path',id=f'area{index}',d=d,style=f'fill:{thread};fill-rule:evenodd;stroke:none')
    node.set('{http://inkstitch.org/namespace}fill_method','auto_satin')
    if spacing:node.set('{http://inkstitch.org/namespace}zigzag_spacing_mm',f'{float(spacing):g}')
    if not knockout:node.set('{http://inkstitch.org/namespace}pull_compensation_mm',str(pull))
    return node


def contours_too_thin(contours,hierarchy,scale):
    """Outer contours with no fillable area (under 4 px²) that are long enough to sew
    as a line (fill_coverage.HAIR_MIN_MM); shorter specks stay reported as missing."""
    from .fill_coverage import HAIR_MIN_MM
    for i,c in enumerate(contours):
        if hierarchy[0,i,3]==-1 and cv2.contourArea(c)<4:
            x,y,w,h=cv2.boundingRect(c)
            if max(w,h)*scale>=HAIR_MIN_MM:yield c


def add_hairline(document,points,thread,index,closed):
    pts=[(float(x),float(y)) for x,y in points]+([tuple(map(float,points[0]))] if closed else [])
    ET.SubElement(document,'path',id=f'hair{index}',d='M '+' L '.join(f'{x},{y}' for x,y in pts),
        style=f'fill:none;stroke:{thread};stroke-width:1',
        attrib={'{http://inkstitch.org/namespace}stroke_method':'running_stitch',
                '{http://inkstitch.org/namespace}running_stitch_length_mm':'1.5',
                '{http://inkstitch.org/namespace}running_stitch_tolerance_mm':'0',
                '{http://inkstitch.org/namespace}trim_after':'true'})


def darker(thread,factor=.55):
    """A darker shade of a thread colour for outlines and shading (very dark threads get black)."""
    rgb=[int(thread[i:i+2],16) for i in (1,3,5)]
    if max(rgb)<60:return '#000000'
    return '#%02x%02x%02x'%tuple(int(v*factor) for v in rgb)


def colour_outlines(document,exact,alpha,masks,scale,thread,retrace_mm):
    """Add outlines: one running line along every colour boundary and the
    outer edge, routed as continuous branched runs (line_art) and sewn last.
    thread: one colour for every outline, or a list (one per mask) for per-part shades;
    a boundary between two parts takes the shade of the part sewn later (it lies on top)."""
    label=np.full(alpha.shape,-1,np.int32)
    for k,m in enumerate(masks):label[m]=k
    # Eight neighbours: on a slanted or round edge a four-neighbour edge is a chain of pixels
    # touching only at corners, which the line tracer breaks into pieces (each one a cut).
    around=[np.roll(np.roll(label,dy,0),dx,1) for dy in (-1,0,1) for dx in (-1,0,1) if dy or dx]
    edge=np.zeros(alpha.shape,bool)
    for shifted in around:
        edge|=label!=shifted
    edge[[0,-1],:]|=label[[0,-1],:]>=0;edge[:,[0,-1]]|=label[:,[0,-1]]>=0
    edge&=label>=0
    if not edge.any():return 0,np.zeros(alpha.shape,bool)
    if isinstance(thread,str):
        return add_line_art(document,exact,alpha,scale,None,retrace_mm,layers=[(thread,edge)])
    # Each edge pixel belongs to the part on top: one with a lower (earlier) or empty neighbour.
    lowest=np.minimum.reduce(around)
    lowest[[0,-1],:]=-1;lowest[:,[0,-1]]=-1
    owned=edge&(lowest<label)
    shades={}
    for k,t in enumerate(thread):
        shades[t]=shades.get(t,np.zeros(alpha.shape,bool))|(owned&(label==k))
    return add_line_art(document,exact,alpha,scale,None,retrace_mm,layers=list(shades.items()))


def cutting_svg(pieces,scale):
    """Appliqué pieces as an SVG in millimetres: one closed outline per piece (holes kept),
    laid out where they sit in the design so each piece is easy to match."""
    points=np.vstack([r[:,0,:] for rings in pieces for r in rings]).astype(float)*scale
    left,top=points.min(axis=0)-2;right,bottom=points.max(axis=0)+2
    paths=[]
    for rings in pieces:
        d=' '.join('M '+' L '.join(f'{x*scale-left:.2f},{y*scale-top:.2f}' for x,y in r[:,0,:])+' Z' for r in rings)
        paths.append(f'<path d="{d}" fill="none" stroke="#000" stroke-width="0.2" fill-rule="evenodd"/>')
    w,h=right-left,bottom-top
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.2f}mm" height="{h:.2f}mm" viewBox="0 0 {w:.2f} {h:.2f}">'
            '<title>Appliqué cutting shapes, actual size</title>'+''.join(paths)+'</svg>')


def closest_join(indices,contours,start):
    """Closest join: sew a colour's areas nearest-first from where the last area
    ended (its centre), instead of in contour-finder order, so travel stays short."""
    left=list(indices);order=[];here=np.asarray(start,float)
    # A few points around each area are enough to compare distances (photos have thousands of specks).
    probe={i:contours[i][::max(1,len(contours[i])//16),0,:] for i in left}
    while left:
        best=min(left,key=lambda i:float(np.min(np.sum((probe[i]-here)**2,axis=1))))
        left.remove(best);order.append(best);here=contours[best][:,0,:].mean(axis=0)
    return order


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
            if sum(math.dist(p,q) for p,q in zip(path,path[1:]))<1.5:
                # Tie-offs on a mark shorter than themselves reach past its ends: that thread is sewn.
                reach=int(math.ceil(.7/scale))
                for end in (points[0],points[-1]):cv2.circle(drawn,tuple(int(round(v)) for v in end),reach,1,-1)
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
        if settings.get('photo_style') in ('one_colour','multi_colour'):
            # Photo lines in one or several colours, closed or open (photo_lines.py).
            if settings.get('border_style','off')!='off':raise ValueError('Photo lines do not take a border.')
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
    from .region_stitches import hole_choices
    filled_holes=hole_choices(settings)
    from .region_stitches import angle_choices
    chosen_angles=angle_choices(settings)
    from .region_stitches import colour_choices, colour_hole_choices, for_colour, colour_style_refusal, split_style, FILL_STYLES
    colour_styles,colour_angles=colour_choices(settings)
    colour_holes=colour_hole_choices(settings)
    from .applique_layout import choices as applique_choices, finish as applique_finish
    applique_choices(settings)
    from .basting_buttonholes import choices as extra_choices
    basting,buttonholes=extra_choices(settings)
    # 3D puff for every area that can hold foam; others stay flat.
    puff_all=settings.get('puff') is True
    from .stitch_engine import puff_min_mm
    foam_mm=min(5.,max(1.,float(settings.get('puff_foam_mm',3))))
    # Published puff guidance: 0.3-0.5 mm pull compensation by foam thickness. This is the
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
    # Fabric preset: satin pull compensation and spacing follow the chosen fabric (generation_policy).
    from .generation_policy import preset_for
    fabric=preset_for(settings)
    satin_pull=float(fabric.get('satin_pull_mm',SATIN_PULL_MM))
    satin_spacing=fabric.get('satin_spacing_mm')
    if len(palette) and not piece_layout:
        present,counts=unique_rows(array[alpha],return_counts=True)
        area={tuple(c):int(n) for c,n in zip(present,counts)}
        palette=sorted(palette,key=lambda c:(-area.get(tuple(c),0),tuple(int(v) for v in c)))
    # Pixels of each included colour, in sewing order, so a fill can reach under the
    # colours sewn after it (fill_shaping.OVERLAP_MM).
    from .fill_shaping import grown as overlap_rings, angle as fill_angle
    sewn_masks=[];sewn_threads=[]
    for colour in ([] if piece_layout else palette):
        key='#%02x%02x%02x'%tuple(colour)
        choice=(colours or {}).get(key,{'include':prepared or not np.all(colour>=245),'thread':key})
        if choice['include']:sewn_masks.append(np.all(array==colour,axis=2)&alpha);sewn_threads.append(choice['thread'])
    later=np.zeros(alpha.shape,bool)
    for m in sewn_masks:later|=m
    here=np.zeros(2)  # where the last area ended (pixels); the design starts top left
    cut_pieces=[]     # appliqué outlines (pixel rings) for the fabric cutting file
    applique_parts=[] # (rings, node, colour pass) finished together after all parts (applique_layout.py)
    pull_bands=[]     # (area, pixels) of satin pulled past its edge; the canvas grows where it reaches the edge
    passes=[]
    for colour in ([] if piece_layout else palette):
        key='#%02x%02x%02x'%tuple(colour)
        choice=(colours or {}).get(key,{'include':prepared or not np.all(colour>=245),'thread':key})
        if choice['include']:passes.append((colour,choice,(np.all(array==colour,axis=2)&alpha).astype('uint8')))
    if settings.get('sew_order','colours') not in ('colours','layers'):
        raise ValueError('Choose a listed sewing order.')
    if settings.get('sew_order')=='layers':
        # Best look: back to front. A part lying inside another part (a cheek in a head) is sewn
        # after it, even when its thread was used before; the colour order decides otherwise.
        passes=layer_passes(passes)
    from .sew_sequence import choices as sew_choices
    sequence=sew_choices(settings)
    if sequence and not piece_layout:
        passes=hand_passes(passes,sequence)
    sewn_parts=[];area_report=[]
    # Outlines per part (part_outlines.py): collected with their parts, sewn after all fills.
    from .part_outlines import choices as outline_choices, add as add_part_outline, in_order as outlines_in_order
    part_outlines=outline_choices(settings);pending_outlines=[]
    for step,(colour,choice,mask) in enumerate(passes):
        later&=~mask.astype(bool)
        release_mask |= mask.astype(bool)
        contours,hierarchy=cv2.findContours(mask,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
        if hierarchy is None:continue
        outer=[i for i,c in enumerate(contours) if hierarchy[0,i,3]==-1 and cv2.contourArea(c)>=4]
        for c in contours_too_thin(contours,hierarchy,scale):
            # Lines a pixel wide have no area to fill: a run along them and back.
            add_hairline(document,c[:,0,:],choice['thread'],objects,closed=False);objects+=1
        for i in closest_join(outer,contours,here):
            c=contours[i]
            here=c[:,0,:].mean(axis=0)
            rings=[c];child=hierarchy[0,i,2]
            while child!=-1:
                rings.append(contours[child]);child=hierarchy[0,child,0]
            identity=region_id(rings);sewn_parts.append(identity)
            if identity in part_outlines:pending_outlines.append(([r[:,0,:] for r in rings],part_outlines[identity]))
            style=region_styles.get(identity)
            if filled_holes.get(identity)=='fill' and len(rings)>1:
                # Remove / fill holes: stitches run straight across them, so no gap opens at
                # the hole's edge; an empty hole is filled. That stitching is intended.
                band=np.zeros_like(mask);cv2.drawContours(band,[c],-1,1,-1)
                release_mask|=band.astype(bool);rings=[c]
            elif len(rings)>1 and for_colour(colour_holes,choice['thread']) is not None:
                # Holes chosen per thread colour: all of them, or those up to a size, are sewn over.
                limit=for_colour(colour_holes,choice['thread'])
                kept=[h for h in rings[1:] if limit!='all' and cv2.contourArea(h)*scale*scale>limit]
                band=np.zeros_like(mask);cv2.drawContours(band,[c],-1,1,-1)
                if kept:cv2.drawContours(band,kept,-1,0,-1)
                release_mask|=band.astype(bool);rings=[c,*kept]
            thick=thickness_mm(rings,scale)
            wanted=for_colour(colour_styles,choice['thread']) if style is None else None
            refused=('Thinner than one thread: sewn as a running line.' if thick<HAIRLINE_MM else colour_style_refusal(
                wanted,rings,scale,thick,(puff_min_mm(foam_mm),PUFF_TO_MM),SMALL_SATIN_MM)) if wanted else ''
            by_colour=bool(wanted) and not refused
            if by_colour:style=wanted
            # What each part became, for the AI digitizer's feedback per colour.
            area=dict(thread=choice['thread'],mm2=round(float(cv2.contourArea(c)-sum(cv2.contourArea(h) for h in rings[1:]))*scale*scale,1),
                      width_mm=round(thick,1),style=style)
            if refused:area.update(asked=wanted,refused=refused)
            area_report.append(area)
            if style is None and puff_all and puff_min_mm(foam_mm)<=thick<=PUFF_TO_MM:
                style='puff'
            if style is None and thick<HAIRLINE_MM:
                # Thinner than one thread: no satin forms; a run around its edge sews the line.
                add_hairline(document,c[:,0,:],choice['thread'],objects,closed=True);objects+=1
                area['style']='running line'
                continue
            # Long bands become satin; thin limbs of thick areas are split off as satin (sewn after the body).
            stroke=style is None and not knockout and SMALL_SATIN_MM<thick<=STROKE_SATIN_MM and stroke_like(rings,scale,thick)
            limbs=[]
            if style is None and not knockout and not stroke and thick>SMALL_SATIN_MM and settings.get('smart_satin',True) is not False:
                rings,limbs=thin_limbs(rings,scale)
            # Plain fills overlap the colours sewn after them and run along their long side.
            # A fill chosen for the whole colour overlaps like the automatic one, so no fabric shows between colours.
            plain=(style is None or by_colour and split_style(style)[0] in FILL_STYLES) and thick>SMALL_SATIN_MM and not knockout and not stroke
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
            if identity in chosen_angles:
                # Stitch direction chosen for this area replaces the automatic one.
                node.set('{http://inkstitch.org/namespace}angle',f'{float(chosen_angles[identity]):g}')
            elif for_colour(colour_angles,choice['thread']) is not None:
                node.set('{http://inkstitch.org/namespace}angle',f'{float(for_colour(colour_angles,choice["thread"])):g}')
            if style=='puff':
                node.set('{http://inkstitch.org/namespace}puff_foam_mm',f'{foam_mm:g}')
                node.set('{http://inkstitch.org/namespace}pull_compensation_mm',puff_pull)
            if style=='puff' and knockout:
                # Removed areas stay exact: no outward pull, as for flat satin.
                node.set('{http://inkstitch.org/namespace}pull_compensation_mm','0')
            if style=='applique':applique_parts.append((rings,node,step))
            if style=='puff' and not knockout:
                # Puff satin is pulled past the edge on purpose; that band is sewn, not empty.
                band=np.zeros_like(mask);cv2.drawContours(band,rings,-1,1,-1)
                grow=max(1,int(math.ceil((float(puff_pull)+.05)/scale)))
                release_mask|=cv2.dilate(band,np.ones((2*grow+1,2*grow+1),np.uint8)).astype(bool);pull_bands.append((band,grow))
            if style is None and (stroke or thickness_mm(rings,scale)<=SMALL_SATIN_MM) or node.get('{http://inkstitch.org/namespace}fill_method')=='auto_satin' and style=='satin':
                # Narrow or small shapes are satin, as a digitizer would do them:
                # rows of fill turn ragged and gappy below a few millimetres.
                node.set('{http://inkstitch.org/namespace}fill_method','auto_satin')
                if satin_spacing:
                    node.set('{http://inkstitch.org/namespace}zigzag_spacing_mm',f'{float(satin_spacing):g}')
                if not knockout:
                    node.set('{http://inkstitch.org/namespace}pull_compensation_mm',str(satin_pull))
                    band=np.zeros_like(mask);cv2.drawContours(band,rings,-1,1,-1)
                    grow=max(1,int(math.ceil(satin_pull/scale)))
                    release_mask|=cv2.dilate(band,np.ones((2*grow+1,2*grow+1),np.uint8)).astype(bool);pull_bands.append((band,grow))
            area['style']=style or ('satin' if node.get('{http://inkstitch.org/namespace}fill_method')=='auto_satin' else
                                    'tatami with satin tips' if limbs else 'tatami')
            if knockout:
                # Removed areas stay exact: keep stitches inside by the file rounding.
                node.set('{http://inkstitch.org/namespace}edge_inset_mm',str(GRID_ROUNDING_MM))
            objects+=1
            for limb in limbs:
                # Thin limbs on top of the body's fill, same thread: satin that follows and tapers.
                add_satin_area(document,limb,choice['thread'],objects,satin_spacing,satin_pull,knockout);objects+=1
                band=np.zeros_like(mask);cv2.drawContours(band,limb,-1,1,-1)
                grow=max(1,int(math.ceil(satin_pull/scale)))
                release_mask|=cv2.dilate(band,np.ones((2*grow+1,2*grow+1),np.uint8)).astype(bool);pull_bands.append((band,grow))
    if applique_parts:
        from .stitch_engine import applique_coverage
        for rings,bare in applique_finish(document,applique_parts,[m for *_,m in passes],scale,settings):
            cut_pieces.append(rings)
            # The satin cover is centred on the fabric's cut edge: half of it, and its mitred corners, lie outside.
            release_mask|=applique_coverage([r[:,0,:] for r in rings],scale,release_mask.shape,bare=bare)
    for rings_px,spec in outlines_in_order(pending_outlines):
        objects+=add_part_outline(document,rings_px,spec,scale,release_mask,objects)
    outline_thread=settings.get('outline_colour','#202020')
    if settings.get('outlines') is True and not line_art and not piece_layout and settings.get('ink_only') is not True and objects:
        if outline_thread!='auto' and not (isinstance(outline_thread,str) and len(outline_thread)==7 and outline_thread[0]=='#'
                and all(ch in '0123456789abcdefABCDEF' for ch in outline_thread[1:])):
            raise ValueError('Choose an outline thread colour.')
        # auto: each part is outlined in a darker shade of its own thread, as digitizers define details.
        thread=[darker(t) for t in sewn_threads] if outline_thread=='auto' else outline_thread.lower()
        count,drawn=colour_outlines(document,exact,alpha,sewn_masks,scale,thread,
                                    min(30.,max(2.,float(settings.get('line_retrace_mm',6.)))))
        objects+=count;release_mask|=drawn&alpha
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
    # Cutting file: the appliqué fabric shapes at true size, for a cutter or a paper template.
    cut_file=directory/'applique-cut.svg'
    if cut_pieces:cut_file.write_text(cutting_svg(cut_pieces,scale),encoding='utf-8')
    elif cut_file.exists():cut_file.unlink()
    from .engine_cache import cache_key, lookup, publish
    import hashlib
    from .thread_recolour import routing_policy
    policy=routing_policy(alpha,scale,settings)
    if piece_layout:
        from .engine_cache import digest
        policy['piece_integration']=[digest(Path(__file__).with_name(n)) for n in ('piece_generation.py','piece_layout.py')]
    # Exact stitch removal areas (stitch_cuts.py) change the plan after generation.
    cuts=[] if piece_layout else [c for c in settings.get('stitch_cuts',[]) if isinstance(c,dict) and len(c.get('points',[]))>=3]
    # Stops, cuts and single-stitch edits (stitch_edits.py) too, after the removal areas.
    from .stitch_edits import choices as edit_choices
    stitch_edits=edit_choices(settings)
    key=hashlib.sha256((cache_key(source,svg)+json.dumps(policy,sort_keys=True)+(json.dumps(piece_layout,sort_keys=True) if piece_layout else '')
                        +(json.dumps(cuts,sort_keys=True) if cuts else '')
                        +(json.dumps(stitch_edits,sort_keys=True) if stitch_edits else '')
                        +(json.dumps([basting,buttonholes,settings.get('piece_hoop_mm') if basting=='hoop' else None]) if basting!='off' or buttonholes else '')
                        # The allowed-stitching mask is recorded only on a fresh run; a cached result
                        # must not keep an older mask when only the mask changed.
                        +hashlib.sha256(np.packbits(release_mask).tobytes()+str(release_mask.shape).encode()).hexdigest()
                        ).encode()).hexdigest()
    cached=lookup(directory,key)
    if cached is not None:return cached
    # Both machine files come from one engine plan. PES v6 retains custom RGB.
    from .thread_recolour import reuse
    recoloured=None if border or piece_layout or cuts or stitch_edits or basting!='off' or buttonholes else reuse(directory,svg,policy)
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
    if stitch_edits:
        from .stitch_edits import apply as edit_stitches
        from .knockout_routing import RemovedPixels
        # Edits are placed in playback millimetres; pieces are shifted after the plan is made.
        shift=(np.asarray(piece_origin)-np.asarray(piece_layout['origin_mm']))*10 if piece_layout else np.zeros(2)
        frame=(np.asarray(mask_origin)-shift/10).tolist() if piece_layout else source_origin
        pixels=RemovedPixels(alpha if settings.get('ink_only') and not ink_routed else release_mask,scale,frame)
        plan=json.loads(plan_bytes)
        edit_report=edit_stitches(plan,stitch_edits,lambda x,y:(x*10-shift[0],y*10-shift[1]),
                                  lambda a,b:pixels.crosses([a[0]+shift[0],a[1]+shift[1]],[b[0]+shift[0],b[1]+shift[1]]))
        plan.setdefault('extras',{})['stitch_edits']=edit_report
        plan_bytes=json.dumps(plan).encode()
    extra_pad=0
    if basting!='off' or buttonholes:
        # Basting first and buttonholes last (basting_buttonholes.py), placed in playback millimetres.
        from .basting_buttonholes import apply as add_extras, band as extras_band
        shift=(np.asarray(piece_origin)-np.asarray(piece_layout['origin_mm']))*10 if piece_layout else np.zeros(2)
        frame=(np.asarray(mask_origin)-shift/10).tolist() if piece_layout else source_origin
        plan=json.loads(plan_bytes)
        drawn=add_extras(plan,basting,buttonholes,settings.get('piece_hoop_mm'),lambda x,y:(x*10-shift[0],y*10-shift[1]))
        # They may reach past the picture: the checked canvas grows to hold them.
        extra_pad,extra_band=extras_band(drawn,scale,np.asarray(frame),release_mask.shape)
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
    gate=alpha if settings.get('ink_only') and not ink_routed else release_mask
    if extra_pad:
        gate=np.pad(gate,extra_pad)|extra_band
        origin=[float(o+extra_pad*scale) for o in origin]
    # Satin pulled past its edge is sewn, not empty (release_mask above), but a mask the size
    # of the picture cuts that band off where an area meets the picture's edge (the whole
    # picture stitched): grow the checked canvas by the pull there, and nowhere else.
    pull_pad,pull_band=edge_pull(pull_bands,extra_pad,gate.shape)
    if pull_pad:
        gate=np.pad(gate,pull_pad)|pull_band
        origin=[float(o+pull_pad*scale) for o in origin]

    knockout_cuts=0
    if settings.get('colour_knockouts'):
        from .knockout_routing import protect, verify
        # A border is requested stitching on the design's edge: its band is not a removed area.
        kept=alpha|coverage(border,alpha.shape) if border else alpha
        if extra_pad:kept=np.pad(kept,extra_pad)|extra_band
        if pull_pad:kept=np.pad(kept,pull_pad)|pull_band
        knockout_cuts=protect(pattern,kept,scale,origin)
    if settings.get('colour_knockouts'):
        from tempfile import TemporaryDirectory
        # Failed validation must not replace a customer's last machine files.
        with TemporaryDirectory(prefix='knockout-check-',dir=directory) as temporary:
            checked=Path(temporary)
            written=write_pair(pattern,checked/'design.pes',checked/'design.dst',{'version':6},repair_spacing=True)
            verify(emb.EmbPattern(str(checked/'design.pes')),kept,scale,origin)
            verify(emb.EmbPattern(str(checked/'design.dst')),kept,scale,origin)
            for name in ('design.pes','design.dst'):(checked/name).replace(directory/name)
    else:
        written=write_pair(pattern,directory/'design.pes',directory/'design.dst',{'version':6},repair_spacing=True)
    pattern=emb.EmbPattern(str(directory/'design.pes'))
    from .repair_pipeline import propose
    before_repair=[s[:] for s in pattern.stitches]
    from .lock_repair import repair as repair_locks
    lock_candidate=pattern.copy()
    lock_report=repair_locks(lock_candidate,gate,scale,origin)
    from .gap_repair import repair as repair_gaps
    gap_report=repair_gaps(lock_candidate,gate,scale,origin)
    candidate,repair_report=propose(lock_candidate,gate,scale,origin)
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
    edit_report=json.loads(plan_bytes).get('extras',{}).get('stitch_edits')
    if edit_report:payload['stitch_edits']=edit_report
    if cut_pieces:payload['applique']={'pieces':len(cut_pieces),'cut_file':'applique-cut.svg'}
    # Parts in the order they are sewn, for moving one earlier or later (sew_sequence.py).
    payload['areas']=area_report
    payload['sew_parts']=[e.get('id')[6:] for e in document.iter('path') if (e.get('id') or '').startswith('piece-')] if piece_layout else sewn_parts
    (directory/'playback.json').write_text(json.dumps(payload))
    from .release_gate import record_context
    record_context(directory,gate,scale,origin)
    publish(directory,key,policy)
    return payload
