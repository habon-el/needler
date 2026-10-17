"""Actual WebGL/CPU comparison. Fixtures are written/read as PES before rendering."""
import base64
import io
import json
import time
from pathlib import Path
import numpy as np
import pyembroidery as emb
from PIL import Image
from browser_helpers import call,ev,wait
from test_thread_surface import write_fixture
from embroiderly.thread_surface import buffers,shade,fit_view,render_file,read_stream,rgb,rgb_lab

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/thread-surface';OUT.mkdir(exist_ok=True)
old=ev('performance.timeOrigin')
call('Page.navigate',{'url':'http://127.0.0.1:5050/'})
wait(f'performance.timeOrigin !== {old}')
wait('typeof window.ThreadSurface === "function"')
ev('window.testCanvas=document.createElement("canvas");testCanvas.width=600;testCanvas.height=320;window.testCtx=testCanvas.getContext("2d");window.testSurface=new ThreadSurface();document.body.replaceChildren(testCanvas)')

def gpu(plan,view):
    ev('window.fixture='+json.dumps(plan)+';window.view='+json.dumps(view)+';testCanvas.width=view.width;testCanvas.height=view.height')
    ev('testSurface.paint(testCtx,fixture,fixture.steps.length,view)')
    return screenshot()

def screenshot():
    encoded=ev('testCanvas.toDataURL("image/png")').split(',')[1]
    return Image.open(io.BytesIO(base64.b64decode(encoded))).convert('RGB')

lines=[((1,y),(11,y)) for y in np.arange(1,11,.4)]+[((x,1),(x,11)) for x in np.arange(14,24,.4)]
plan=write_fixture(OUT/'angle.pes',lines)
view=dict(width=600,height=320,s=1,factor=22,x=20,y=20,threadWidth=.375,fabric='#c2baa8',texture='twill',lightAngle=0,neutralLight=False)
a=gpu(plan,view);a.save(OUT/'angle-0.png')
ev('view.lightAngle=90;testSurface.paint(testCtx,fixture,fixture.steps.length,view)');b=screenshot();b.save(OUT/'angle-90.png')
# Same readback, same light -> identical output, including fibre variation.
ev('view.lightAngle=0;testSurface.paint(testCtx,fixture,fixture.steps.length,view)')
assert np.array_equal(a,screenshot())
assert ev('testSurface.builds')==1, 'Lighting must not rebuild the height buffers'
h,d,c,owner=buffers(plan,1200,640,44,[40,40])
cpu=np.rint(shade(h,d,c,44,[40,40],angle=0)*255).astype(np.uint8)
# Compare high-res buffers before browser-vs-Lanczos downsampling differences.
raw=ev('(()=>{const s=testSurface,g=s.gl,w=s.bufferWidth,h=s.bufferHeight,data=new Uint8Array(w*h*4);g.bindFramebuffer(g.READ_FRAMEBUFFER,s.fbos[3]);g.readPixels(0,0,w,h,g.RGBA,g.UNSIGNED_BYTE,data);const flip=new Uint8ClampedArray(data.length);for(let y=0;y<h;y++)flip.set(data.subarray(y*w*4,(y+1)*w*4),(h-1-y)*w*4);const c=document.createElement("canvas");c.width=w;c.height=h;c.getContext("2d").putImageData(new ImageData(flip,w,h),0,0);return c.toDataURL("image/png")})()').split(',')[1]
gpu_high=np.asarray(Image.open(io.BytesIO(base64.b64decode(raw))).convert('RGB'))
error=np.abs(cpu.astype(float)-gpu_high.astype(float))
metrics={'parity_mean_abs_rgb':float(error.mean()),'parity_thread_mean_abs_rgb':float(error[owner>=0].mean()),'parity_p99_rgb':float(np.percentile(error,99))}
assert metrics['parity_thread_mean_abs_rgb']<2.5,metrics
aa=np.asarray(a);bb=np.asarray(b)
left=(slice(45,250),slice(48,250));right=(slice(45,250),slice(337,530))
assert aa[left].mean()<aa[right].mean() and bb[left].mean()>bb[right].mean()
metrics['angle_brightness_swap']=True
Image.fromarray(cpu).resize((600,320),Image.Resampling.LANCZOS).save(OUT/'angle-cpu.png')
# Height/direction prefix must rewind exactly, not retain future ridges.
ev('testSurface.paint(testCtx,fixture,Math.floor(fixture.steps.length/2),view)')
partial=screenshot()
ev('testSurface.reset();testSurface.paint(testCtx,fixture,Math.floor(fixture.steps.length/2),view)')
assert np.array_equal(partial,screenshot())
metrics['prefix_rewind_deterministic']=True

