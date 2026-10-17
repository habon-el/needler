"""Width/height adapter and a real, read-only embroidery-font width check."""
if __name__ == '__main__':
    from browser_workspace_isolated import main
    main(('browser_size_lettering.py',))
    raise SystemExit

import base64
import json
from pathlib import Path
from browser_helpers import call, ev, wait

call('Emulation.setDeviceMetricsOverride',dict(width=1440,height=1000,deviceScaleFactor=1,mobile=False))
call('Page.navigate',dict(url=WORKSPACE_URL))
wait("!!window.embroideryStudio && !embroideryStudio.isBusy() && document.getElementById('status').textContent.startsWith('Preview ready')")
ev("document.querySelector('[data-topic=size]').click()")
before=ev('JSON.stringify(embroideryStudio.snapshot())')
ev("document.getElementById('canvasWidth').value='50';document.getElementById('canvasWidth').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}))")
wait('!embroideryStudio.isBusy() && document.getElementById("status").textContent.startsWith("Preview ready")')
assert abs(ev('embroideryStudio.snapshot().height_mm')-50/1.2)<1e-7
assert ev("document.getElementById('canvasWidth').value")=='50.0'
assert ev("document.getElementById('canvasHeight').value")=='41.7'
assert ev("document.getElementById('exportDst').hidden")
ev("document.getElementById('canvasWidth').value='bad';document.getElementById('canvasWidth').dispatchEvent(new Event('change',{bubbles:true}))")
assert ev("document.getElementById('canvasWidth').getAttribute('aria-invalid')")=='true'
assert abs(ev('embroideryStudio.snapshot().height_mm')-50/1.2)<1e-7
ev("document.getElementById('canvasWidth').value='75';document.getElementById('canvasWidth').dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));document.getElementById('undo').click()")
wait('!embroideryStudio.isBusy() && document.getElementById("status").textContent.startsWith("Preview ready")')
assert ev('JSON.stringify(embroideryStudio.snapshot())')==before
assert ev("document.getElementById('canvasWidth').value")=='120.0'
ev("document.getElementById('canvasHeight').value='50';document.getElementById('canvasHeight').dispatchEvent(new Event('change',{bubbles:true}))")
wait('!embroideryStudio.isBusy() && document.getElementById("status").textContent.startsWith("Preview ready")')
assert ev("document.getElementById('canvasWidth').value")=='60.0'
print('PASS: width 50 → height 41.7; height 50 → width 60; invalid/Escape preserve state; Undo restores size; stale exports hidden.')

ev("document.getElementById('textTool').click()")
wait("document.getElementById('letteringStatus').textContent.startsWith('Preview ready')")
ev("document.getElementById('letteringWords').value='Hello World';document.getElementById('letteringWords').dispatchEvent(new Event('input',{bubbles:true}));document.getElementById('nativeWidth').value='50';document.getElementById('nativeCheck').click()")
assert ev("document.getElementById('nativeCheck').disabled")
wait("!document.getElementById('nativeCheck').disabled",timeout=260)
result=ev("document.getElementById('nativeResult').textContent")
assert 'DST: 0 short, 0 long, 0 crossings' in result,result
assert 'PES: 0 short, 0 long, 0 crossings' in result,result
assert ev("document.getElementById('nativeFit').textContent.startsWith('Width fits:')")
ev("document.getElementById('nativeFit').scrollIntoView({block:'center'})")
Path('outputs/lettering-width-trial.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',dict(format='png'))['result']['data']))
print('PASS: real 50 mm space native check:',result)
call('Emulation.setDeviceMetricsOverride',dict(width=390,height=844,deviceScaleFactor=1,mobile=False))
assert ev("document.getElementById('letteringDialog').scrollWidth<=document.getElementById('letteringDialog').clientWidth+1")
ev("document.getElementById('nativeWidth').value='20';document.getElementById('nativeWidth').dispatchEvent(new Event('input',{bubbles:true}))")
assert ev("document.getElementById('nativePreview').hidden && document.getElementById('nativeFit').textContent.startsWith('Width not checked')")
ev("document.getElementById('letteringDialog').close()")
wait("document.activeElement.id==='textTool'")
print('PASS: width edit invalidates native check; 390px reflow; dialog focus restored. No customer design modified.')
