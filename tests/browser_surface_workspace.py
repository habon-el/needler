"""Exercise the real workspace on our own uploaded 'hello' sample, never a user's design."""
import base64
import json
from pathlib import Path
import requests
from browser_helpers import call,ev,wait

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/thread-surface'
OUT.mkdir(exist_ok=True);record=OUT/'workspace-fixture.json'
if record.exists():
    name=json.loads(record.read_text())['name']
    if requests.get('http://127.0.0.1:5050/artwork/'+name,timeout=15).status_code!=200:name=None
else:name=None
if not name:
    with (ROOT/'src/embroiderly/static/landing/hello.png').open('rb') as image:
        response=requests.post('http://127.0.0.1:5050/upload',files={'image':('Thread realism - hello.png',image,'image/png')},allow_redirects=False,timeout=30)
    assert response.status_code==302,response.text
    name=response.headers['Location'].rsplit('/',1)[-1]
    record.write_text(json.dumps({'name':name})+'\n')
call('Page.bringToFront',{});call('Emulation.setFocusEmulationEnabled',{'enabled':True})
call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False})
old=ev('performance.timeOrigin');call('Page.navigate',{'url':'http://127.0.0.1:5050/artwork/'+name})
wait(f'performance.timeOrigin !== {old}')
wait('!!window.embroideryStudio && !embroideryStudio.isBusy()')
if ev('document.querySelector("#run").disabled'):
    ev('embroideryStudio.apply({height_mm:40,count:2,smooth:0,simplify:0,floor_mm2:.1,mask_holes_mm2:0})')
    wait('!embroideryStudio.isBusy() && !document.querySelector("#save").disabled')
    ev('document.querySelector("#confirmed").checked=true;document.querySelector("#confirmed").dispatchEvent(new Event("change"));document.querySelector("#stitch").click()')
    wait('!document.querySelector("#run").disabled',timeout=180)
