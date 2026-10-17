"""Actual isolated generation plus explicit browser response doubles for races/errors."""
import base64
import json
import logging
from pathlib import Path
import socket
import subprocess
import threading
import time
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw
from werkzeug.serving import make_server
from embroiderly.web import create_app


def main():
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1', 9229)) != 0
    evidence = Path('.simple-ui-evidence').resolve()
    evidence.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix='.result-browser-', dir='.') as temporary:
        root = Path(temporary).resolve()
        app = create_app(root)
        picture = Image.new('RGBA', (100, 100), (0, 0, 0, 0))
        ImageDraw.Draw(picture).rectangle((20, 20, 80, 80), fill='black')
        picture.save(root/'work/uploads/result.png')
        picture.putpixel((5, 5), (0, 0, 0, 255))
        picture.save(root/'work/uploads/blocked.png')
        options = dict(count=2, smooth=0, floor_mm2=0, mask_holes_mm2=0,
                       protect_selection=True, height_mm=20)
        (root/'work/decisions/result.png.preparation.json').write_text(json.dumps(options))
        (root/'work/decisions/blocked.png.preparation.json').write_text(json.dumps(options))
        server = make_server('127.0.0.1', 0, app, threaded=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        browser = subprocess.Popen(['chromium', '--headless', '--no-sandbox', '--disable-gpu',
            '--remote-debugging-port=9229', '--remote-allow-origins=*',
            '--user-data-dir='+str(root/'browser'), 'about:blank'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            time.sleep(2)
            from browser_helpers import call, ev, wait, ws
            url = f'http://127.0.0.1:{server.server_port}/artwork/result.png'
            def shot(name):
                (evidence/('result-'+name+'.png')).write_bytes(base64.b64decode(
                    call('Page.captureScreenshot', {'format':'png'})['result']['data']))
            def ready():
                wait("!!window.DesignWorkflow && !embroideryStudio.isBusy()")
                wait("document.getElementById('status').textContent.includes('Preview ready')")
            call('Emulation.setDeviceMetricsOverride', dict(width=1366, height=768, deviceScaleFactor=1, mobile=False))
            call('Page.navigate', dict(url=url+'?view=stitched'))
            ready()
            ev("document.documentElement.dataset.theme='light'")
            assert ev("workflowResult.dataset.state") == 'empty'
            shot('empty')
            # Real generation through the app, not a fabricated stitch plan.
            ev("confirmed.checked=true;confirmed.dispatchEvent(new Event('change'));stitch.click()")
            wait("!embroideryStudio.isBusy() && embroideryStudio.hasPlayback()", timeout=90)
            counts = ev("({stitches:preparationConfig.previous?.stitch_count,summary:stitchStatus.textContent})")
            shot('generated')
            ev("document.querySelector('[data-view=compare]').focus()")
            call('Input.dispatchKeyEvent', dict(type='keyDown', key='Enter', code='Enter', text='\r', windowsVirtualKeyCode=13))
            call('Input.dispatchKeyEvent', dict(type='keyUp', key='Enter', code='Enter', windowsVirtualKeyCode=13))
            assert ev("document.getElementById('stitched').parentElement.style.display") == 'block', 'Compare hides actual stitches'
            assert ev("document.getElementById('prepared').parentElement.style.display") == 'none'
            assert ev("document.getElementById('original').parentElement.style.display") == 'block'
            shot('compare')
            ev("finish.click()")
            assert ev("Number(timeline.value)===Number(timeline.max)")
            ev("run.click()")
            wait("Number(timeline.value)>0 && Number(timeline.value)<Number(timeline.max)")
            ev("finish.click()")
            assert ev("Number(timeline.value)===Number(timeline.max)")
            # Saved plan without special query opens its finished result.
            call('Page.navigate', dict(url=url))
            ready()
            assert ev("document.body.dataset.workflow") == 'check'
            assert ev("document.getElementById('stitched').parentElement.style.display") == 'block'
            assert ev("document.getElementById('workflowResult').dataset.state") == 'ready'
            assert ev("!embroideryAssistance.isBusy()")
            shot('saved')
            # Ordinary editing compare remains original vs prepared.
            ev("DesignWorkflow.show('edit');document.querySelector('[data-view=compare]').click()")
            assert ev("document.getElementById('prepared').parentElement.style.display") == 'block'
            ev("embroideryStudio.apply({height_mm:20.5})")
            wait("!embroideryStudio.isBusy() && !embroideryStudio.hasPlayback()")
            # Delayed automatic suggestion, same options: cannot steal finished canvas.
            ev("""window.originalFetch=fetch;window.releaseSuggestion=null;
                window.fetch=(u,a)=>String(u).startsWith('/assist/')?new Promise(resolve=>{
                  window.releaseSuggestion=()=>resolve(new Response(JSON.stringify({
                    operation:'colour-knockout',image:preparationConfig.original,
                    before_image:preparationConfig.original,patch:{},method:'Race test double'
                  }),{status:200,headers:{'Content-Type':'application/json'}}))
                }):originalFetch(u,a);
                embroideryAssistance.request({action:'recommend'},true);""")
            wait("!!window.releaseSuggestion")
            ev("confirmed.checked=true;confirmed.dispatchEvent(new Event('change'));stitch.click()")
            assert ev("workflowResult.dataset.state") == 'generating'
            shot('generating')
            ev("releaseSuggestion()")
            wait("!embroideryStudio.isBusy() && embroideryStudio.hasPlayback()", timeout=90)
            wait("!embroideryAssistance.isBusy()")
            assert ev("document.body.dataset.workflow") == 'check'
            assert ev("document.getElementById('stitched').parentElement.style.display") == 'block'
            # Failed generation / retry, using an explicit HTTP failure double.
            ev("""window.fetch=(u,a)=>String(u).startsWith('/artwork/')&&a?.method==='POST'
                  ?Promise.resolve(new Response(JSON.stringify({error:'A detail has no stitchable outline. Review it before generating.'}),{status:400}))
                  :originalFetch(u,a);
                embroideryStudio.apply({height_mm:21});""")
            wait("!embroideryStudio.isBusy() && document.getElementById('status').textContent.startsWith('Could not prepare')")
            assert ev("!embroideryStudio.hasPlayback() && run.disabled")
            assert ev("document.getElementById('workflowResult').dataset.state") == 'error'
            assert ev("document.getElementById('workflowResult').textContent.includes('no stitchable outline')")
            shot('error')
            ev("window.fetch=originalFetch;confirmed.checked=true;confirmed.dispatchEvent(new Event('change'));stitch.click()")
            wait("!embroideryStudio.isBusy() && embroideryStudio.hasPlayback()", timeout=90)
            assert ev("document.getElementById('workflowResult').dataset.state") == 'ready'
            # No current plan / blocked regions are never labelled completed.
            ev("window.fetch=originalFetch")
            call('Page.navigate', dict(url=url.replace('result.png','blocked.png')+'?view=stitched'))
            ready()
            wait("!embroideryStudio.isBusy() && document.getElementById('workflowResult').dataset.state==='blocked'")
            assert ev("!embroideryStudio.hasPlayback() && run.disabled")
            shot('blocked')
            call('Emulation.setDeviceMetricsOverride', dict(width=390, height=844, deviceScaleFactor=1, mobile=True))
            call('Emulation.setEmulatedMedia', {'features':[{'name':'prefers-reduced-motion','value':'reduce'}]})
            ev("document.documentElement.dataset.theme='dark';workflowResult.scrollIntoView({block:'center'})")
            time.sleep(.2)
            assert ev("document.documentElement.scrollWidth<=innerWidth")
            assert ev("workflowResult.checkVisibility()")
            shot('narrow-dark')
            print(json.dumps(dict(status='passed',actual_generation=counts,paid_calls=0,
                doubles=['late suggestion','failed preparation'],real_blocker=True)))
            ws.close()
        finally:
            browser.terminate()
            browser.wait(timeout=10)
            server.shutdown()


if __name__ == '__main__':
    main()
