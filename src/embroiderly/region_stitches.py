"""Region-owned stitch styles. Geometry IDs survive recolouring, not reshaping.

Native fills use the installed engine. Decorative overlays are our own bounded
geometry, not copies of another application's pattern library. Sew-out required.
"""
import hashlib
import math
import xml.etree.ElementTree as ET
import cv2
import numpy as np
from .colour_rows import unique_rows
from shapely.geometry import Polygon, LineString

NS='{http://inkstitch.org/namespace}'
CATALOG=[
    ('tatami','Tatami','Rows of fill stitches'),
    ('satin','Satin','Narrow, convex areas only'),
    ('raised_satin','3D satin','Three satin layers · experimental, no foam'),
    ('puff','3D puff','Satin over foam · parts 3–6 mm wide (2 mm foam: 2–6)'),
    ('motif','Motif','Clipped diamond repeats · open fill'),
    ('embossed','Embossed','Tatami + diamond overlay · experimental texture'),
    ('ripple','Ripple','Concentric circular waves'),
    ('contour','Contour','Follows the area boundary'),
    ('cross','Cross stitch','Clipped diagonal crosses · open fill'),
    ('stipple','Stipple single run','Meandering open fill'),
]


def assignments(options):
    value=options.get('region_styles',{})
    if not isinstance(value,dict) or len(value)>500:
        raise ValueError('Region stitch styles must contain at most 500 area assignments.')
    allowed={item[0] for item in CATALOG}
    for key,style in value.items():
        if not isinstance(key,str) or len(key)!=20 or any(c not in '0123456789abcdef' for c in key) or not isinstance(style,str) or style not in allowed:
            raise ValueError('Invalid region stitch style. Select a current area and a listed style.')
    return value


def region_id(rings):
    return hashlib.sha256(b'|'.join(np.asarray(r,dtype='<i4').tobytes() for r in rings)).hexdigest()[:20]


