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
    ('step','Step fill','Tatami with stepped needle holes'),
    ('gradient','Gradient','Dense to open across the area'),
    ('shaded','Shaded','Tatami with a darker shade fading across it · one more thread'),
    ('radial','Radial','Rays from the centre'),
    ('wave','Wave','Rows that rise and fall in smooth waves'),
    ('florentine','Florentine','Rows follow the curve of the top edge'),
    ('applique','Appliqué','Fabric piece, satin edge · 2 stops'),
    ('satin','Satin','Follows the shape · parts up to 8 mm wide'),
    ('raised_satin','3D satin','Three satin layers · experimental, no foam'),
    ('puff','3D puff','Satin over foam · parts 3–6 mm wide (2 mm foam: 2–6)'),
    ('motif','Motif','Small repeated shapes · open fill'),
    ('embossed','Embossed','Tatami + diamond overlay · experimental texture'),
    ('ripple','Ripple','Concentric circular waves'),
    ('maze','Maze','One line winding like a labyrinth · open fill'),
    ('star','Star','Star-shaped spiral from the centre · open fill'),
    ('contour','Offset fill','Rows follow the outline inward, around holes'),
    ('cross','Cross stitch','Clipped diagonal crosses · open fill'),
    ('stipple','Stipple','Meandering open fill'),
    ('blackwork_fill','Blackwork','Lattice of straight lines · open fill'),
    ('candlewick_fill','Candlewicking','Raised knots in rows · open fill'),
    ('lacework','Lacework','Honeycomb net · open fill'),
]
OPEN_FILLS=('blackwork_fill','candlewick_fill','lacework')   # whole-area patterns (open_fill_shapes)
# Choices under a style, first = default. Stored with the style as 'motif:heart'; the default
# is stored as the plain style, so saved designs keep their look.
VARIANTS={
    'motif':[('diamond','Diamonds'),('heart','Hearts'),('star','Stars'),('scale','Scales'),('circle','Circles')],
    'stipple':[('run','Single run'),('backstitch','Backstitch'),('stemstitch','Stemstitch')],
}


def split_style(style):
    """'motif:heart' -> ('motif','heart'); a plain style -> (style, its default choice or '')."""
    base,_,variant=style.partition(':')
    return base,variant or (VARIANTS[base][0][0] if base in VARIANTS else '')


def assignments(options):
    value=options.get('region_styles',{})
    if not isinstance(value,dict) or len(value)>500:
        raise ValueError('Region stitch styles must contain at most 500 area assignments.')
    allowed={item[0] for item in CATALOG}|{f'{base}:{v}' for base,choices in VARIANTS.items() for v,_ in choices[1:]}
    for key,style in value.items():
        if not isinstance(key,str) or len(key)!=20 or any(c not in '0123456789abcdef' for c in key) or not isinstance(style,str) or style not in allowed:
            raise ValueError('Invalid region stitch style. Select a current area and a listed style.')
    return value


def hole_choices(options):
    """Areas whose holes are sewn over (remove/fill holes): {area id: 'fill'}."""
    value=options.get('area_holes',{})
    if not isinstance(value,dict) or len(value)>500 or any(
            not isinstance(k,str) or len(k)!=20 or any(c not in '0123456789abcdef' for c in k) or v!='fill'
            for k,v in value.items()):
        raise ValueError('Invalid hole choice. Select a current area and try again.')
    return value


def angle_choices(options):
    """Stitch direction per area, degrees (0 = horizontal rows, positive = rising to the right)."""
    value=options.get('area_angles',{})
    if not isinstance(value,dict) or len(value)>500 or any(
            not isinstance(k,str) or len(k)!=20 or any(c not in '0123456789abcdef' for c in k)
            or type(v) not in (int,float) or not -180<=v<=180 for k,v in value.items()):
        raise ValueError('Enter a stitch direction from -180° to 180°.')
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


TURNING_SATIN_MM=8.0  # widest part the shape-following satin accepts (wider columns are split)


