"""Real generation + synthetic AI: opt-in, dedup, review actions and stale replies."""
import base64
import json
import logging
from pathlib import Path
import socket
import subprocess
import threading
import time
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image, ImageDraw
from werkzeug.serving import make_server
from embroiderly.web import create_app
from embroiderly.ai_workflow import MODEL


def main():
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1', 9229)) != 0
    evidence = Path('.simple-ui-evidence').resolve(); evidence.mkdir(exist_ok=True)
    calls = []
    class Fake:
        def __init__(self,*a): pass
        def request(self,payload):
            calls.append(payload)
            value = dict(summary='Synthetic test review: compare the shape before applying any changes.', details=[
                dict(label='Shape edge', note='Synthetic finding: inspect this edge.', bounds=[150,150,350,350], certainty='possible')])
            return dict(model=MODEL, status='completed', usage=dict(input_tokens=100,output_tokens=40),
                        output=[dict(content=[dict(type='output_text',text=json.dumps(value))])])
    with TemporaryDirectory(prefix='.ai-browser-', dir='.') as temporary, \
            patch('embroiderly.ai_workflow.BudgetedProvider', Fake), \
            patch('embroiderly.ai_workflow.readiness', return_value=(True, 'Synthetic test provider')):
        root = Path(temporary).resolve(); app = create_app(root)
        picture = Image.new('RGBA',(100,100),(0,0,0,0))
        ImageDraw.Draw(picture).rectangle((20,20,80,80), fill='black')
        picture.save(root/'work/uploads/test.png')
        options=dict(count=2,smooth=0,floor_mm2=0,mask_holes_mm2=0,protect_selection=True,height_mm=20)
        (root/'work/decisions/test.png.preparation.json').write_text(json.dumps(options))
        server=make_server('127.0.0.1',0,app,threaded=True)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        browser=subprocess.Popen(['chromium','--headless','--no-sandbox','--disable-gpu',
            '--remote-debugging-port=9229','--remote-allow-origins=*','--user-data-dir='+str(root/'browser'),'about:blank'],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            time.sleep(2)
            from browser_helpers import call, ev, wait, ws
            url=f'http://127.0.0.1:{server.server_port}/artwork/test.png'
            def shot(name):
                (evidence/('ai-'+name+'.png')).write_bytes(base64.b64decode(call('Page.captureScreenshot',{'format':'png'})['result']['data']))
            def ready(): wait("!!window.DesignWorkflow && !!document.getElementById('autoAiReview') && !embroideryStudio.isBusy()")
            call('Emulation.setDeviceMetricsOverride', dict(width=1366,height=768,deviceScaleFactor=1,mobile=False))
            call('Page.navigate',dict(url=url)); ready()
            time.sleep(.3)
            ev("document.documentElement.dataset.theme='light'")
            assert len(calls)==0, 'Opening the app must not grant sharing permission'
            ev("aiWorkflow.scrollIntoView({block:'center'})"); shot('off')
            baseline=ev('JSON.stringify(embroideryStudio.snapshot())')
            ev('autoAiReview.focus()')
            call('Input.dispatchKeyEvent',dict(type='keyDown',key=' ',code='Space',windowsVirtualKeyCode=32))
            call('Input.dispatchKeyEvent',dict(type='keyUp',key=' ',code='Space',windowsVirtualKeyCode=32))
            wait("!!document.querySelector('.ai-review-card[data-stage=upload]')")
            assert len(calls)==1
            ev("autoAiDetails.open=true;document.querySelector('.ai-review-card').open=true;aiWorkflow.scrollIntoView({block:'center'})")
            shot('upload')
            assert ev('JSON.stringify(embroideryStudio.snapshot())')==baseline
            ev("Array.from(document.querySelectorAll('.ai-detail-actions button')).find(b=>b.textContent==='Keep').click()")
            assert ev('askAiQuestion.value.startsWith("Keep this detail")')
            assert ev('!askAiConsent.checked')
            # Never overwrite a prompt the user is composing, nor apply any image edits.
            ev("askAiQuestion.value='My own draft';Array.from(document.querySelectorAll('.ai-detail-actions button')).find(b=>b.textContent==='Remove').click()")
            assert ev('askAiQuestion.value')=='My own draft'
            assert ev('JSON.stringify(embroideryStudio.snapshot())')==baseline
            ev("askAiQuestion.value='';Array.from(document.querySelectorAll('.ai-detail-actions button')).find(b=>b.textContent==='Fix manually').click()")
            assert ev("document.getElementById('tool').value")=='polygon'
            ev("embroideryStudio.selectTool('pan');confirmed.checked=true;confirmed.dispatchEvent(new Event('change'));stitch.click()")
            wait('!embroideryStudio.isBusy() && embroideryStudio.hasPlayback()',timeout=90)
            wait("!!document.querySelector('.ai-review-card[data-stage=finished]')")
            assert len(calls)==2
            assert ev("document.body.dataset.workflow")=='check'
            assert ev('!document.querySelector("#autoLocalCheck button").disabled')
            assert ev("document.getElementById('stitched').parentElement.style.display")=='block'
            ev("finish.click();run.click()")
            wait('Number(timeline.value)>0 && Number(timeline.value)<Number(timeline.max)')
            ev("autoAiDetails.open=false")
            ev('finish.click();aiWorkflow.scrollIntoView({block:"center"})'); shot('finished')
            # Reload restores both reviews from server receipts with zero paid repeats.
            call('Page.navigate',dict(url=url)); ready()
            wait("!!document.querySelector('.ai-review-card[data-stage=finished]')")
            assert len(calls)==2
            assert ev("document.querySelector('[data-stage=finished]').textContent.includes('saved review')")
            # Undo restores the saved comparison without paying a second time.
            ev("embroideryStudio.apply({height_mm:20.1})")
            wait('!embroideryStudio.isBusy()')
            ev('document.getElementById("undo").click()')
            wait("!embroideryStudio.isBusy() && !!document.querySelector('[data-stage=finished]')")
            assert len(calls)==2
            # Delay a final response, then edit: obsolete findings must not reappear.
            ev("""window.realFetch=fetch;window.releaseReview=null;
              window.fetch=(u,a)=>String(u).startsWith('/ai-workflow/')&&a?.method==='POST'&&JSON.parse(a.body).stage==='finished'
                ?new Promise(resolve=>{window.releaseReview=()=>resolve(new Response(JSON.stringify({state:'completed',stage:'finished',model:'Test double',summary:'STALE FINDING',details:[]})))})
                :realFetch(u,a);
              embroideryStudio.apply({height_mm:21});""")
            wait('!embroideryStudio.isBusy()')
            ev("confirmed.checked=true;confirmed.dispatchEvent(new Event('change'));stitch.click()")
            wait('!embroideryStudio.isBusy() && embroideryStudio.hasPlayback()',timeout=90)
            wait('!!window.releaseReview')
            ev('embroideryStudio.apply({height_mm:22});releaseReview()')
            wait('!embroideryStudio.isBusy()')
            assert not ev("autoAiResults.textContent.includes('STALE FINDING')")
            assert not ev("!!document.querySelector('[data-stage=finished]')")
            # Failure is recoverable, and opt-out never starts another request.
            ev("""window.fetch=(u,a)=>String(u).startsWith('/ai-workflow/')&&a?.method==='POST'
              ?Promise.resolve(new Response(JSON.stringify({error:'Synthetic budget limit. No call sent.'}),{status:400}))
              :realFetch(u,a);
              autoAiReview.click();autoAiReview.click();""")
            wait("!autoAiRetry.hidden && autoAiStatus.textContent.includes('budget limit')")
            ev('aiWorkflow.scrollIntoView({block:"center"})'); shot('budget-error')
            ev('autoAiReview.click();window.fetch=realFetch')
            before=len(calls)
            ev("embroideryStudio.apply({height_mm:23})")
            wait('!embroideryStudio.isBusy()')
            assert len(calls)==before
            call('Emulation.setDeviceMetricsOverride',dict(width=390,height=844,deviceScaleFactor=1,mobile=True))
            call('Emulation.setEmulatedMedia',{'features':[{'name':'prefers-reduced-motion','value':'reduce'}]})
            ev("document.documentElement.dataset.theme='dark';aiWorkflow.scrollIntoView({block:'center'})")
            time.sleep(.2)
            assert ev('document.documentElement.scrollWidth<=innerWidth')
            ratio=ev("""(()=>{const s=getComputedStyle(autoAiStatus),b=getComputedStyle(aiWorkflow);
              const l=c=>{const v=c.match(/[0-9.]+/g).slice(0,3).map(x=>{x=Number(x)/255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4});
                return .2126*v[0]+.7152*v[1]+.0722*v[2]};
              return (Math.max(l(s.color),l(b.backgroundColor))+.05)/(Math.min(l(s.color),l(b.backgroundColor))+.05)})()""")
            assert ratio>=4.5,ratio
            shot('narrow-dark')
            print(json.dumps(dict(status='passed',paid_calls=0,synthetic_review_calls=len(calls),real_generation=True,
                checks=['opt-in','refresh dedup','prompt ownership','manual tools','playback','stale review','budget error','opt-out','keyboard','narrow dark'])))
            ws.close()
        finally:
            browser.terminate(); browser.wait(timeout=10); server.shutdown()


if __name__=='__main__': main()
