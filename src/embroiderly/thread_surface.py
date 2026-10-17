"""Deterministic, illustrative thread surface from machine-file readback only.

No digitizing, smoothing, interpolation of missing paths, foam, or file writes.
CPU reference for thread-surface.js. Dimensions are mm; widths are visual
assumptions, not manufacturer-certified thread diameters or measured height.
"""
from pathlib import Path
import math
import numpy as np
from PIL import Image
import pyembroidery as emb

FABRICS = ('twill', 'pique', 'knit', 'fleece', 'cap')
MAX_COMMANDS = 200_000


def read_stream(path, palette=None):
    path = Path(path)
    if path.suffix.lower() not in ('.pes', '.dst'):
        raise ValueError('A written PES or DST file is required, not an internal plan.')
    if path.suffix.lower() == '.dst' and not palette:
        raise ValueError('DST does not contain thread colours; supply its explicit palette.')
    from .machine_files import read_pattern
    pattern = read_pattern(path)
    if len(pattern.stitches) > MAX_COMMANDS:
        raise ValueError('Mockup limit is 200,000 machine commands; use line inspection.')
    colours = palette or [t.hex_color() for t in pattern.threadlist]
    if not colours:
        raise ValueError('The written file has no thread palette.')
    kinds = {emb.STITCH:'stitch', emb.JUMP:'jump', emb.TRIM:'trim',
             emb.COLOR_CHANGE:'color_change', emb.END:'end'}
    steps, colour = [], 0
    for x, y, flags in pattern.stitches:
        kind = kinds.get(flags & emb.COMMAND_MASK, 'unknown')
        if kind == 'color_change':
            colour += 1
        if kind == 'stitch' and colour >= len(colours):
            raise ValueError('The supplied palette is shorter than the written colour sequence.')
        if not np.isfinite([x,y]).all() or max(abs(x), abs(y)) > 100_000:
            raise ValueError('Written coordinates exceed the preview bounds.')
        steps.append(dict(x=x/10, y=y/10, t=kind, color=colours[min(colour,len(colours)-1)]))
    return dict(steps=steps, colors=colours, origin_mm=[0,0], source='export-readback')


def rgb(hex_colour):
    if not isinstance(hex_colour,str) or len(hex_colour)!=7 or hex_colour[0]!='#':
        raise ValueError('Use a six-digit RGB colour.')
    return np.array([int(hex_colour[i:i+2],16)/255 for i in (1,3,5)],np.float32)


def rgb_lab(c):
    c=np.asarray(c,dtype=np.float32)
    linear=np.where(c<=.04045,c/12.92,((c+.055)/1.055)**2.4)
    xyz=linear @ np.array([[.4124564,.2126729,.0193339],[.3575761,.7151522,.1191920],[.1804375,.0721750,.9503041]],np.float32)
    xyz/=np.array([.95047,1,1.08883],np.float32)
    f=np.where(xyz>.008856,np.cbrt(xyz),7.787*xyz+16/116)
    return np.stack((116*f[...,1]-16,500*(f[...,0]-f[...,1]),200*(f[...,1]-f[...,2])),axis=-1)


def lab_rgb(lab):
    fy=(lab[...,0]+16)/116
    f=np.stack((fy+lab[...,1]/500,fy,fy-lab[...,2]/200),axis=-1)
    xyz=np.where(f**3>.008856,f**3,(f-16/116)/7.787)*np.array([.95047,1,1.08883],np.float32)
    linear=xyz @ np.array([[3.2404542,-.9692660,.0556434],[-1.5371385,1.8760108,-.2040259],[-.4985314,.0415560,1.0572252]],np.float32)
    c=np.where(linear<=.0031308,12.92*linear,1.055*np.maximum(linear,0)**(1/2.4)-.055)
    return np.clip(c,0,1)


def segments(plan, cursor=None):
    previous=(0.,0.)
    for index,step in enumerate(plan['steps'][:cursor]):
        point=(step['x'],step['y'])
        if step['t']=='stitch' and point!=previous:
            yield index,previous,point,step['color']
        previous=point


def fit_view(plan, width, height, padding=2):
    points=[p for _,a,b,_ in segments(plan) for p in (a,b)]
    if not points:
        raise ValueError('This export has no sewn segments.')
    points=np.array(points);low=points.min(0)-padding;high=points.max(0)+padding
    ppm=min(width/(high[0]-low[0]),height/(high[1]-low[1]))
    return float(ppm),((np.array([width,height])-(high+low)*ppm)/2).tolist()


