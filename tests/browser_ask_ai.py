"""Isolated real-browser checks; AI replies are labelled test doubles, not paid calls."""
import base64
import json
from pathlib import Path
import socket
import subprocess
from tempfile import TemporaryDirectory
import threading
import time

from werkzeug.serving import make_server
from embroiderly.web import create_app
from embroiderly import design_review as review
from test_design_review import character, OPTIONS
from test_ask_ai import answer


def main():
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1', 9229)) != 0
    evidence = Path('.simple-ui-evidence').resolve(); evidence.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix='.ask-ai-browser-', dir='.') as temporary:
        root = Path(temporary).resolve(); app = create_app(root)
        character(root/'work/uploads/character.png')
        (root/'work/decisions/character.png.preparation.json').write_text(json.dumps(OPTIONS))
        calls = []
        class Fake:
            def __init__(self, *args): pass
            def request(self, payload):
                calls.append(payload); time.sleep(1)
                return answer('Synthetic browser reply: <img src=x onerror=alert(1)> is text, not an edit. Compare the eyes before changing colours.')
        real_provider, real_ready = review.BudgetedProvider, review.readiness
        review.BudgetedProvider = Fake
        review.readiness = lambda root: (True, 'Synthetic test provider.')
        server = make_server('127.0.0.1', 0, app, threaded=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        browser = subprocess.Popen(['chromium', '--headless', '--no-sandbox', '--disable-gpu',
            '--remote-debugging-port=9229', '--remote-allow-origins=*',
            '--user-data-dir='+str(root/'browser'), 'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            time.sleep(2)
            from browser_helpers import call, ev, wait, ws
            def shot(name):
                (evidence/name).write_bytes(base64.b64decode(call('Page.captureScreenshot', {'format': 'png'})['result']['data']))
            def enter(selector):
                ev(f"document.querySelector({selector!r}).scrollIntoView({{block:'center'}});document.querySelector({selector!r}).focus()")
                call('Input.dispatchKeyEvent', dict(type='keyDown', key='Enter', code='Enter', text='\r', windowsVirtualKeyCode=13))
                call('Input.dispatchKeyEvent', dict(type='keyUp', key='Enter', code='Enter', windowsVirtualKeyCode=13))
            def draft(text):
                ev(f"document.getElementById('askAiQuestion').value={json.dumps(text)};document.getElementById('askAiQuestion').dispatchEvent(new Event('input'))")
            def permit(): ev("document.getElementById('askAiConsent').click()")
            def idle():
                wait("!embroideryStudio.isBusy() && document.getElementById('status').textContent.startsWith('Preview ready')")
                wait("!window.embroideryAssistance?.isBusy()")
            url = f'http://127.0.0.1:{server.server_port}/artwork/character.png'
            call('Emulation.setDeviceMetricsOverride', dict(width=1366, height=768, deviceScaleFactor=1, mobile=False))
            call('Page.navigate', dict(url=url)); wait('!!window.embroideryWorkspace'); idle()
            ev("document.getElementById('askAiAdviceMode').click()")
            wait("document.getElementById('askAiAvailability').textContent.includes('ready when')")
            ev("if(document.getElementById('workflowBack').getClientRects().length)document.getElementById('workflowBack').click()")
            assert ev("document.getElementById('workflowAskAI').getClientRects().length>0")
            shot('ask-ai-entry.png')
            enter('#workflowAskAI')
            assert ev("document.getElementById('askAiQuestion').getClientRects().length>0")
            assert ev("document.getElementById('askAiSend').disabled")
            assert calls == []
            before = ev('JSON.stringify(embroideryStudio.snapshot())')
            draft('How can I keep the eyes?')
            assert ev("document.getElementById('askAiSend').disabled")
            permit(); enter('#askAiSend')
            assert ev("document.getElementById('askAiSend').disabled")
            assert ev("document.getElementById('askAiCancel').getClientRects().length>0")
            shot('ask-ai-loading.png')
            wait("document.getElementById('askAiMessages').textContent.includes('Synthetic browser reply')")
            assert len(calls) == 1
            assert ev("document.querySelectorAll('#askAiMessages img').length===0")
            assert not ev("document.getElementById('askAiConsent').checked")
            assert before == ev('JSON.stringify(embroideryStudio.snapshot())')
            shot('ask-ai-answer.png')
            # Follow-up sends bounded history; IME Enter does not submit.
            draft('Can you explain that more simply?'); permit()
            ev("document.getElementById('askAiQuestion').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',ctrlKey:true,isComposing:true}))")
            assert len(calls) == 1
            enter('#askAiSend'); wait("document.querySelectorAll('#askAiMessages article').length===4")
            assert len(calls) == 2 and calls[-1]['input'][0]['content'] == 'How can I keep the eyes?'
            # Network failure retains the question; retry never happens automatically.
            ev("window.askOriginalFetch=window.fetch;window.fetch=(u,a)=>u.startsWith('/design-review/')&&a?.method==='POST'?Promise.reject(Error('Offline test')):askOriginalFetch(u,a)")
            draft('Offline draft'); permit(); enter('#askAiSend')
            wait("document.getElementById('askAiStatus').textContent==='Offline test'")
            assert ev("document.getElementById('askAiQuestion').value==='Offline draft'") and len(calls) == 2
            shot('ask-ai-error.png')
            ev('window.fetch=window.askOriginalFetch')
            # Cancel and stale responses cannot become an answer for edited artwork.
            draft('A delayed question'); permit(); enter('#askAiSend'); enter('#askAiCancel')
            time.sleep(2)
            assert ev("document.querySelectorAll('#askAiMessages article').length===4")
            draft('Another delayed question'); permit(); enter('#askAiSend')
            ev('embroideryStudio.apply({height_mm:75})'); idle(); time.sleep(2)
            assert ev("document.querySelectorAll('#askAiMessages article').length===0")
            assert ev("document.getElementById('askAiQuestion').value==='Another delayed question'")
            # Browser-only input validation prevents accidental key sharing.
            count = len(calls); draft('sk-proj-'+'x'*40); permit(); enter('#askAiSend')
            assert ev("document.getElementById('askAiQuestion').getAttribute('aria-invalid')==='true'")
            assert len(calls) == count
            enter('#askAiClear'); assert ev("document.getElementById('askAiQuestion').value===''")
            # Narrow/dark/reduced-motion: one owner, no page overflow, keyboard still works.
            call('Emulation.setDeviceMetricsOverride', dict(width=390, height=844, deviceScaleFactor=1, mobile=False))
            call('Emulation.setEmulatedMedia', dict(features=[dict(name='prefers-reduced-motion', value='reduce')]))
            ev("document.documentElement.dataset.theme='dark';document.getElementById('askAiQuestion').scrollIntoView({block:'center'})")
            assert ev('document.documentElement.scrollWidth<=innerWidth')
            assert ev("document.querySelectorAll('#askAiQuestion').length===1")
            shot('ask-ai-narrow-dark.png')
            # Sibling basic topics remain available, including persistent playback.
            enter('#workflowBack'); enter('#workflowDetails')
            assert ev("document.getElementById('checkMyDesign').getClientRects().length>0")
            assert ev("document.getElementById('run').getClientRects().length>0")
            # Missing key/rates: no paid call, no editing tools removed.
            review.readiness = lambda root: (False, 'AI is off. Configure the server key and spending limits.')
            call('Page.navigate', dict(url=url)); wait('!!window.embroideryWorkspace'); idle(); ev("document.getElementById('workflowBack').click()"); enter('#workflowAskAI')
            enter('#askAiAdviceMode')
            wait("document.getElementById('askAiAvailability').textContent.includes('AI is off')")
            draft('Still here'); permit(); assert ev("document.getElementById('askAiSend').disabled")
            ws.close()
            print('PASS: entry, empty, consent, loading, duplicate guard, success, plain text/XSS, follow-up history, IME, offline retention, cancel, stale design, key rejection, keyboard, narrow/dark/reduced motion, sibling review/player, unavailable provider; no design edits by AI.')
        finally:
            browser.terminate(); browser.wait(timeout=15); server.shutdown()
            review.BudgetedProvider, review.readiness = real_provider, real_ready


if __name__ == '__main__': main()
