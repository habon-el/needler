"""Isolated browser proof for visible, locatable pre-generation detail blockers."""
import base64
import io
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
        assert probe.connect_ex(('127.0.0.1', 9229)) != 0, 'Test browser port is occupied'
    evidence = Path('.repair-browser').resolve()
    evidence.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix='.repair-browser-data-', dir='.') as temporary:
        root = Path(temporary).resolve()
        app = create_app(root)
        image = Image.new('RGBA', (100, 100), '#ddaa88')
        ImageDraw.Draw(image).rectangle((48, 48, 49, 49), fill='black')
        # Disposable test input only; no customer design is opened or approved.
        image.save(root / 'work/uploads/detail.png')
        client = app.test_client()
        options = dict(count=2, floor_mm2=0, smooth=0, height_mm=25)
        response = client.post('/artwork/detail.png', json=dict(options=options, save=True))
        assert response.status_code == 200, response.json
        blocked = client.post('/artwork/detail.png', json=dict(options=options, digitize=True, subject_confirmed=True))
        assert blocked.status_code == 400 and 'would leave out' in blocked.json['error']
        server = make_server('127.0.0.1', 0, app, threaded=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        browser = subprocess.Popen(['chromium', '--headless', '--no-sandbox', '--disable-gpu',
            '--remote-debugging-port=9229', '--remote-allow-origins=*',
            '--user-data-dir='+str(root/'browser'), 'about:blank'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            time.sleep(2)
            from browser_helpers import call, ev, wait, ws
            call('Emulation.setDeviceMetricsOverride', dict(width=1366, height=768, deviceScaleFactor=1, mobile=False))
            call('Page.navigate', dict(url=f'http://127.0.0.1:{server.server_port}/artwork/detail.png'))
            wait("!!window.embroideryStudio && !embroideryStudio.isBusy() && document.getElementById('healthSummary').textContent.includes('cannot be stitched')")
            assert ev("document.getElementById('healthIssues').textContent.includes('0.5 × 0.5 mm')")
            assert not ev("document.getElementById('healthSummary').textContent.includes('No tiny-area warnings')")
            assert ev("document.getElementById('healthSummary').closest('details').open")
            before = ev('JSON.stringify(embroideryStudio.snapshot())')
            ev("document.getElementById('healthSummary').scrollIntoView()")
            (evidence/'detail-before-approval.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',dict(format='png'))['result']['data']))
            ev("(()=>{const b=[...document.querySelectorAll('#healthIssues button')].find(b=>b.textContent==='Show this detail');b.scrollIntoView();b.focus()})()")
            assert ev("document.activeElement.textContent==='Show this detail'")
            assert ev("document.activeElement.getClientRects().length>0")
            call('Input.dispatchKeyEvent', dict(type='keyDown', key='Enter', code='Enter', text='\r', windowsVirtualKeyCode=13))
            call('Input.dispatchKeyEvent', dict(type='keyUp', key='Enter', code='Enter', windowsVirtualKeyCode=13))
            assert before == ev('JSON.stringify(embroideryStudio.snapshot())'), 'Locating must not edit the design'
            wait("document.getElementById('status').textContent.startsWith('Detail close-up')")
            (evidence/'detail-warning.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',dict(format='png'))['result']['data']))
            call('Emulation.setDeviceMetricsOverride', dict(width=390, height=844, deviceScaleFactor=1, mobile=False))
            time.sleep(.3)
            assert ev('document.documentElement.scrollWidth<=innerWidth')
            (evidence/'detail-warning-narrow.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',dict(format='png'))['result']['data']))
            ws.close()
            print('PASS: real-size warning before generation, incomplete export blocked, keyboard locate without edits, 390px reflow.')
        finally:
            browser.terminate()
            browser.wait(timeout=15)
            server.shutdown()


if __name__ == '__main__':
    main()