ev('document.querySelector("[data-view=stitched]").click();document.querySelector("#finish").click();document.querySelector("[data-topic=size]").click()')
wait('document.querySelector("#surfaceStatus").textContent.includes("WebGL2")')
before=ev('JSON.stringify(embroideryStudio.snapshot())')
print('Surface',ev('JSON.stringify(embroideryStudio.previewInfo())'))
ev('window.initialSurface=document.querySelector("#stitched").toDataURL();document.querySelector("#lightAngle").value=45;document.querySelector("#lightAngle").dispatchEvent(new Event("input"))')
assert ev('initialSurface!==document.querySelector("#stitched").toDataURL()')
ev('document.querySelector("#threadRelief").click()')
assert ev('document.querySelector("#surfaceStatus").textContent.includes("Plain exported paths")')
ev('document.querySelector("#threadRelief").click();document.querySelector("#fabricTexture").value="knit";document.querySelector("#fabricTexture").dispatchEvent(new Event("input"));document.querySelector("#neutralLight").click()')
assert before==ev('JSON.stringify(embroideryStudio.snapshot())')
ev('document.querySelector("#lightAngle").focus()')
call('Input.dispatchKeyEvent',{'type':'keyDown','key':'ArrowRight','code':'ArrowRight','windowsVirtualKeyCode':39})
call('Input.dispatchKeyEvent',{'type':'keyUp','key':'ArrowRight','code':'ArrowRight','windowsVirtualKeyCode':39})
assert ev('document.querySelector("#lightAngle").value==="46"')
ev('document.querySelector("#fabricTexture").focus()')
call('Input.dispatchKeyEvent',{'type':'keyDown','key':' ','code':'Space','windowsVirtualKeyCode':32,'text':' '})
call('Input.dispatchKeyEvent',{'type':'keyUp','key':' ','code':'Space','windowsVirtualKeyCode':32})
call('Input.dispatchKeyEvent',{'type':'keyDown','key':'Escape','code':'Escape','windowsVirtualKeyCode':27})
call('Input.dispatchKeyEvent',{'type':'keyUp','key':'Escape','code':'Escape','windowsVirtualKeyCode':27})
# Weight profiles are preview-only and restore their own session widths.
ev('document.querySelector("#threadWeight").value=30;document.querySelector("#threadWeight").dispatchEvent(new Event("change"));document.querySelector("#threadVisualWidth").value=.5;document.querySelector("#threadVisualWidth").dispatchEvent(new Event("input"));document.querySelector("#threadWeight").value=40;document.querySelector("#threadWeight").dispatchEvent(new Event("change"))')
assert ev('Number(document.querySelector("#threadVisualWidth").value)===.375')
ev('document.querySelector("#threadWeight").value=30;document.querySelector("#threadWeight").dispatchEvent(new Event("change"))')
assert ev('Number(document.querySelector("#threadVisualWidth").value)===.5')
ev('document.querySelector("#threadWeight").value=0;document.querySelector("#threadWeight").dispatchEvent(new Event("change"))')
assert ev('document.querySelector("#threadWeight").getAttribute("aria-invalid")==="true"')
ev('document.querySelector("#threadWeight").value=40;document.querySelector("#threadWeight").dispatchEvent(new Event("change"));document.querySelector("#dragLight").checked=true')
position=ev('(()=>{const r=document.querySelector("#stitched").getBoundingClientRect();return {x:r.x+r.width*.7,y:r.y+r.height*.5}})()')
call('Input.dispatchMouseEvent',{'type':'mousePressed',**position,'button':'left','buttons':1,'clickCount':1})
call('Input.dispatchMouseEvent',{'type':'mouseReleased',**position,'button':'left','buttons':0,'clickCount':1})
assert ev('Number(document.querySelector("#lightAngle").value)===0')
ev('document.querySelector("#dragLight").checked=false')
assert before==ev('JSON.stringify(embroideryStudio.snapshot())')
# Mockup error, duplicate guard, recovery, and a real exported-file PNG download.
call('Browser.setDownloadBehavior',{'behavior':'allow','downloadPath':str(OUT.resolve())})
ev('window.realFetch=window.fetch;window.fetch=(...args)=>args[0].startsWith("/thread-mockup/")?new Promise(resolve=>setTimeout(()=>resolve(new Response(JSON.stringify({error:"Injected mockup busy; retry."}),{status:429,headers:{"Content-Type":"application/json"}})),400)):realFetch(...args);document.querySelector("#downloadMockup").click()')
assert ev('document.querySelector("#downloadMockup").disabled')
wait('document.querySelector("#surfaceStatus").textContent.includes("Injected mockup busy")')
assert ev('!document.querySelector("#downloadMockup").disabled')
ev('window.fetch=realFetch;document.querySelector("#downloadMockup").click()')
wait('document.querySelector("#surfaceStatus").textContent.includes("PNG saved")',timeout=60)
assert before==ev('JSON.stringify(embroideryStudio.snapshot())')
# Appearance defaults restored for handoff.
ev('document.querySelector("#neutralLight").checked=false;document.querySelector("#fabricTexture").value="twill";document.querySelector("#lightAngle").value=225;document.querySelector("#lightAngle").dispatchEvent(new Event("input"))')
OUT.joinpath('workspace-realistic.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',{'format':'png'})['result']['data']))
# Fail-closed graphics fallback and recovery, without mutating generation.
ev('window.realSurfacePaint=ThreadSurface.prototype.paint;ThreadSurface.prototype.paint=function(){throw Error("Injected graphics failure")};embroideryStudio.redraw()')
assert ev('document.querySelector("#surfaceStatus").textContent.includes("Line fallback")')
assert ev('!document.querySelector("#retrySurface").hidden && !document.querySelector("#run").disabled')
ev('ThreadSurface.prototype.paint=realSurfacePaint;document.querySelector("#retrySurface").click()')
assert ev('document.querySelector("#surfaceStatus").textContent.includes("WebGL2")')
assert before==ev('JSON.stringify(embroideryStudio.snapshot())')
call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
assert ev('document.documentElement.scrollWidth<=innerWidth')
call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False})
print('PASS: live surface, line toggle, fabric, light keyboard/drag, weight profiles, PNG download/error/retry, native select popup, unchanged options, graphics failure/fallback/retry, 390 px reflow.')
print('Preview URL: http://127.0.0.1:5050/artwork/'+name)