def buffers(plan, width, height, ppm, offset, strand=.375, cursor=None):
    """Ordered rounded ridges; jump/trim/end never deposit thread."""
    h=np.zeros((height,width),np.float32)
    direction=np.zeros((height,width,4),np.float32)
    colour=np.zeros((height,width,3),np.float32)
    owner=np.full((height,width),-1,np.int32)
    palette={c:i for i,c in enumerate(plan['colors'])}
    radius=strand/2
    for index,a,b,hex_colour in segments(plan,cursor):
        a=np.array(a);b=np.array(b);delta=b-a;length=float(np.linalg.norm(delta));tangent=delta/length
        lo=np.floor((np.minimum(a,b)-radius*1.1)*ppm+offset).astype(int)
        hi=np.ceil((np.maximum(a,b)+radius*1.1)*ppm+offset).astype(int)
        x0,y0=np.maximum(lo,0);x1,y1=np.minimum(hi,[width,height])
        if x0>=x1 or y0>=y1:continue
        xx=(np.arange(x0,x1,dtype=np.float32)+.5-offset[0])/ppm-a[0]
        yy=(np.arange(y0,y1,dtype=np.float32)+.5-offset[1])/ppm-a[1]
        along=xx[None,:]*tangent[0]+yy[:,None]*tangent[1]
        across=-xx[None,:]*tangent[1]+yy[:,None]*tangent[0]
        taper=np.clip(np.minimum(along,length-along)/max(strand*.75,.001),0,1)
        taper=taper*taper*(3-2*taper)
        seed=((index*37+17)%997)/997
        # Fibre displacement only: both exported needle endpoints stay fixed.
        across=across-(seed-.5)*strand*.035*taper
        radial=np.sqrt(np.maximum(0,1-(across/radius)**2))
        ridge=radius*radial*taper
        mask=(abs(across)<radius)&(along>0)&(along<length)&(ridge>.00001)
        tile=h[y0:y1,x0:x1];tile[mask]+=ridge[mask]
        d=direction[y0:y1,x0:x1];d[mask,0]=tangent[0];d[mask,1]=tangent[1]
        phase=along/.55+across/max(strand,.001)*.7+seed
        d[mask,2]=phase[mask]%1;d[mask,3]=seed
        colour[y0:y1,x0:x1][mask]=rgb(hex_colour)
        owner[y0:y1,x0:x1][mask]=palette[hex_colour]
    return h,direction,colour,owner


def weave(x,y,kind):
    tau=2*np.pi
    if kind=='pique':return .016*np.cos(tau*x/.7)*np.cos(tau*y/.7)
    if kind=='knit':return .014*np.sin(tau*x/.65+.7*np.sin(tau*y/.9))+.006*np.cos(tau*y/.9)
    if kind=='fleece':return .006*(np.sin(tau*(x*4+y*3))+np.cos(tau*(x*7-y*5))+np.sin(tau*(x*11+y*9)))
    pitch=.45 if kind=='cap' else .6
    return .012*np.sin(tau*(x+y)/pitch)+.006*np.cos(tau*x/.35)*np.cos(tau*y/.35)


def shade(h,direction,colour,ppm,offset,fabric='#c2baa8',texture='twill',angle=225,neutral=False):
    """Same equations as GLSL; no stochastic calls or order-dependent light state."""
    height,width=h.shape
    xx=(np.arange(width,dtype=np.float32)+.5-offset[0])/ppm
    yy=(np.arange(height,dtype=np.float32)+.5-offset[1])/ppm
    x,y=np.meshgrid(xx,yy)
    light=np.array([0,0,1],np.float32) if neutral else np.array([math.cos(math.radians(angle))*.70710678,math.sin(math.radians(angle))*.70710678,.70710678],np.float32)
    half=(light+[0,0,1]);half/=np.linalg.norm(half)
    p=np.pad(h,1,mode='edge');left=p[1:-1,:-2];right=p[1:-1,2:];up=p[:-2,1:-1];down=p[2:,1:-1]
    nx=-(right-left)*ppm/2;ny=-(down-up)*ppm/2
    diffuse=(nx*light[0]+ny*light[1]+light[2])/np.sqrt(nx*nx+ny*ny+1)
    dot=direction[...,0]*half[0]+direction[...,1]*half[1]
    shine=np.maximum(0,1-dot*dot)**6
    ao=np.clip(((left+right+up+down)/4-h)*2,0,.3)
    delta=12*(diffuse-light[2]*.78)+14*(shine-.6)+2*np.cos(direction[...,2]*2*np.pi)+.9*(direction[...,3]-.5)-15*ao
    if neutral:delta=np.clip(delta,-1.25,1.25)
    lab=rgb_lab(colour);lab[...,0]=np.clip(lab[...,0]+delta,0,100)
    thread=lab_rgb(lab)
    weave_h=weave(x,y,texture)
    wx=-(weave(x+.02,y,texture)-weave(x-.02,y,texture))/.04
    wy=-(weave(x,y+.02,texture)-weave(x,y-.02,texture))/.04
    fd=(wx*light[0]+wy*light[1]+light[2])/np.sqrt(wx*wx+wy*wy+1)
    shadow=np.zeros_like(h)
    iy,ix=np.indices(h.shape)
    for distance,weight in ((.18,.5),(.4,.3),(.8,.2)):
        sx=np.clip(np.floor(ix+.5+light[0]*distance*ppm).astype(int),0,width-1)
        sy=np.clip(np.floor(iy+.5+light[1]*distance*ppm).astype(int),0,height-1)
        shadow+=weight*np.clip((h[sy,sx]-h-distance*light[2])/.15,0,1)
    cloth=np.clip(rgb(fabric)[None,None,:]*(1+.16*(fd-light[2])+.035*weave_h/.018-.23*shadow-.2*ao)[...,None],0,1)
    return np.where((h>0)[...,None],thread,cloth)


def render_file(path, width=960, height=720, strand=.375, fabric='#c2baa8', texture='twill', angle=225, neutral=False, palette=None, supersample=2):
    if not (64<=width<=1200 and 64<=height<=900 and supersample in (2,3) and width*height*supersample**2<=5_000_000):
        raise ValueError('Mockup dimensions exceed the bounded render size.')
    if not math.isfinite(strand) or not .1<=strand<=.8 or not math.isfinite(angle) or not 0<=angle<=360 or texture not in FABRICS:
        raise ValueError('Invalid thread appearance settings.')
    rgb(fabric)
    plan=read_stream(path,palette)
    w,h=width*supersample,height*supersample
    ppm,offset=fit_view(plan,w,h)
    heights,d,c,_=buffers(plan,w,h,ppm,offset,strand)
    pixels=np.rint(shade(heights,d,c,ppm,offset,fabric,texture,angle,neutral)*255).astype(np.uint8)
    return Image.fromarray(pixels).resize((width,height),Image.Resampling.LANCZOS)
