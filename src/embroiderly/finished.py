"""Supersampled thread rendering from resolved written-file events."""
from math import atan2, cos, pi
from PIL import Image, ImageDraw, ImageColor

def render_finished(payload, fabric='#c2baa8', pixels_per_mm=12):
    points=[(s['x'],s['y']) for s in payload['steps'] if s['t'] in ('stitch','jump')]
    if not points:
        return Image.new('RGB',(120,120),fabric)
    minx=min(x for x,y in points);miny=min(y for x,y in points)
    maxx=max(x for x,y in points);maxy=max(y for x,y in points)
    # Cap the final longest edge for bounded memory, retaining 3x supersampling.
    scale=min(pixels_per_mm,1600/max(maxx-minx+10,maxy-miny+10))
    w=max(1,round((maxx-minx+10)*scale));h=max(1,round((maxy-miny+10)*scale))
    ss=3
    image=Image.new('RGB',(w*ss,h*ss),fabric);draw=ImageDraw.Draw(image)
    base=ImageColor.getrgb(fabric)
    weave=tuple(max(0,v-7) for v in base)
    for x in range(0,w*ss,9):draw.line((x,0,x,h*ss),fill=weave,width=1)
    for y in range(0,h*ss,9):draw.line((0,y,w*ss,y),fill=weave,width=1)
    def xy(p):return ((p[0]-minx+5)*scale*ss,(p[1]-miny+5)*scale*ss)
    def stroke(a,b,col,width):
        draw.line((*a,*b),fill=col,width=width)
        radius=width/2
        for x,y in (a,b):draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill=col)
    previous=(0,0)
    for step in payload['steps']:
        point=(step['x'],step['y'])
        if step['t']=='stitch' and point!=previous:
            a,b=xy(previous),xy(point)
            rgb=ImageColor.getrgb(step['color'])
            angle=atan2(point[1]-previous[1],point[0]-previous[0])
            intensity=1+.15*cos(2*(angle-pi/4))
            colour=tuple(min(255,max(0,round(v*intensity))) for v in rgb)
            width=max(1,round(payload.get('thread_width_mm',.22)*scale*ss))
            stroke((a[0]+ss*.15,a[1]+ss*.15),(b[0]+ss*.15,b[1]+ss*.15),tuple(round(v*.8) for v in colour),width)
            stroke(a,b,colour,width)
            start=tuple(a[i]+.175*(b[i]-a[i]) for i in (0,1))
            end=tuple(a[i]+.825*(b[i]-a[i]) for i in (0,1))
            stroke(start,end,tuple(min(255,round(v+(255-v)*.18)) for v in colour),max(1,width//3))
        previous=point
    return image.resize((w,h),Image.Resampling.LANCZOS)