defects=write_fixture(OUT/'defects.pes',[((1,2),(10,2)),((1,4),(4,4)),((6,4),(10,4))])
v=dict(view,width=600,height=320,factor=45,x=35,y=30,lightAngle=225)
gpu(defects,v).save(OUT/'defects.png')
for density,rows in [('normal',21),('dense',31)]:
    p=write_fixture(OUT/(density+'.pes'),[((1,y),(10,y)) for y in np.linspace(1,9,rows)])
    gpu(p,dict(v,width=600,height=500)).save(OUT/(density+'.png'))

# Saturated/neutral palette swatches are measured on the actual GPU output.
colours=['#126957','#527aa4','#ffffff','#000000','#ff0000','#ffec00','#9b3e58']
pattern=emb.EmbPattern()
for i,colour in enumerate(colours):
    pattern.add_thread(colour)
    if i:pattern.add_command(emb.COLOR_CHANGE)
    for y in np.arange(1,5,.4):
        pattern.add_stitch_absolute(emb.JUMP,(1+i*6)*10,y*10)
        pattern.add_stitch_absolute(emb.STITCH,(1+i*6)*10,y*10)
        pattern.add_stitch_absolute(emb.STITCH,(5+i*6)*10,y*10)
pattern.add_command(emb.END)
emb.write_pes(pattern,str(OUT/'neutral-colours.pes'),{'version':6})
coloured=read_stream(OUT/'neutral-colours.pes')
cv=dict(view,width=1000,height=220,factor=22,x=10,y=30,neutralLight=True)
pixels=np.asarray(gpu(coloured,cv))/255
# Measure full thread coverage, not an antialiased mixture of cloth and thread.
_,_,_,owners=buffers(coloured,2000,440,44,[20,60])
coverage=owners.reshape(220,2,1000,2)
deltas={}
for i,colour in enumerate(colours):
    complete=np.all(coverage==i,axis=(1,3));interior=complete.copy()
    for axis in (0,1):
        for shift in (-1,1):interior &= np.roll(complete,shift,axis=axis)
    average=pixels[interior].mean(axis=0)
    delta=float(np.linalg.norm(rgb_lab(average)-rgb_lab(rgb(colour))))
    assert delta<3,(colour,delta)
    deltas[colour]=delta
metrics['neutral_gpu_cie76_delta_e']=deltas
metrics['neutral_gpu_max_delta_e']=max(deltas.values())

# Thirty thousand sewn nonzero segments, not 30k JSON placeholders.
large=write_fixture(OUT/'30000.pes',[((col,row*.36),(col+.9,row*.36)) for row in range(150) for col in range(200)])
assert sum(1 for s in large['steps'] if s['t']=='stitch' and s['x']%1!=0)>=30000
large_view=dict(view,width=1440,height=900,factor=6.8,x=35,y=250,lightAngle=225)
t=time.perf_counter();gpu(large,large_view).save(OUT/'30000.png');metrics['initial_build_wall_ms']=(time.perf_counter()-t)*1000
timings=ev('(()=>{let frames=[];for(let i=0;i<12;i++){view.lightAngle=i*30;let t=performance.now();testSurface.paint(testCtx,fixture,fixture.steps.length,view);testSurface.gl.finish();if(i>=3)frames.push(performance.now()-t)}return frames})()')
metrics.update(frame_ms_median=float(np.median(timings)),frame_ms_p95=float(np.percentile(timings,95)),viewport=[1440,900],supersample=2,measured_frames=len(timings))
metrics['renderer']=ev('(()=>{const g=testSurface.gl,e=g.getExtension("WEBGL_debug_renderer_info");return e?g.getParameter(e.UNMASKED_RENDERER_WEBGL):g.getParameter(g.RENDERER)})()')
metrics['frame_budget_33ms_met']=metrics['frame_ms_p95']<=33.3
cached=ev('(()=>{let frames=[];for(let i=0;i<9;i++){let t=performance.now();testSurface.paint(testCtx,fixture,fixture.steps.length,view);testSurface.gl.finish();frames.push(performance.now()-t)}return frames})()')
metrics['unchanged_frame_ms_median']=float(np.median(cached))
(OUT/'verification.json').write_text(json.dumps(metrics,indent=2)+'\n')
print(json.dumps(metrics,indent=2))
print('PASS: exported fixtures; GPU/CPU parity; angle swap; determinism; prefix rewind. Performance and physical validation reported separately.')
