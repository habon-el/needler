"""Real pointer/keyboard measurement on disposable artwork, no customer writes."""
if __name__ == '__main__':
    from browser_workspace_isolated import main
    main(('browser_ruler.py',))
    raise SystemExit

import base64
from pathlib import Path
from browser_helpers import call, ev, wait

call('Emulation.setDeviceMetricsOverride',dict(width=1440,height=1000,deviceScaleFactor=1,mobile=False))
call('Page.navigate',dict(url=WORKSPACE_URL))
wait("!!window.DesignRuler && !embroideryStudio.isBusy() && document.getElementById('status').textContent.startsWith('Preview ready')")
before=ev('JSON.stringify(embroideryStudio.snapshot())')

def click(x,y,view='original',zoom=1):
    p=ev(f"(()=>{{const c=document.getElementById('{view}'),r=c.getBoundingClientRect(),s=Math.min(c.width/600,c.height/500)*.92*{zoom};return {{x:r.left+(c.width-600*s)/2+{x}*s,y:r.top+(c.height-500*s)/2+{y}*s}}}})()")
    for kind,buttons in [('mousePressed',1),('mouseReleased',0)]:
        call('Input.dispatchMouseEvent',dict(type=kind,**p,button='left',buttons=buttons,clickCount=1))

def distance():return ev("document.getElementById('rulerDistance').textContent")

ev("document.querySelector('[data-tool=measure]').click()")
click(200,200);click(300,200)
assert distance()=='A → B: 20.0 mm',distance()
ev("document.getElementById('clearRuler').click()")
click(200,200);click(260,280)
assert distance()=='A → B: 20.0 mm', '3-4-5 diagonal uses Euclidean distance'
call('Input.dispatchMouseEvent',dict(type='mousePressed',x=650,y=460,button='middle',buttons=4))
call('Input.dispatchMouseEvent',dict(type='mouseMoved',x=680,y=480,button='middle',buttons=4))
call('Input.dispatchMouseEvent',dict(type='mouseReleased',x=680,y=480,button='middle',buttons=0))
assert distance()=='A → B: 20.0 mm', 'Pan cannot change distance'
ev("document.getElementById('fit').click();document.getElementById('clearRuler').click()")
click(200,200);click(300,200)
assert distance()=='A → B: 20.0 mm'
# Drag-create, endpoint adjustment, whole-line movement and cancellation.
def drag(ax,ay,bx,by,cancel=False):
    def screen(x,y):
        return ev(f"(()=>{{const c=document.getElementById('original'),r=c.getBoundingClientRect(),s=Math.min(c.width/600,c.height/500)*.92;return {{x:r.left+(c.width-600*s)/2+{x}*s,y:r.top+(c.height-500*s)/2+{y}*s}}}})()")
    call('Input.dispatchMouseEvent',dict(type='mousePressed',**screen(ax,ay),button='left',buttons=1,clickCount=1))
    call('Input.dispatchMouseEvent',dict(type='mouseMoved',**screen(bx,by),button='left',buttons=1))
    if cancel:call('Input.dispatchKeyEvent',dict(type='keyDown',key='Escape',code='Escape'))
    live=distance()
    call('Input.dispatchMouseEvent',dict(type='mouseReleased',**screen(bx,by),button='left',buttons=0,clickCount=1))
    return live
ev("document.getElementById('clearRuler').click()")
assert drag(200,200,300,200)=='A → B: 20.0 mm'
assert drag(300,200,350,200)=='A → B: 30.0 mm'
assert drag(200,200,250,200)=='A → B: 20.0 mm'
assert drag(300,200,300,250)=='A → B: 20.0 mm'
assert drag(350,250,400,250,cancel=True)=='A → B: 20.0 mm'
ev("document.getElementById('rulerTarget').value='1';document.getElementById('original').focus()")
call('Input.dispatchKeyEvent',dict(type='keyDown',key='ArrowRight',code='ArrowRight'))
assert distance()=='A → B: 20.2 mm'
ev("document.getElementById('clearRuler').click()")
click(200,200);click(300,200)
assert before==ev('JSON.stringify(embroideryStudio.snapshot())')
ev("document.getElementById('zoomIn').click()")
assert distance()=='A → B: 20.0 mm'
ev("document.getElementById('clearRuler').click()")
click(200,200,zoom=1.25);click(300,200,zoom=1.25)
assert distance()=='A → B: 20.0 mm'
ev("document.documentElement.dataset.units='in'")
wait("document.getElementById('rulerDistance').textContent==='A → B: 0.787 in'")
ev("document.documentElement.dataset.units='mm';document.querySelector('[data-view=prepared]').click();document.getElementById('fit').click();document.getElementById('clearRuler').click()")
click(200,200,'prepared');click(300,200,'prepared')
assert distance()=='A → B: 20.0 mm'
ev("document.querySelector('[data-view=stitched]').click();document.getElementById('fit').click();document.getElementById('clearRuler').click()")
click(200,200,'stitched');click(300,200,'stitched')
assert distance()=='A → B: 20.0 mm'
assert before==ev('JSON.stringify(embroideryStudio.snapshot())')
ev("document.querySelector('[data-view=original]').click();document.getElementById('clearRuler').click();document.getElementById('original').focus()")
for key in ['Enter','ArrowRight','Enter']:
    call('Input.dispatchKeyEvent',dict(type='keyDown',key=key,code=key))
assert distance()=='A → B: 0.2 mm',distance()
call('Input.dispatchKeyEvent',dict(type='keyDown',key='Escape',code='Escape'))
assert distance()=='Click point A, then point B.'
click(200,200);click(300,200)
ev("document.getElementById('rulerEditSize').click()")
assert ev("!document.getElementById('topic-size').hidden && document.activeElement.dataset.option==='height_mm'")
# Existing size owner invalidates old stitches, retains the ruler's image anchors.
ev("const field=document.activeElement;field.value='50';field.dispatchEvent(new Event('input',{bubbles:true}));field.dispatchEvent(new Event('change',{bubbles:true}))")
wait("!embroideryStudio.isBusy() && embroideryStudio.snapshot().height_mm===50 && document.getElementById('status').textContent.startsWith('Preview ready')")
assert distance()=='A → B: 10.0 mm'
assert not ev('embroideryStudio.hasPlayback()')
ev("document.getElementById('undo').click()")
wait("!embroideryStudio.isBusy() && embroideryStudio.snapshot().height_mm===100 && document.getElementById('status').textContent.startsWith('Preview ready')")
assert distance()=='A → B: 20.0 mm'
Path('outputs/ruler-desktop.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',dict(format='png'))['result']['data']))
call('Emulation.setDeviceMetricsOverride',dict(width=390,height=844,deviceScaleFactor=1,mobile=True))
wait('document.documentElement.scrollWidth<=innerWidth')
assert ev("!!document.querySelector('[data-tool=measure]') && !document.getElementById('rulerBar').hidden")
Path('outputs/ruler-mobile.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',dict(format='png'))['result']['data']))
print('Ruler: pointer, zoom, three views, units, keyboard, no mutation, resize/Undo and narrow reflow passed')