def regions(rgb,alpha):
    for colour in unique_rows(rgb[alpha]):
        mask=(np.all(rgb==colour,axis=2)&alpha).astype('uint8')
        contours,hierarchy=cv2.findContours(mask,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
        if hierarchy is None:continue
        for i,c in enumerate(contours):
            if hierarchy[0,i,3]!=-1 or cv2.contourArea(c)<4:continue
            rings=[c];child=hierarchy[0,i,2]
            while child!=-1:
                rings.append(contours[child]);child=hierarchy[0,child,0]
            yield region_id(rings),'#%02x%02x%02x'%tuple(colour),rings


def polygon(rings,scale):
    return Polygon(np.asarray(rings[0]).reshape(-1,2)*scale,
                   [np.asarray(r).reshape(-1,2)*scale for r in rings[1:] if len(r)>=3])


def satin_rails(rings,scale):
    p=polygon(rings,scale)
    if not p.is_valid or p.is_empty or p.interiors or p.convex_hull.area-p.area>max(.02,p.area*.015):
        raise ValueError('Satin needs a simple convex area without holes. Split this area or use Tatami.')
    rect=np.asarray(p.minimum_rotated_rectangle.exterior.coords)[:4]
    edges=np.roll(rect,-1,axis=0)-rect;lengths=np.linalg.norm(edges,axis=1)
    i=int(np.argmax(lengths));axis=edges[i]/lengths[i];normal=np.array([-axis[1],axis[0]])
    points=np.asarray(p.exterior.coords);u=points@axis;v=points@normal
    if v.max()-v.min()>6 or v.max()-v.min()<.8 or u.max()-u.min()<2:
        raise ValueError('This satin converter accepts areas 0.8–6 mm across and at least 2 mm long. Use Tatami or split the area.')
    a=[];b=[]
    for t in np.linspace(u.min()+.01,u.max()-.01,max(3,int((u.max()-u.min())/.6)+1)):
        line=LineString([axis*t+normal*(v.min()-1),axis*t+normal*(v.max()+1)])
        segment=p.intersection(line)
        if segment.geom_type!='LineString' or segment.length<.02:
            raise ValueError('Satin rails could not be paired. Use Tatami or refine the area.')
        coords=np.asarray(segment.coords);order=np.argsort(coords@normal)
        a.append(coords[order[0]]/scale);b.append(coords[order[-1]]/scale)
    return a,b


def inventory(rgb,alpha,scale,options):
    chosen=assignments(options);items=[]
    if options.get('ink_only') or options.get('line_art') or options.get('artwork_type')=='portrait':
        return dict(areas=[],stale=list(chosen),catalog=CATALOG,unavailable='Area fills require colour artwork mode. Black lines keep Running/Reinforced; portrait stitching has its own planner.')
    for key,colour,rings in regions(rgb,alpha):
        if len(items)>=500:break
        reason=''
        try:satin_rails(rings,scale)
        except ValueError as error:reason=str(error)
        x,y,w,h=cv2.boundingRect(rings[0])
        notice=''
        if chosen.get(key)=='embossed':
            try:
                if not decorative_paths(rings,scale,'embossed'):
                    notice='Embossed: this area is too small for a texture repeat; its base fill is preserved.'
            except ValueError as error:notice=str(error)
        items.append(dict(id=key,colour=colour,bounds=[x,y,w,h],rings=[r.reshape(-1,2).tolist() for r in rings],style_notice=notice,style=chosen.get(key,'tatami'),satin_reason=reason))
    return dict(areas=items,stale=sorted(set(chosen)-{r['id'] for r in items}),catalog=CATALOG,unavailable='')


def path_data(points):
    return 'M '+' L '.join(f'{x:.5f},{y:.5f}' for x,y in points)


def decorative_paths(rings,scale,kind):
    p=polygon(rings,scale)
    if not p.is_valid:
        # Pixel contours can revisit a corner. Keep every polygonal component,
        # never buffer(0), choose the largest lobe, or alter the selected mask.
        from shapely import make_valid
        from shapely.ops import unary_union
        def surfaces(g):
            if g.geom_type == 'Polygon':return [g]
            return [p for part in getattr(g,'geoms',[]) for p in surfaces(part)]
        repaired=unary_union(surfaces(make_valid(p)))
        if repaired.is_empty or not repaired.is_valid:
            raise ValueError('Decorative outline repair would change the selected area. Refine the selection or choose Tatami.')
        p=repaired
    left,top,right,bottom=p.bounds;pitch=4.0;parts=[]
    if math.ceil((right-left)/pitch)*math.ceil((bottom-top)/pitch)>400:
        raise ValueError('Decorative pattern exceeds 400 cells. Use a smaller area or Tatami.')
    for y in np.arange(top,bottom,pitch):
        for x in np.arange(left,right,pitch):
            shapes=[[(x,y),(x+pitch,y+pitch)],[(x+pitch,y),(x,y+pitch)]] if kind=='cross' else [[(x+2,y),(x+4,y+2),(x+2,y+4),(x,y+2),(x+2,y)]]
            for shape in shapes:
                clipped=p.intersection(LineString(shape))
                segments=[clipped] if clipped.geom_type=='LineString' else list(getattr(clipped,'geoms',[]))
                for segment in segments:
                    if segment.geom_type=='LineString' and segment.length>=.4:
                        parts.append(path_data(np.asarray(segment.coords)/scale))
    if not parts and kind!='embossed':raise ValueError('Area is too small for this decorative pattern. Choose Tatami or enlarge this area.')
    if len(parts)>1200:raise ValueError('Too many decorative fragments. Use Tatami or simplify the area.')
    return ' '.join(parts)


def apply_style(document,node,rings,scale,kind):
    if kind=='tatami':return
    if kind=='puff':
        # Dense satin over foam, sewn after a stop; see stitch_engine._puff_area.
        node.set(NS+'fill_method','puff_satin');node.set(NS+'zigzag_spacing_mm','.22')
        node.set(NS+'pull_compensation_mm','.45')
        return
    if kind in ('contour','ripple','stipple'):
        node.set(NS+'fill_method',{'contour':'contour_fill','ripple':'circular_fill','stipple':'meander_fill'}[kind])
        if kind in ('ripple','stipple'):node.set(NS+'fill_underlay','false')
        if kind=='ripple':
            node.set(NS+'row_spacing_mm','1.2');node.set(NS+'running_stitch_length_mm','1')
            node.set(NS+'running_stitch_tolerance_mm','.15')
        if kind=='stipple':
            node.set(NS+'meander_scale_percent','20');node.set(NS+'smoothness_mm','.3')
            node.set(NS+'clip','true');node.set(NS+'running_stitch_length_mm','1')
            node.set(NS+'running_stitch_tolerance_mm','.15')
        return
    if kind in ('satin','raised_satin'):
        a,b=satin_rails(rings,scale)
        colour=node.get('style').split(';')[0].split(':')[1]
        node.set('d',path_data(a)+' '+path_data(b))
        node.set('style',f'fill:none;stroke:{colour};stroke-width:1')
        node.set(NS+'satin_column','true');node.set(NS+'center_walk_underlay','true')
        node.set(NS+'zigzag_spacing_mm','.45')
        if kind=='raised_satin':
            for layer in (1,2):
                extra=ET.SubElement(document,'path',dict(node.attrib))
                extra.set('id',node.get('id')+f'-layer{layer}');extra.set(NS+'center_walk_underlay','false')
        return
    if kind in ('motif','cross','embossed'):
        colour=node.get('style').split(';')[0].split(':')[1]
        decoration=decorative_paths(rings,scale,kind)
        if not decoration:return  # Embossed retains its base; inventory discloses no fitting repeat.
        target=ET.SubElement(document,'path',id=node.get('id')+'-texture') if kind=='embossed' else node
        # The area outline lets the generator travel inside it between fragments.
        target.set(NS+'travel_area',node.get('d'))
        target.set('d',decoration)
        target.set('style',f'fill:none;stroke:{colour};stroke-width:1')
        target.set(NS+'stroke_method','running_stitch');target.set(NS+'running_stitch_length_mm','2')
        return
    raise ValueError('Unsupported stitch style.')
