"""Outer-silhouette border geometry shared by the preview and stitch exporter."""
from .knowledge_messages import message as knowledge_message
import math
import cv2
import numpy as np
from shapely.geometry import Polygon
import xml.etree.ElementTree as ET
from .stitch_paths import MOTIFS

NS='http://inkstitch.org/namespace'
# Running-line borders with a decorative stitch (stitch_engine.OUTLINE_STYLES); width is the band they cover.
OUTLINES=('backstitch','stemstitch','blanket','zigzag','motif')
INNER_GAP_MM=1.2   # space between a border and the decorative line inside it

def border_plan(mask,height_mm,options):
    kind=options.get('border_style','off')
    if kind=='off':return None
    if kind not in ('running','satin')+OUTLINES:raise ValueError('Choose a listed border stitch; 3D puff is not supported.')
    if options.get('artwork_type')=='portrait':raise ValueError('Borders currently require Logo mode, not the experimental portrait engine.')
    width=float(options.get('border_width',2));spacing=float(options.get('border_spacing',.4))
    if not math.isfinite(width) or not .8<=width<=6:raise ValueError(knowledge_message('borders.02'))
    if kind=='satin' and width<1.6:raise ValueError(knowledge_message('borders.03'))
    if not math.isfinite(spacing) or not .3<=spacing<=.8:raise ValueError(knowledge_message('borders.04'))
    colour=options.get('border_colour','#202020')
    if not isinstance(colour,str) or len(colour)!=7 or colour[0]!='#' or any(c not in '0123456789abcdefABCDEF' for c in colour[1:]):raise ValueError('Invalid border colour.')
    placement=options.get('border_placement','center')
    if placement not in ('inside','center','outside'):raise ValueError('Invalid border placement.')
    inner_kind=options.get('border_inner','off')
    if inner_kind not in ('off','triple'):raise ValueError('Choose a listed line inside the border.')
    motif=options.get('border_motif','diamond')
    if motif not in MOTIFS:raise ValueError('Choose a listed motif for the motif run.')
    scale=height_mm/mask.shape[0]
    offset={'inside':-width/2,'center':0,'outside':width/2}[placement]/scale if kind=='satin' else 0
    contours,_=cv2.findContours(mask.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    paths=[];inner=[];warnings=[]
    # Line inside: a triple-stitch line this far inside the border's inner edge, as on badges and frames.
    gap=(band_mm(kind,width)/2 if kind!='running' else .3)+INNER_GAP_MM
    for contour in contours:
        if cv2.contourArea(contour)<4:continue
        points=cv2.approxPolyDP(contour,.1/scale,True)[:,0,:]
        if len(points)<3:continue
        polygon=Polygon(points)
        if not polygon.is_valid:raise ValueError('Border outline crosses itself. Correct the selection before generating a border.')
        if kind=='satin':polygon=polygon.simplify(width*.15/scale,preserve_topology=True)
        line=polygon.buffer(offset,join_style='mitre') if offset else polygon
        if line.is_empty or line.geom_type!='Polygon':raise ValueError('Border does not fit this outline. Reduce its width or choose centered placement.')
        coords=[[float(x),float(y)] for x,y in line.exterior.coords]
        if kind=='satin':satin_rails(coords,width/(2*scale))
        paths.append(coords)
        if inner_kind=='triple':
            ring=line.buffer(-gap/scale,join_style='round')
            if not ring.is_empty and ring.geom_type=='Polygon' and ring.area*scale*scale>=20:
                inner.append([[float(x),float(y)] for x,y in ring.exterior.coords])
            else:warnings.append('The line inside the border does not fit a part of this outline; that part has none.')
        extent=line.buffer(band_mm(kind,width)/(2*scale)) if kind!='running' else line
        x,y,r,b=extent.bounds
        if x<0 or y<0 or r>=mask.shape[1] or b>=mask.shape[0]:warnings.append('Border extends beyond the artwork canvas. Check hoop clearance and use Fit stitches.')
    if not paths:raise ValueError('No outer boundary available for a border.')
    if len(paths)>100:raise ValueError('Too many disconnected border outlines. Refine the subject selection.')
    warnings.append('Tight corners, tiny islands and narrow gaps require a physical sew-out. Internal holes are not bordered.')
    return dict(style=kind,motif=motif,width_mm=width,spacing_mm=spacing,colour=colour,placement=placement,paths=paths,inner=inner,warnings=list(dict.fromkeys(warnings)),scale=scale)

def satin_rails(points,radius):
    """Matched offset rails; reject collapsed or sharply spiked outlines."""
    p=np.asarray(points[:-1],dtype=float)
    edges=np.roll(p,-1,axis=0)-p
    lengths=np.linalg.norm(edges,axis=1)
    if np.any(lengths<1e-6):raise ValueError('Duplicate border nodes; refine the outline.')
    tangents=edges/lengths[:,None]
    normals=np.column_stack((-tangents[:,1],tangents[:,0]))
    previous=np.roll(normals,1,axis=0)
    denom=1+np.sum(previous*normals,axis=1)
    if np.any(denom<1e-3):raise ValueError('Border corner is too sharp for satin. Use running stitch or smooth the selection.')
    shifts=(previous+normals)/denom[:,None]*radius
    # Cap corners: a mitre longer than twice the half-width (corners sharper than about
    # 60°) is cut back to that length, so the point is flattened instead of spiking out.
    reach=np.linalg.norm(shifts,axis=1)
    shifts=np.where((reach>2*radius)[:,None],shifts/np.maximum(reach,1e-9)[:,None]*2*radius,shifts)
    if np.any(np.linalg.norm(shifts,axis=1)>radius*3):
        raise ValueError('Border corner is too sharp for satin. Use running stitch or smooth the selection.')
    a,b=p+shifts,p-shifts
    pa,pb=Polygon(a),Polygon(b)
    if not pa.is_valid or not pb.is_valid or not (pa.covers(pb) or pb.covers(pa)):
        raise ValueError('Satin rails overlap at this width. Reduce width or use running stitch.')
    inner=min((pa,pb),key=lambda x:x.area)
    center=Polygon(p)
    if center.buffer(-radius).is_empty or not center.covers(inner):
        raise ValueError('Satin does not fit the narrow parts of this outline.')
    a=np.vstack((a,a[0]));b=np.vstack((b,b[0]))
    mid=len(p)//2
    return [(a[:mid+1],b[:mid+1]),(a[mid:],b[mid:])]

def band_mm(kind,width):
    """Width of the stitched band centred on the border line (blanket spikes and motifs reach one side)."""
    return {'backstitch':.6,'blanket':2*width,'motif':2*width}.get(kind,width)


def coverage(plan,shape):
    """Source-pixel band the requested border sews over; part of the release mask."""
    band=np.zeros(shape,np.uint8)
    for points in plan['paths']:
        if plan['style']=='satin':
            # Exact rail outline, including mitred corners, plus one pixel.
            for a,b in satin_rails(points,plan['width_mm']/(2*plan['scale'])):
                ring=np.rint(np.vstack((a,b[::-1]))).astype(np.int32)
                cv2.fillPoly(band,[ring],1);cv2.polylines(band,[ring],True,1,thickness=3)
        else:
            wide=band_mm(plan['style'],plan['width_mm']) if plan['style'] in OUTLINES else .6
            cv2.polylines(band,[np.rint(np.asarray(points)).astype(np.int32)],True,1,thickness=max(3,int(math.ceil(wide/plan['scale']))+2))
    for points in plan.get('inner',[]):
        cv2.polylines(band,[np.rint(np.asarray(points)).astype(np.int32)],True,1,thickness=3)
    return band.astype(bool)

def add_border(document,plan):
    if not plan:return 0
    metadata=ET.SubElement(document,'metadata')
    ET.SubElement(metadata,f'{{{NS}}}inkstitch_svg_version').text='3'
    columns=[]
    for points in plan['paths']:
        if plan['style']=='satin':
            for rails in satin_rails(points,plan['width_mm']/(2*plan['scale'])):
                columns.append(' '.join('M '+' L '.join(f'{x:.6f},{y:.6f}' for x,y in rail) for rail in rails))
        else:columns.append('M '+' L '.join(f'{x:.6f},{y:.6f}' for x,y in points)+' Z')
    for i,d in enumerate(columns):
        attrs=dict(id=f'border{i}',d=d,style=f"fill:none;stroke:{plan['colour']};stroke-width:{(plan['width_mm'] if plan['style']=='satin' else .2)/plan['scale']};stroke-linejoin:round")
        if plan['style']=='satin':
            attrs.update({f'{{{NS}}}satin_column':'true',f'{{{NS}}}center_walk_underlay':'true',f'{{{NS}}}zigzag_spacing_mm':str(plan['spacing_mm'])})
        else:attrs.update({f'{{{NS}}}stroke_method':'running_stitch',f'{{{NS}}}running_stitch_length_mm':'2'})
        if plan['style'] in OUTLINES:
            attrs.update({f'{{{NS}}}outline_style':plan['style'],f'{{{NS}}}outline_width_mm':str(plan['width_mm']),
                          f'{{{NS}}}running_stitch_length_mm':{'backstitch':'2.5','motif':'2'}.get(plan['style'],'3')})
            if plan['style']=='motif':attrs[f'{{{NS}}}outline_motif']=plan.get('motif','diamond')
        attrs[f'{{{NS}}}trim_after']='true'
        ET.SubElement(document,'path',attrs)
    for i,points in enumerate(plan.get('inner',[])):
        # Triple stitch (each stitch sewn three times): a bold, even line that reads well beside satin.
        d='M '+' L '.join(f'{x:.6f},{y:.6f}' for x,y in points)+' Z'
        ET.SubElement(document,'path',{'id':f'border-inner{i}','d':d,'style':f"fill:none;stroke:{plan['colour']};stroke-width:{.2/plan['scale']}",
                      f'{{{NS}}}stroke_method':'running_stitch',f'{{{NS}}}running_stitch_length_mm':'2.2',
                      f'{{{NS}}}bean_stitch_repeats':'1',f'{{{NS}}}trim_after':'true'})
    return len(columns)+len(plan.get('inner',[]))
