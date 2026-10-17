"""Real app colour removal workflow on an owned copy, never edit the source design."""
import base64
import json
from pathlib import Path
import requests
from browser_helpers import call,ev,wait

ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'outputs/colour-knockout';out.mkdir(exist_ok=True)
source=ROOT/'work/uploads/e2742318856746e2b8a749b2dcecdf15.webp'
with source.open('rb') as stream:
    response=requests.post('http://127.0.0.1:5050/upload',files={'image':('knockout-browser-check.webp',stream)},allow_redirects=False,timeout=60)
assert response.status_code==302,response.text
name=response.headers['Location'].split('/')[-1]
url='http://127.0.0.1:5050/artwork/'+name
(out/'browser-fixture.json').write_text(json.dumps({'name':name,'url':url,'owned_test_copy':True},indent=2))

def click(id):ev(f"document.getElementById('{id}').click()")
def ready():wait("!embroideryStudio.isBusy() && document.getElementById('status').textContent.startsWith('Preview ready')")
def proposal():wait("!embroideryAssistance.isBusy() && !document.getElementById('knockoutApply').disabled && !document.getElementById('knockoutDraftActions').hidden")
def key(name,code=None,text=None):
    args=dict(type='keyDown',key=name,code=code or name)
    if text:args['text']=text
    call('Input.dispatchKeyEvent',args);call('Input.dispatchKeyEvent',dict(type='keyUp',key=name,code=code or name))
def screenshot(name):
    (out/name).write_bytes(base64.b64decode(call('Page.captureScreenshot',dict(format='png',captureBeyondViewport=True))['result']['data']))

call('Emulation.setDeviceMetricsOverride',dict(width=1440,height=1000,deviceScaleFactor=1,mobile=False))
old=ev('performance.timeOrigin');call('Page.navigate',dict(url=url));wait(f'performance.timeOrigin!=={old}')
wait('!!window.colourKnockout');ready();proposal()
baseline=ev('JSON.stringify(embroideryStudio.snapshot())')
assert not ev('embroideryStudio.snapshot().colour_knockouts?.length')
assert ev("document.getElementById('knockoutMeasurements').textContent.includes('0.0000 mm²')")
assert ev("document.querySelectorAll('#knockoutParts input').length===7 && document.querySelectorAll('#knockoutParts input:checked').length===0")
assert ev("document.getElementById('knockoutBrushReport').textContent.startsWith('Filled 2 ')")
assert ev("!document.getElementById('knockoutWipeBar').hidden")
ev("document.getElementById('knockoutWipe').focus()")
v=ev("Number(document.getElementById('knockoutWipe').value)");key('ArrowRight')
assert ev("Number(document.getElementById('knockoutWipe').value)")>v
screenshot('browser-proposal.png');click('knockoutCancel')
assert baseline==ev('JSON.stringify(embroideryStudio.snapshot())')

# Exercise pointer colour picking on the ORIGINAL, not flattened prepared colours.
ev("document.querySelector('[data-tool=colour-remove]').click()")
p=ev("(()=>{const c=document.getElementById('original'),r=c.getBoundingClientRect(),s=Math.min(c.width/612,c.height/408)*.92;return {x:r.left+(c.width-612*s)/2+10*s,y:r.top+(c.height-408*s)/2+10*s}})()")
for event,buttons in [('mousePressed',1),('mouseReleased',0)]:call('Input.dispatchMouseEvent',dict(type=event,button='left',buttons=buttons,clickCount=1,**p))
proposal()
ev("document.getElementById('knockoutScope').focus()")
key('ArrowDown');key('Enter',text='\r');proposal()
assert ev("document.getElementById('knockoutScope').value==='this area'")
assert not ev("document.getElementById('knockoutMeasurements').textContent.includes('0.0000 mm²')")
ev("document.getElementById('knockoutScope').focus()")
key('ArrowUp');key('Enter',text='\r');proposal()
assert ev("document.getElementById('knockoutMeasurements').textContent.includes('0.0000 mm²')")
click('knockoutCancel')

