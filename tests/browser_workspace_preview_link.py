"""Old prepared links must open the modern workspace without regenerating paths."""
import base64
import json
from pathlib import Path
from browser_helpers import call,ev,wait

root=Path(__file__).resolve().parents[1];out=root/'outputs/colour-knockout'
record=json.loads((out/'browser-playback.json').read_text())
call('Emulation.setDeviceMetricsOverride',dict(width=1440,height=1000,deviceScaleFactor=1,mobile=False))
old=ev('performance.timeOrigin')
call('Page.navigate',dict(url='http://127.0.0.1:5050/engine/'+record['prepared']+'?view=1'))
wait(f'performance.timeOrigin!=={old}')
wait("!!window.embroideryStudio && !embroideryStudio.isBusy() && embroideryStudio.hasPlayback()")
assert ev("location.pathname.startsWith('/artwork/') && new URLSearchParams(location.search).get('view')==='stitched'")
assert ev("document.querySelector('[data-view=stitched]').getAttribute('aria-pressed')==='true'")
assert ev("document.querySelectorAll('.topic-nav button').length===7 && document.querySelectorAll('.tools button .ui-icon').length>0")
assert ev("document.getElementById('stitchLink').textContent==='View stitches' && document.getElementById('stitchLink').getAttribute('href').startsWith('/artwork/')")
saved=ev('JSON.stringify(embroideryStudio.snapshot())');origin=ev('performance.timeOrigin')
ev("document.querySelector('[data-view=original]').click();document.getElementById('stitchLink').focus()")
call('Input.dispatchKeyEvent',dict(type='keyDown',key='Enter',code='Enter',text='\r',windowsVirtualKeyCode=13))
call('Input.dispatchKeyEvent',dict(type='keyUp',key='Enter',code='Enter',windowsVirtualKeyCode=13))
assert ev('performance.timeOrigin')==origin, 'View stitches stays in the current editor'
assert saved==ev('JSON.stringify(embroideryStudio.snapshot())')
assert ev("document.querySelector('[data-view=stitched]').getAttribute('aria-pressed')==='true'")
ev("document.getElementById('rewind').click();document.getElementById('run').click()")
wait("Number(document.getElementById('timeline').value)>0")
ev("document.getElementById('run').click();document.getElementById('finish').click()")
(out/'modern-workspace-preview.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',dict(format='png'))['result']['data']))
call('Emulation.setDeviceMetricsOverride',dict(width=390,height=844,deviceScaleFactor=1,mobile=False))
assert ev('document.documentElement.scrollWidth<=innerWidth')
print('PASS: old preview redirects to modern workspace; Stitches selected; keyboard View stitches stays in place; settings unchanged; Play advances; 390px reflow.')