def satin_reason(rings,scale):
    """Why this area cannot be Satin ('' when it can): straight satin for simple convex areas,
    otherwise satin that follows the shape's centre line, for parts up to TURNING_SATIN_MM wide."""
    try:
        satin_rails(rings,scale);return ''
    except ValueError:pass
    from shapely.ops import polylabel
    p=polygon(rings,scale)
    if not p.is_valid:p=p.buffer(0)
    if p.is_empty:return 'This area is too small for satin.'
    p=max(getattr(p,'geoms',[p]),key=lambda g:g.area)
    width=2*polylabel(p,.05).distance(p.boundary)
    if width>TURNING_SATIN_MM:
        return f'Satin is for parts up to {TURNING_SATIN_MM:g} mm wide; this one is {width:.1f} mm. Use Tatami, or split the area.'
    return ''


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
        return dict(areas=[],stale=list(chosen),catalog=CATALOG,variants=VARIANTS,unavailable='Area fills require colour artwork mode. Black lines keep Running/Reinforced; portrait stitching has its own planner.')
    for key,colour,rings in regions(rgb,alpha):
        if len(items)>=500:break
        reason=satin_reason(rings,scale)
        try:satin_rails(rings,scale);raised=''
        except ValueError as error:raised=str(error)   # 3D satin still needs a simple straight band
        x,y,w,h=cv2.boundingRect(rings[0])
        notice=''
        if chosen.get(key)=='embossed':
            try:
                if not decorative_paths(rings,scale,'embossed'):
                    notice='Embossed: this area is too small for a texture repeat; its base fill is preserved.'
            except ValueError as error:notice=str(error)
        items.append(dict(id=key,colour=colour,bounds=[x,y,w,h],rings=[r.reshape(-1,2).tolist() for r in rings],style_notice=notice,style=chosen.get(key,'tatami'),satin_reason=reason,raised_reason=raised,
                          holes=len(rings)-1,holes_filled=hole_choices(options).get(key)=='fill',
                          angle=angle_choices(options).get(key)))
    # Styles of duplicated pieces belong to the copies, not to stale picture areas.
    from .piece_layout import copy_ids
    return dict(areas=items,stale=sorted(set(chosen)-{r['id'] for r in items}-copy_ids(options)),catalog=CATALOG,variants=VARIANTS,unavailable='')


def path_data(points):
    return 'M '+' L '.join(f'{x:.5f},{y:.5f}' for x,y in points)


MOTIF_PITCH=4.0  # mm between repeats


def motif_shapes(pattern,x,y,row):
    """Polylines (mm) of one repeat in the cell at (x,y); our own simple shapes, about 3.2 mm."""
    cx,cy=x+2,y+2
    if pattern=='heart':
        t=np.linspace(0,2*math.pi,25)
        hx=16*np.sin(t)**3;hy=13*np.cos(t)-5*np.cos(2*t)-2*np.cos(3*t)-np.cos(4*t)
        return [list(zip(cx+hx*.1,cy-(hy+2.5)*.1))]
    if pattern=='star':
        a=-math.pi/2+np.arange(11)*math.pi/5;r=np.where(np.arange(11)%2,.75,1.9)
        return [list(zip(cx+r*np.cos(a),cy+.15+r*np.sin(a)))]
    if pattern=='circle':
        a=np.linspace(0,2*math.pi,17)
        return [list(zip(cx+1.5*np.cos(a),cy+1.5*np.sin(a)))]
    if pattern=='scale':
        # Fish scales: half circles joined end to end, every other row shifted half a repeat.
        a=np.linspace(math.pi,2*math.pi,9);sx=x+(2 if row%2 else 0)
        return [list(zip(sx+2+2*np.cos(a),y+4+2*np.sin(a)))]
    return [[(x+2,y),(x+4,y+2),(x+2,y+4),(x,y+2),(x+2,y)]]


LACE_SIDE=2.0   # mm, one side of a lacework honeycomb cell
KNOT_PITCH=4.0  # mm between candlewicking knots