# Same deterministic command flow in the existing assistant; no provider needed.
ev("embroideryWorkspace.showTopic('details');document.getElementById('assistText').closest('details').open=true;document.getElementById('assistText').value='remove the white'")
click('assistEdit');proposal();click('knockoutApply');ready()
assert ev('embroideryStudio.snapshot().colour_knockouts.length===1')
click('knockoutUndoCleanup');ready()
assert ev('embroideryStudio.snapshot().colour_knockouts[0].cleanup===false')
assert ev("document.getElementById('knockoutBrushReport').textContent.startsWith('Filled 0 ')")
click('undo');ready()
assert ev('embroideryStudio.snapshot().colour_knockouts[0].cleanup===true')

# One click restores a deliberately retained white detail, one click removes it.
ev("document.querySelector('#knockoutParts input').click()");ready()
assert ev('embroideryStudio.snapshot().colour_knockouts[0].restore_parts.length===1')
assert not ev("document.getElementById('knockoutMeasurements').textContent.includes('0.0000 mm²')")
ev("document.querySelector('#knockoutParts input').click()");ready()
assert ev('embroideryStudio.snapshot().colour_knockouts[0].restore_parts.length===0')

# Explicit failure and retry: old preview must never re-enable Apply.
ev("window.knockoutFetch=window.fetch;window.fetch=(url,args)=>url.startsWith('/assist/')?Promise.resolve(new Response(JSON.stringify({error:'Controlled test failure'}),{status:503,headers:{'Content-Type':'application/json'}})):knockoutFetch(url,args)")
click('knockoutPreview');wait("!embroideryAssistance.isBusy() && document.getElementById('knockoutStatus').textContent.includes('Controlled test failure')")
assert ev("document.getElementById('knockoutApply').disabled")
ev('window.fetch=window.knockoutFetch');click('knockoutPreview');proposal();click('knockoutCancel')

# Delayed stale request is discarded after a design edit.
ev("window.fetch=(url,args)=>url.startsWith('/assist/')?knockoutFetch(url,args).then(r=>new Promise(resolve=>setTimeout(()=>resolve(r),1200))):knockoutFetch(url,args)")
click('knockoutPreview');wait('embroideryAssistance.isBusy()')
ev('embroideryStudio.apply({height_mm:101})');ready();wait('!embroideryAssistance.isBusy()')
assert ev("document.getElementById('knockoutDraftActions').hidden")
ev('window.fetch=window.knockoutFetch');click('undo');ready()

# Save and reload only this owned test upload.
click('save');wait("!embroideryStudio.isBusy() && document.getElementById('status').textContent.includes('artwork saved')")
saved=ev('JSON.stringify(embroideryStudio.snapshot())')
old=ev('performance.timeOrigin');call('Page.reload',{});wait(f'performance.timeOrigin!=={old}');wait('!!window.colourKnockout');ready()
wait('!embroideryAssistance.isBusy()')
assert saved==ev('JSON.stringify(embroideryStudio.snapshot())')
screenshot('browser-applied.png')
call('Emulation.setEmulatedMedia',dict(features=[dict(name='prefers-reduced-motion',value='reduce')]))
call('Emulation.setDeviceMetricsOverride',dict(width=390,height=844,deviceScaleFactor=1,mobile=False))
ev("embroideryWorkspace.showTopic('selection');document.getElementById('knockoutControls').scrollIntoView()")
assert ev('document.documentElement.scrollWidth<=innerWidth')
assert ev("[...document.querySelectorAll('#knockoutControls input,#knockoutControls select')].every(e=>e.closest('label'))")
screenshot('browser-narrow.png')
print('PASS: auto proposal, seven recoverable parts, two specks, zero white, cancel, keyboard wipe/scope, pointer colour sampling, assistant command, Apply, cleanup-only Undo, one-click recovery, failure/retry, stale response, save/reload, 390px reflow, reduced motion.')
print(url)
