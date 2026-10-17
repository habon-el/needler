"""Isolated real-browser regression; never loads or saves a customer design."""
import base64
import json
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from werkzeug.serving import make_server
from embroiderly.web import create_app
from test_cleanup_review import detail


def main():
    with tempfile.TemporaryDirectory(prefix='cleanup-browser-') as directory:
        root=Path(directory);app=create_app(root)
        detail(root/'work/uploads/detail.png')
        server=make_server('127.0.0.1',5063,app,threaded=True)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        browser=subprocess.Popen(['chromium','--headless','--no-sandbox','--disable-gpu','--remote-debugging-port=9229','--remote-allow-origins=*','--user-data-dir='+str(root/'browser'),'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            time.sleep(2)
            from browser_helpers import call,ev,wait
            call('Page.navigate',dict(url='http://127.0.0.1:5063/artwork/detail.png'))
            wait("!!window.embroideryStudio && !embroideryStudio.isBusy() && document.getElementById('status').textContent.startsWith('Preview ready')")
            ev("embroideryStudio.apply({count:2,height_mm:25,floor_mm2:1,smooth:0})")
            wait("!embroideryStudio.isBusy() && document.getElementById('detailFindings').textContent.includes('0.5 × 0.5')")
            assert not ev("document.getElementById('healthSummary').textContent.includes('No tiny-area warnings')")
            assert not ev("document.getElementById('detailStatus').textContent.includes('Nothing was changed automatically')")
            for label,value in [('Keep it','keep'),('Let it go','drop')]:
                ev("[...document.querySelectorAll('#detailFindings button')].find(b=>b.textContent==="+json.dumps(label)+").click()")
                wait("!embroideryStudio.isBusy() && document.getElementById('detailFindings').textContent.includes('Decision: "+value+"')")
                assert value in ev('Object.values(embroideryStudio.snapshot().cleanup_decisions)')
            ev("document.getElementById('undo').click()")
            wait("!embroideryStudio.isBusy() && document.getElementById('detailFindings').textContent.includes('Decision: keep')")
            call('Emulation.setDeviceMetricsOverride',dict(width=390,height=844,deviceScaleFactor=1,mobile=False))
            ev("document.querySelector('[data-topic=details]').click()")
            assert ev('document.documentElement.scrollWidth<=innerWidth')
            Path('/tmp/cleanup-review-browser.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',dict(format='png'))['result']['data']))
            print('PASS: real-size warning; truthful messages; Keep/Let go/Undo; 390px reflow.')
            import io
            from PIL import Image
            from verify_lettering_batch import render,CASES
            from embroiderly.colour_knockout import propose_background
            data,_,_=render(CASES[-1]);image=Image.open(io.BytesIO(data))
            image.save(root/'work/uploads/letters.png')
            call('Page.navigate',dict(url='http://127.0.0.1:5063/artwork/letters.png?view=stitched'))
            wait("!!window.embroideryStudio && !embroideryStudio.isBusy() && document.getElementById('status').textContent.startsWith('Preview ready')")
            options={'height_mm':10,'colour_knockouts':[propose_background(image)]}
            ev('embroideryStudio.apply('+json.dumps(options)+')')
            wait("!embroideryStudio.isBusy() && document.querySelectorAll('#knockoutParts button').length===9")
            assert ev("document.getElementById('knockoutBrushReport').textContent.includes('Filled 0')")
            ev("document.querySelector('[data-topic=selection]').click();document.querySelector('#knockoutParts button').click()")
            wait("!embroideryStudio.isBusy() && document.getElementById('knockoutBrushReport').textContent.includes('Filled 1')")
            ev("[...document.querySelectorAll('#knockoutParts button')].find(b=>b.textContent==='Keep hole open').click()")
            wait("!embroideryStudio.isBusy() && document.getElementById('knockoutBrushReport').textContent.includes('Filled 0')")
            assert ev('document.documentElement.scrollWidth<=innerWidth')
            print('PASS: nine letter-hole controls; explicit fill one; reopen; 390px reflow.')
        finally:
            browser.terminate();browser.wait(timeout=15);server.shutdown()


if __name__=='__main__':main()
