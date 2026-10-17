"""Isolated queued-generation recovery and real stitch playback acceptance."""
if __name__ == '__main__':
    from browser_workspace_isolated import main
    main()
    raise SystemExit

import base64
import json
from pathlib import Path
from browser_helpers import call, ev, wait

call('Emulation.setDeviceMetricsOverride', dict(width=1440,height=1000,deviceScaleFactor=1,mobile=False))
origin=ev('performance.timeOrigin')
call('Page.navigate',dict(url=WORKSPACE_URL))
wait(f'performance.timeOrigin !== {origin}')
wait("!!window.embroideryWorkspace && !embroideryStudio.isBusy() && document.getElementById('status').textContent.startsWith('Preview ready')")
ev("window.realFetch=window.fetch;window.fetch=(url,args)=>{if(args?.body&&url.startsWith('/artwork/')){const body=JSON.parse(args.body);if(body.digitize)return new Promise(resolve=>setTimeout(()=>resolve(new Response(JSON.stringify({error:'Test timeout. Your source image is unchanged.'}),{status:504,headers:{'Content-Type':'application/json'}})),1200));return realFetch(url,args).then(response=>new Promise(resolve=>setTimeout(()=>resolve(response),1200)))}return realFetch(url,args)};embroideryStudio.apply({height_mm:101})")
wait('embroideryStudio.isBusy()')
snapshot=ev('JSON.stringify(embroideryStudio.snapshot())')
# Queue behind the preview via the existing action handler.
ev("document.getElementById('confirmed').checked=true;document.getElementById('confirmed').onchange();document.getElementById('stitch').onclick()")
assert ev("document.querySelector('[data-view=stitched]').getAttribute('aria-pressed')==='true'")
assert ev("!document.querySelector('[data-topic=colours]').disabled")
ev("document.querySelector('[data-topic=colours]').click()")
assert ev("!document.getElementById('topic-colours').hidden")
wait("!embroideryStudio.isBusy() && document.getElementById('status').textContent.includes('Test timeout')")
assert ev("!document.getElementById('stitchEmpty').hidden && document.getElementById('stitchEmptyMessage').textContent.includes('Test timeout')")
assert snapshot == ev('JSON.stringify(embroideryStudio.snapshot())')
assert ev("!document.getElementById('stitchEmptyGenerate').disabled")
for theme in ('light','dark'):
    ev("document.documentElement.dataset.theme="+json.dumps(theme))
    for selector in ('#stitchEmpty','#stitchEmpty .confirm'):
        ratio=ev("(()=>{const s=getComputedStyle(document.querySelector("+json.dumps(selector)+"));const l=c=>{const v=c.match(/[0-9.]+/g).slice(0,3).map(x=>{x=Number(x)/255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4});return .2126*v[0]+.7152*v[1]+.0722*v[2]};const a=l(s.color),b=l(s.backgroundColor);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05)})()")
        assert ratio>=4.5,(theme,selector,ratio)
Path('outputs/workspace-error-state.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',dict(format='png'))['result']['data']))
print('PASS: generation error and confirmation text meet 4.5:1 contrast in light and dark themes.')
ev('window.fetch=window.realFetch')
print('PASS: queued generation opens Stitches; topic navigation during loading; explicit timeout and retry; options preserved.')

origin=ev('performance.timeOrigin')
call('Page.navigate',dict(url=WORKSPACE_URL))
wait(f'performance.timeOrigin !== {origin}')
wait("!!window.embroideryWorkspace && !embroideryStudio.isBusy() && document.getElementById('status').textContent.startsWith('Preview ready')")
# Generate real stitches only in the disposable test project.
ev("document.getElementById('confirmed').checked=true;document.getElementById('confirmed').onchange();document.getElementById('stitch').onclick()")
wait("!embroideryStudio.isBusy() && embroideryStudio.hasPlayback()", timeout=120)
ev("document.querySelector('[data-view=stitched]').click();document.getElementById('finish').click()")
assert ev("document.getElementById('stitchEmpty').hidden && !document.getElementById('run').disabled")
assert ev("(()=>{const c=document.getElementById('stitched'),d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;const distinct=new Set();for(let i=0;i<d.length;i+=400)distinct.add(d[i]+','+d[i+1]+','+d[i+2]);return distinct.size>5})()")
Path('outputs/workspace-stitches.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',dict(format='png'))['result']['data']))
ev("document.getElementById('rewind').click();document.getElementById('run').click()")
wait("Number(document.getElementById('timeline').value)>0")
ev("document.getElementById('run').click();document.getElementById('finish').click()")
print('PASS: saved colour stitches are visible and machine-command playback advances.')
