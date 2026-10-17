"""Outer-silhouette border geometry shared by the preview and stitch exporter."""
from .knowledge_messages import message as knowledge_message
import math
import cv2
import numpy as np
from shapely.geometry import Polygon
import xml.etree.ElementTree as ET

NS='http://inkstitch.org/namespace'

def border_plan(mask,height_mm,options):
    kind=options.get('border_style','off')
    if kind=='off':return None
    if kind not in ('running','satin'):raise ValueError('Choose running or satin; 3D puff is not supported.')
    if options.get('artwork_type')=='portrait':raise ValueError('Borders currently require Logo mode, not the experimental portrait engine.')
    width=float(options.get('border_width',2));spacing=float(options.get('border_spacing',.4))
    if not math.isfinite(width) or not .8<=width<=6:raise ValueError(knowledge_message('borders.02'))
    if kind=='satin' and width<1.6:raise ValueError(knowledge_message('borders.03'))
    if not math.isfinite(spacing) or not .3<=spacing<=.8:raise ValueError(knowledge_message('borders.04'))
    colour=options.get('border_colour','#202020')
    if not isinstance(colour,str) or len(colour)!=7 or colour[0]!='#' or any(c not in '0123456789abcdefABCDEF' for c in colour[1:]):raise ValueError('Invalid border colour.')
    placement=options.get('border_placement','center')
    if placement not in ('inside','center','outside'):raise ValueError('Invalid border placement.')
    scale=height_mm/mask.shape[0]
    offset={'inside':-width/2,'center':0,'outside':width/2}[placement]/scale if kind=='satin' else 0
    contours,_=cv2.findContours(mask.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    paths=[];warnings=[]
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
        extent=line.buffer(width/(2*scale)) if kind=='satin' else line
        x,y,r,b=extent.bounds
        if x<0 or y<0 or r>=mask.shape[1] or b>=mask.shape[0]:warnings.append('Border extends beyond the artwork canvas. Check hoop clearance and use Fit stitches.')
    if not paths:raise ValueError('No outer boundary available for a border.')
    if len(paths)>100:raise ValueError('Too many disconnected border outlines. Refine the subject selection.')
    warnings.append('Tight corners, tiny islands and narrow gaps require a physical sew-out. Internal holes are not bordered.')
    return dict(style=kind,width_mm=width,spacing_mm=spacing,colour=colour,placement=placement,paths=paths,warnings=list(dict.fromkeys(warnings)),scale=scale)

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
    if np.any(denom<.08):raise ValueError('Border corner is too sharp for satin. Use running stitch or smooth the selection.')
    shifts=(previous+normals)/denom[:,None]*radius
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
        attrs[f'{{{NS}}}trim_after']='true'
        ET.SubElement(document,'path',attrs)
    return len(columns)
