"""Real-browser checks on disposable artwork; run directly or through the runner."""
if __name__ == '__main__':
    from browser_workspace_isolated import main
    main()
    raise SystemExit

import base64
import json
import time
from pathlib import Path

from browser_helpers import call, ev, wait, ws
ws.settimeout(20)
call('Emulation.setDeviceMetricsOverride', dict(width=1440,height=1000,deviceScaleFactor=1,mobile=False))
previous_origin = ev('performance.timeOrigin')
call('Page.navigate', dict(url=WORKSPACE_URL))
wait(f'performance.timeOrigin !== {previous_origin}')
wait("!!window.embroideryWorkspace && !embroideryStudio.isBusy() && document.getElementById('status').textContent.startsWith('Preview ready')")
baseline = ev('JSON.stringify(embroideryStudio.snapshot())')
assert ev("document.querySelectorAll('.topic-panel:not([hidden])').length===1")
assert ev("document.querySelectorAll('.topic-nav button').length===8")
assert ev("document.querySelectorAll('.tools button .ui-icon').length===document.querySelectorAll('.tools button').length")
assert ev("document.documentElement.scrollWidth<=innerWidth")
assert ev("[...document.querySelectorAll(\"[data-view]\")].every(e=>e.tagName===\"BUTTON\")"), "View selector must not match the canvas container"
for topic in ['ask','colours','borders','size','details','review','styles','selection']:
    ev(f"document.querySelector('[data-topic={topic}]').click()")
    assert baseline == ev('JSON.stringify(embroideryStudio.snapshot())')
    assert ev(f"!document.getElementById('topic-{topic}').hidden")
Path('outputs/workspace-after.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',dict(format='png'))['result']['data']))

def point(x,y):
    # Invert the studio's current mapping, including fit, pan, zoom and CSS size.
    ev("document.getElementById('original').scrollIntoView({block:'center'})")
    return ev(f"""(()=>{{const c=document.getElementById('original'),r=c.getBoundingClientRect();
      const cx=r.left+r.width/2,cy=r.top+r.height/2;
      const a=embroideryStudio.point({{clientX:cx,clientY:cy}});
      const b=embroideryStudio.point({{clientX:cx+1,clientY:cy+1}});
      return {{x:cx+({x}-a[0])/(b[0]-a[0]),y:cy+({y}-a[1])/(b[1]-a[1])}}}})()""")

def mouse(kind,p,buttons=0):
    call('Input.dispatchMouseEvent',dict(type=kind,x=p['x'],y=p['y'],button='left',buttons=buttons,clickCount=1))

def click_at(x,y):
    p=point(x,y)
    assert ev(f"document.elementFromPoint({p['x']},{p['y']})?.id")=='original', p
    mouse('mousePressed',p,1);mouse('mouseReleased',p)

ev("document.querySelector('[data-tool=erase-outline]').click()")
for x,y in [(230,180),(350,180),(350,300),(230,300)]: click_at(x,y)
assert baseline==ev('JSON.stringify(embroideryStudio.snapshot())'), 'Draft must not modify options'
assert ev("document.getElementById('applyOutline').textContent==='Erase area'")
Path('outputs/erase-area-draft.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',dict(format='png'))['result']['data']))
ev("document.getElementById('cancelOutline').click()")
assert baseline==ev('JSON.stringify(embroideryStudio.snapshot())')
for x,y in [(230,180),(350,180),(350,300),(230,300)]: click_at(x,y)
ev("document.getElementById('applyOutline').click()")
wait("!embroideryStudio.isBusy() && document.getElementById('status').textContent.startsWith('Preview ready')")
assert ev("embroideryStudio.snapshot().edits.at(-1).shape==='polygon'")
ev("document.getElementById('undo').click()")
wait("!embroideryStudio.isBusy() && document.getElementById('status').textContent.startsWith('Preview ready')")
assert baseline==ev('JSON.stringify(embroideryStudio.snapshot())'), 'Undo restores exact options'

# Cancel a captured brush stroke. This previously committed it.
ev("document.querySelector('.extra-tools').open=true;document.querySelector('[data-tool=erase]').click()")
p=point(280,220);mouse('mousePressed',p,1);mouse('mouseMoved',point(300,225),1)
ev("document.getElementById('original').dispatchEvent(new PointerEvent('pointercancel',{pointerId:1,bubbles:true}))")
mouse('mouseReleased',point(300,225))
assert baseline==ev('JSON.stringify(embroideryStudio.snapshot())'), 'Cancel restores options'

# Keyboard activation, select navigation, responsive access, reduced motion.
ev("workflowBack.click();workflowBorders.focus()")
call('Input.dispatchKeyEvent',dict(type='keyDown',key='Enter',code='Enter',text='\r',windowsVirtualKeyCode=13))
call('Input.dispatchKeyEvent',dict(type='keyUp',key='Enter',code='Enter',windowsVirtualKeyCode=13))
assert ev("!document.getElementById('topic-borders').hidden")
ev("document.querySelector('[data-border=border_style]').focus()")
call('Input.dispatchKeyEvent',dict(type='keyDown',key='F4',code='F4',windowsVirtualKeyCode=115))
call('Input.dispatchKeyEvent',dict(type='keyUp',key='F4',code='F4',windowsVirtualKeyCode=115))
call('Input.dispatchKeyEvent',dict(type='keyDown',key='Escape',code='Escape',windowsVirtualKeyCode=27))
call('Input.dispatchKeyEvent',dict(type='keyUp',key='Escape',code='Escape',windowsVirtualKeyCode=27))
assert baseline==ev('JSON.stringify(embroideryStudio.snapshot())')
call('Emulation.setEmulatedMedia',dict(features=[dict(name='prefers-reduced-motion',value='reduce')]))
call('Emulation.setDeviceMetricsOverride',dict(width=390,height=844,deviceScaleFactor=1,mobile=False))
ev("embroideryWorkspace.showTopic('selection')")
time.sleep(.3)
assert ev("document.documentElement.scrollWidth<=innerWidth"), 'No horizontal document overflow'
Path('outputs/workspace-narrow.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',dict(format='png',captureBeyondViewport=True))['result']['data']))
print('PASS: eight topics preserve values; icons; area draft/cancel/apply/Undo; canceled brush rollback; keyboard; native select; 390px reflow; reduced motion.')
print(json.dumps(ev("({scrollbar:getComputedStyle(document.documentElement).scrollbarColor,visibleSections:document.querySelectorAll('.topic-panel:not([hidden]) > details[open]').length})")))
