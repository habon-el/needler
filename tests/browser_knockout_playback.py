"""Generate and play the real machine commands on the owned browser test copy."""
import base64
import json
from pathlib import Path
import numpy as np
from PIL import Image
import pyembroidery as emb
from embroiderly.knockout_routing import verify
from browser_helpers import call,ev,wait

root=Path(__file__).resolve().parents[1];out=root/'outputs/colour-knockout'
fixture=json.loads((out/'browser-fixture.json').read_text())
call('Emulation.setDeviceMetricsOverride',dict(width=1440,height=1000,deviceScaleFactor=1,mobile=False))
old=ev('performance.timeOrigin');call('Page.navigate',dict(url=fixture['url']));wait(f'performance.timeOrigin!=={old}')
wait("!!window.colourKnockout && !embroideryStudio.isBusy() && document.getElementById('status').textContent.startsWith('Preview ready')")
wait('!embroideryAssistance.isBusy()')
assert ev("document.querySelector('[data-option=floor_mm2]').disabled && document.getElementById('unprotectSubject').disabled")
ev("window.beforeGenerationFetch=window.fetch;window.fetch=async (...args)=>{const r=await beforeGenerationFetch(...args);if(args[0].startsWith('/artwork/')&&JSON.parse(args[1].body).digitize)window.knockoutGenerated=await r.clone().json();return r}")
ev("document.getElementById('confirmed').checked=true;document.getElementById('confirmed').onchange();document.getElementById('stitch').click()")
wait('!!window.knockoutGenerated',timeout=240)
result=ev('window.knockoutGenerated');assert not result.get('error'),result
wait('!embroideryStudio.isBusy() && embroideryStudio.hasPlayback()')
assert ev("!document.getElementById('run').disabled && document.getElementById('stitchEmpty').hidden")
ev("document.getElementById('rewind').click();document.getElementById('run').click()")
wait("Number(document.getElementById('timeline').value)>0")
ev("document.getElementById('run').click();document.getElementById('finish').click()")
assert ev("(()=>{const c=document.getElementById('stitched'),p=c.getContext('2d').getImageData(0,0,c.width,c.height).data;const colours=new Set();for(let i=0;i<p.length;i+=400)colours.add(p[i]+','+p[i+1]+','+p[i+2]);return colours.size>5})()")
source=root/'work/uploads'/result['prepared_name'];image=Image.open(source);mask=np.asarray(image)[:,:,3]>127
folder=root/'work/inkstitch-preview'/source.stem;plan=result['playback']
for format in ['pes','dst']:verify(emb.EmbPattern(str(folder/('design.'+format))),mask,plan['height_mm']/image.height,plan['origin_mm'])
assert result['report']['colour_knockouts'][0]['remaining_colour_area_mm2']==0
assert len(plan['colors'])==1
(out/'browser-stitches.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',dict(format='png'))['result']['data']))
evidence={k:plan[k] for k in ['stitch_count','trim_count','colors','colour_knockout_routing']}
evidence.update(url=fixture['url'],prepared=result['prepared_name'],playback_advances=True,canvas_nonblank=True)
(out/'browser-playback.json').write_text(json.dumps(evidence,indent=2)+'\n')
print('PASS: generated in the app, nonblank coloured stitches, Play advances, PES and DST have no exposed crossings beyond one-pixel raster boundary tolerance.')
print(json.dumps(evidence,indent=2))
