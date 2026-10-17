"""Isolated browser evidence. AI responses are synthetic, never live API calls."""
import base64
from pathlib import Path
import socket
import subprocess
from tempfile import TemporaryDirectory
import threading
import time

from werkzeug.serving import make_server
from embroiderly.web import create_app
from embroiderly import design_review
from test_design_review import character, OPTIONS, altered, response


def main():
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1', 9229)) != 0
    evidence = Path('.repair-browser').resolve(); evidence.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix='.review-browser-', dir='.') as temporary:
        root = Path(temporary).resolve(); app = create_app(root)
        character(root/'work/uploads/character.png')
        calls = []
        class Fake:
            def __init__(self, *args): pass
            def request(self, payload):
                calls.append(payload)
                ident = payload['text']['format']['schema']['properties']['findings']['items']['properties']['region_id']['enum'][0]
                return response([dict(region_id=ident, detail='Possible missing cheek',
                    observation='Synthetic browser test: the pink colour changed.', certainty='possible')])
        real_provider, real_ready = design_review.BudgetedProvider, design_review.readiness
        design_review.BudgetedProvider = Fake
        design_review.readiness = lambda root: (False, 'AI review is off. Local comparison is available.')
        server = make_server('127.0.0.1', 0, app, threaded=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        browser = subprocess.Popen(['chromium', '--headless', '--no-sandbox', '--disable-gpu',
            '--remote-debugging-port=9229', '--remote-allow-origins=*',
            '--user-data-dir='+str(root/'browser'), 'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            time.sleep(2)
            from browser_helpers import call, ev, wait, ws
            import json
            def shot(name):
                (evidence/name).write_bytes(base64.b64decode(call('Page.captureScreenshot', dict(format='png'))['result']['data']))
            def enter(selector):
                ev(f"document.querySelector({selector!r}).scrollIntoView({{block:'center'}});document.querySelector({selector!r}).focus()")
                assert ev('document.activeElement.getClientRects().length>0')
                call('Input.dispatchKeyEvent',dict(type='keyDown',key='Enter',code='Enter',text='\r',windowsVirtualKeyCode=13))
                call('Input.dispatchKeyEvent',dict(type='keyUp',key='Enter',code='Enter',windowsVirtualKeyCode=13))
            def idle():
                wait("!embroideryStudio.isBusy() && document.getElementById('status').textContent.startsWith('Preview ready')")
            def show():
                ev("embroideryWorkspace.showTopic('review');document.getElementById('detailMap').closest('details').open=true;document.getElementById('checkMyDesign').scrollIntoView({block:'center'})")
            url=f'http://127.0.0.1:{server.server_port}/artwork/character.png'
            call('Emulation.setDeviceMetricsOverride',dict(width=1366,height=768,deviceScaleFactor=1,mobile=False))
            call('Page.navigate',dict(url=url));wait('!!window.embroideryWorkspace');idle()
            ev('embroideryStudio.apply('+json.dumps(altered())+')');idle();show()
            before=ev('JSON.stringify(embroideryStudio.snapshot())')
            enter('#checkMyDesign')
            wait("document.querySelectorAll('#designReviewFindings article').length===3")
            assert ev("document.getElementById('designReviewStatus').textContent.includes('3 parts look different')")
            assert ev("document.getElementById('askDesignReview').disabled")
            assert before==ev('JSON.stringify(embroideryStudio.snapshot())') and calls==[]
            shot('design-review-local.png')
            enter('#designReviewFindings button')
            assert before==ev('JSON.stringify(embroideryStudio.snapshot())')
            # Identical artwork must not be described as fault-free.
            ev('embroideryStudio.apply({merges:{}})');idle();show();enter('#checkMyDesign')
            wait("document.getElementById('designReviewStatus').textContent.startsWith('No clear differences')")
            assert ev("document.querySelectorAll('#designReviewFindings article').length===0")
            # Network error and old reply after an edit must not replace new state.
            ev("window.reviewFetch=window.fetch;window.fetch=(url,args)=>url.startsWith('/design-review/')&&args?.method==='POST'?Promise.reject(Error('Offline test')):reviewFetch(url,args)")
            enter('#checkMyDesign');wait("document.getElementById('designReviewStatus').textContent==='Offline test'")
            ev("window.fetch=(url,args)=>url.startsWith('/design-review/')&&args?.method==='POST'?reviewFetch(url,args).then(r=>new Promise(resolve=>setTimeout(()=>resolve(r),1800))):reviewFetch(url,args)")
            enter('#checkMyDesign');ev('embroideryStudio.apply({height_mm:70})');idle()
            time.sleep(2)
            assert ev("document.querySelectorAll('#designReviewFindings article').length===0")
            assert ev("document.getElementById('designReviewStatus').textContent.includes('Design changed')")
            ev('window.fetch=window.reviewFetch')
            # AI path with explicitly fake provider, consent and cache reuse.
            design_review.readiness=lambda root:(True,'Synthetic provider for browser testing only.')
            call('Page.navigate',dict(url=url));wait('!!window.embroideryWorkspace');idle()
            ev('embroideryStudio.apply('+json.dumps(altered())+')');idle();show();enter('#checkMyDesign')
            wait("document.querySelectorAll('#designReviewFindings article').length===3")
            ev("document.getElementById('designReviewConsent').closest('details').open=true")
            assert ev("document.getElementById('askDesignReview').disabled")
            ev("document.getElementById('designReviewConsent').click()")
            enter('#askDesignReview')
            wait("document.getElementById('designReviewFindings').textContent.includes('Synthetic browser test')")
            assert len(calls)==1
            assert not ev("document.getElementById('designReviewConsent').checked")
            assert ev("document.getElementById('askDesignReview').disabled")
            ev("document.getElementById('designReviewConsent').click()")
            enter('#askDesignReview');wait("document.getElementById('designReview').textContent.includes('reused result')")
            assert len(calls)==1
            call('Emulation.setDeviceMetricsOverride',dict(width=390,height=844,deviceScaleFactor=1,mobile=False))
            ev("document.getElementById('checkMyDesign').scrollIntoView({block:'start'})")
            assert ev('document.documentElement.scrollWidth<=innerWidth')
            shot('design-review-narrow.png')
            call('Emulation.setEmulatedMedia',dict(features=[dict(name='prefers-reduced-motion',value='reduce')]))
            ev("document.documentElement.dataset.theme='dark'")
            assert ev('document.documentElement.scrollWidth<=innerWidth')
            shot('design-review-dark.png')
            assert not list((root/'work/decisions').glob('*.preparation.json'))
            ws.close()
            print('PASS: local differences, unchanged control, no mutations, keyboard, focus, missing configuration, explicit consent, synthetic AI, cache reuse, offline, stale reply, narrow/dark/reduced motion.')
        finally:
            browser.terminate();browser.wait(timeout=15);server.shutdown()
            design_review.BudgetedProvider, design_review.readiness = real_provider, real_ready


if __name__ == '__main__':
    main()
