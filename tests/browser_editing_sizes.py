"""Isolated browser: bulk preservation, Undo, size controls and native rebuild."""
import base64
from pathlib import Path
import socket
import subprocess
from tempfile import TemporaryDirectory
import threading
import time
from PIL import Image, ImageDraw
from werkzeug.serving import make_server
from embroiderly.web import create_app


def main():
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1', 9229)) != 0
    evidence = Path('.repair-browser').resolve(); evidence.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix='.repair-editing-', dir='.') as temporary:
        root = Path(temporary).resolve(); app = create_app(root)
        image = Image.new('RGBA', (240, 250), 'white'); draw = ImageDraw.Draw(image)
        for y in range(12):
            for x in range(31):
                draw.rectangle((5+x*7,5+y*19,6+x*7,6+y*19), fill='black')
        image.save(root/'work/uploads/details.png')
        server = make_server('127.0.0.1', 0, app, threaded=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        browser = subprocess.Popen(['chromium','--headless','--no-sandbox','--disable-gpu',
            '--remote-debugging-port=9229','--remote-allow-origins=*',
            '--user-data-dir='+str(root/'browser'),'about:blank'], stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            time.sleep(2)
            from browser_helpers import call,ev,wait,ws
            def shot(name):
                (evidence/name).write_bytes(base64.b64decode(call('Page.captureScreenshot',dict(format='png'))['result']['data']))
            def enter(selector):
                ev(f"document.querySelector({selector!r}).scrollIntoView({{block:'center'}});document.querySelector({selector!r}).focus()")
                assert ev('document.activeElement.getClientRects().length>0')
                call('Input.dispatchKeyEvent',dict(type='keyDown',key='Enter',code='Enter',text='\r',windowsVirtualKeyCode=13))
                call('Input.dispatchKeyEvent',dict(type='keyUp',key='Enter',code='Enter',windowsVirtualKeyCode=13))
            def idle():
                wait("!embroideryStudio.isBusy() && document.getElementById('status').textContent.startsWith('Preview ready')")
            call('Emulation.setDeviceMetricsOverride',dict(width=1366,height=768,deviceScaleFactor=1,mobile=False))
            call('Page.navigate',dict(url=f'http://127.0.0.1:{server.server_port}/artwork/details.png'))
            wait("!!window.embroideryStudio && !embroideryStudio.isBusy() && document.getElementById('status').textContent.startsWith('Preview ready')")
            ev('embroideryStudio.apply({count:2,height_mm:50,floor_mm2:1,smooth:0})');idle()
            ev("document.getElementById('confirmed').checked=true;document.getElementById('confirmed').dispatchEvent(new Event('change'));document.getElementById('stitch').disabled=false")
            enter('#stitch')
            wait("!embroideryStudio.isBusy() && document.activeElement.id==='keepPendingDetails'")
            assert ev("document.getElementById('cleanupChoices').textContent.includes('372 small areas')")
            assert ev("document.querySelectorAll('#cleanupChoices article').length===30")
            assert not ev("document.getElementById('status').textContent.includes('Could not prepare')")
            shot('cleanup-bulk-review.png')
            # An explicit existing drop must survive the later bulk Keep action.
            enter('#cleanupChoices article button:last-child');idle()
            before=ev('JSON.stringify(embroideryStudio.snapshot().cleanup_decisions)')
            enter('#keepPendingDetails');idle()
            assert ev("Object.values(embroideryStudio.snapshot().cleanup_decisions).filter(v=>v==='keep').length===371")
            assert ev("Object.values(embroideryStudio.snapshot().cleanup_decisions).filter(v=>v==='drop').length===1")
            enter('#undo');idle()
            assert before == ev('JSON.stringify(embroideryStudio.snapshot().cleanup_decisions)')
            # Stale controls must not apply old decisions while a new preview is queued.
            ev("window.oldKeep=document.getElementById('keepPendingDetails');embroideryStudio.apply({height_mm:60});oldKeep.click()")
            idle()
            assert before == ev('JSON.stringify(embroideryStudio.snapshot().cleanup_decisions)')
            ev("DesignWorkflow.show('edit')")
            enter('#canvasResize button');idle()
            assert ev('embroideryStudio.snapshot().height_mm===54')
            assert ev("document.getElementById('canvasWidth').value==='51.8'")
            enter('#undo');idle();assert ev('embroideryStudio.snapshot().height_mm===60')
            call('Emulation.setDeviceMetricsOverride',dict(width=390,height=844,deviceScaleFactor=1,mobile=False))
            assert ev('document.documentElement.scrollWidth<=innerWidth')
            shot('editing-size-narrow.png')
            # Text stays native; no image preparation is used to resize letters.
            call('Page.navigate',dict(url=f'http://127.0.0.1:{server.server_port}/text/new'))
            wait('!!window.nativeLettering && !!window.DesignWorkflow')
            assert ev("document.getElementById('nativeHeight').min==='3.6' && document.getElementById('nativeHeight').max==='15.2'")
            ev("document.getElementById('letteringWords').value='tiny';document.getElementById('letteringWords').dispatchEvent(new Event('input',{bubbles:true}))")
            enter('#nativeSmaller');assert ev("document.getElementById('nativeHeight').value==='4.5'")
            enter('#undo');assert ev("document.getElementById('nativeHeight').value==='5'")
            enter('#nativeLarger');assert ev("document.getElementById('nativeHeight').value==='5.5'")
            ev("document.getElementById('nativeHeight').value='3.6';document.getElementById('nativeHeight').dispatchEvent(new Event('input',{bubbles:true}))")
            enter('#stitch')
            wait("embroideryStudio.hasPlayback() && document.getElementById('healthSummary').textContent.includes('File checks passed')",timeout=120)
            assert ev("document.getElementById('workflowMeasuredSize').textContent.includes('mm wide')")
            assert ev("document.getElementById('nativeResult').textContent.includes('Adjusted the securing stitches')")
            assert list((root/'work/uploads').iterdir()) == [root/'work/uploads/details.png']
            shot('small-text-size-check.png')
            assert ev('document.documentElement.scrollWidth<=innerWidth')
            ws.close();print('PASS: 372-area review, preserve earlier choices, bulk Undo, stale protection, image resize/Undo, native resize/rebuild, keyboard, 390px.')
        finally:
            browser.terminate();browser.wait(timeout=15);server.shutdown()


if __name__ == '__main__':
    main()