def open_fill_shapes(bounds,kind):
    """Polylines (mm) across the area's box. Blackwork: a lattice of long lines (across, down
    and both diagonals) so it sews in few pieces. Lacework: rows of half honeycomb cells, each
    row sharing its flat sides with the next. Candlewicking: knots on staggered rows, twelve
    spokes out from one hole and back."""
    left,top,right,bottom=bounds;shapes=[]
    if kind=='blackwork_fill':
        pitch=MOTIF_PITCH;span=(right-left)+(bottom-top)
        for y in np.arange(top+pitch/2,bottom,pitch):shapes.append([(left,y),(right,y)])
        for x in np.arange(left+pitch/2,right,pitch):shapes.append([(x,top),(x,bottom)])
        # Diagonals through the cell edges' middles make a diamond in every cell.
        for c in np.arange(-span,span,pitch):
            shapes.append([(left+c,top),(left+c+span,top+span)])
            shapes.append([(left+c,bottom),(left+c+span,bottom-span)])
    elif kind=='lacework':
        s=LACE_SIDE;d=s*math.sqrt(3)/2
        for k,y in enumerate(np.arange(top-d,bottom+d,d)):
            x=left-3*s+(1.5*s if k%2 else 0);row=[(x,y)]
            while x<right+3*s:
                row+=[(x+s,y),(x+1.5*s,y+d),(x+2.5*s,y+d),(x+3*s,y)];x+=3*s
            shapes.append(row)
    else:
        r=.7
        for k,y in enumerate(np.arange(top+KNOT_PITCH/2,bottom,KNOT_PITCH)):
            for x in np.arange(left+KNOT_PITCH/2+(KNOT_PITCH/2 if k%2 else 0),right,KNOT_PITCH):
                knot=[(x,y)]
                for j in range(12):
                    a=math.radians(j*60+(30 if j>=6 else 0))
                    knot+=[(x+r*math.cos(a),y+r*math.sin(a)),(x,y)]
                shapes.append(knot)
    return shapes


def decorative_paths(rings,scale,kind,pattern='diamond'):
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
    left,top,right,bottom=p.bounds;pitch=MOTIF_PITCH;parts=[]
    if math.ceil((right-left)/pitch)*math.ceil((bottom-top)/pitch)>400:
        raise ValueError('Decorative pattern exceeds 400 cells. Use a smaller area or Tatami.')
    # Scales are shifted half a repeat on every other row: start one repeat further left.
    columns=np.arange(left-(pitch if pattern=='scale' else 0),right,pitch)
    if kind in OPEN_FILLS:
        from shapely.geometry import Point
        for shape in open_fill_shapes(p.bounds,kind):
            if kind=='candlewick_fill':
                # Whole knots only; clipping a line that retraces itself would merge its spokes.
                if p.contains(Point(shape[0]).buffer(.75)):parts.append(path_data(np.asarray(shape)/scale))
                continue
            clipped=p.intersection(LineString(shape))
            for segment in [clipped] if clipped.geom_type=='LineString' else list(getattr(clipped,'geoms',[])):
                if segment.geom_type=='LineString' and segment.length>=.4:
                    parts.append(path_data(np.asarray(segment.coords)/scale))
        columns=[]
    for row,y in enumerate(np.arange(top,bottom,pitch)):
        for x in columns:
            shapes=[[(x,y),(x+pitch,y+pitch)],[(x+pitch,y),(x,y+pitch)]] if kind=='cross' else motif_shapes(pattern,x,y,row)
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
    kind,pattern=split_style(kind)
    if kind=='tatami':return
    if kind=='applique':
        # Placement, stop, tack-down, stop, satin cover (stitch_engine._applique).
        node.set(NS+'fill_method','applique');node.set(NS+'applique_cover_mm','3')
        return
    if kind=='shaded':
        # Depth from two shades: the area's own tatami, then a darker shade on top, dense on one
        # side and fading out (stitch_fills.gradient), as a digitizer layers feather tips.
        from .fill_shaping import angle as fill_angle
        from .engine import darker
        colour=node.get('style').split(';')[0].split(':')[1]
        shade=ET.SubElement(document,'path',dict(node.attrib));shade.set('id',node.get('id')+'-shade')
        shade.set('style',f'fill:{darker(colour,.7)};fill-rule:evenodd;stroke:none')
        shade.set(NS+'fill_method','gradient_fill');shade.set(NS+'angle',f'{fill_angle(rings)+90:.1f}')
        shade.set(NS+'fill_underlay','false');shade.set(NS+'gradient_open_spacing_mm','2.4')
        return
    if kind in ('step','gradient','radial','wave','florentine'):
        # Specialty fills (stitch_fills); rows run along the area's long side.
        from .fill_shaping import angle as fill_angle
        node.set(NS+'fill_method',kind+'_fill');node.set(NS+'angle',f'{fill_angle(rings):.1f}')
        if kind=='gradient':node.set(NS+'fill_underlay','false')  # underlay would show through the open end
        return
    if kind=='puff':
        # Dense satin over foam, sewn after a stop; see stitch_engine._puff_area.
        node.set(NS+'fill_method','puff_satin');node.set(NS+'zigzag_spacing_mm','.22')
        node.set(NS+'pull_compensation_mm','.45')
        return
    if kind in ('contour','ripple','stipple','maze','star'):
        node.set(NS+'fill_method',{'contour':'contour_fill','ripple':'circular_fill','stipple':'meander_fill',
                                   'maze':'maze_fill','star':'star_fill'}[kind])
        if kind!='contour':node.set(NS+'fill_underlay','false')
        if kind=='maze':
            # Lanes 1 mm apart, square corners kept (stitch_fills.maze).
            node.set(NS+'row_spacing_mm','1');node.set(NS+'running_stitch_length_mm','1.5')
            node.set(NS+'running_stitch_tolerance_mm','.05')
        if kind=='star':node.set(NS+'row_spacing_mm','1.6');node.set(NS+'running_stitch_length_mm','2')
        if kind=='contour':
            # Offset fill: open underlay rows along the long side hold the fabric under the rings.
            from .fill_shaping import angle as fill_angle
            node.set(NS+'fill_underlay','true');node.set(NS+'angle',f'{fill_angle(rings):.1f}')
        if kind=='ripple':
            node.set(NS+'row_spacing_mm','1.2');node.set(NS+'running_stitch_length_mm','1')
            node.set(NS+'running_stitch_tolerance_mm','.15')
        if kind=='stipple':
            node.set(NS+'meander_scale_percent','20');node.set(NS+'smoothness_mm','.3')
            if pattern!='run':node.set(NS+'stipple_stitch',pattern)  # backstitch or stemstitch (stitch_fills.meander)
            node.set(NS+'clip','true');node.set(NS+'running_stitch_length_mm','1')
            node.set(NS+'running_stitch_tolerance_mm','.15')
        return
    if kind=='satin':
        try:satin_rails(rings,scale)
        except ValueError:
            # Not a simple straight band: satin columns that follow the shape and taper with it.
            reason=satin_reason(rings,scale)
            if reason:raise ValueError(reason)
            node.set(NS+'fill_method','auto_satin');node.set(NS+'zigzag_spacing_mm','.4')
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
    if kind in ('motif','cross','embossed')+OPEN_FILLS:
        colour=node.get('style').split(';')[0].split(':')[1]
        decoration=decorative_paths(rings,scale,kind,pattern)
        if not decoration:return  # Embossed retains its base; inventory discloses no fitting repeat.
        target=ET.SubElement(document,'path',id=node.get('id')+'-texture') if kind=='embossed' else node
        # The area outline lets the generator travel inside it between fragments.
        target.set(NS+'travel_area',node.get('d'))
        target.set('d',decoration)
        target.set('style',f'fill:none;stroke:{colour};stroke-width:1')
        target.set(NS+'stroke_method','running_stitch');target.set(NS+'running_stitch_length_mm','2')
        if kind=='motif' and pattern!='diamond':
            # Curved repeats: shorter stitches that keep their points, so hearts stay round.
            target.set(NS+'running_stitch_length_mm','1.2');target.set(NS+'running_stitch_tolerance_mm','.05')
        if kind=='lacework':target.set(NS+'running_stitch_length_mm','1.5')
        if kind=='candlewick_fill':target.set(NS+'running_stitch_tolerance_mm','0')  # keep every spoke
        return
    raise ValueError('Unsupported stitch style.')
