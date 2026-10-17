"""Isolated browser UX verification. Synthetic AI; real local preparation."""
import base64
import json
import logging
from pathlib import Path
import socket
import subprocess
from tempfile import TemporaryDirectory
import threading
import time

import numpy as np
from werkzeug.serving import make_server
from embroiderly.web import create_app
from embroiderly import ai_draft as draft, design_review as review
from test_design_review import character, OPTIONS
from test_ai_draft import PLAN, response


def main():
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1', 9229)) != 0
    evidence = Path('.simple-ui-evidence').resolve(); evidence.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix='.ai-draft-browser-', dir='.') as temporary:
        root = Path(temporary).resolve(); app = create_app(root)
        character(root/'work/uploads/character.png')
        (root/'work/decisions/character.png.preparation.json').write_text(json.dumps(OPTIONS))
        calls = []; uncertain = [False]
        class Fake:
            def __init__(self, *a): pass
            def request(self, payload):
                calls.append(payload); time.sleep(.7)
                if payload['text']['format']['name']=='subject_plan': return response(PLAN)
                return response(dict(summary='Synthetic review: inspect the hair.',
                    concerns=['Hair uncertain.'] if uncertain[0] else [],
                    selection_status='uncertain' if uncertain[0] else 'acceptable',
                    artwork_concerns=['<img src=x onerror=alert(1)> is plain text.']))
        real = draft.BudgetedProvider, draft.readiness, draft.propose_mask
        draft.BudgetedProvider = Fake; draft.readiness = lambda root: (True, 'Test connection')
        draft.propose_mask = lambda im,p,b,**kw: (np.any(np.asarray(im)[:,:,:3]<240,axis=2), {'method':'GrabCut fallback'})
        server = make_server('127.0.0.1', 0, app, threaded=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        browser = subprocess.Popen(['chromium','--headless','--no-sandbox','--disable-gpu','--remote-debugging-port=9229',
            '--remote-allow-origins=*','--user-data-dir='+str(root/'browser'),'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            time.sleep(2)
            from browser_helpers import call, ev, wait, ws
            def shot(name):
                (evidence/name).write_bytes(base64.b64decode(call('Page.captureScreenshot', {'format':'png'})['result']['data']))
            def click(selector):
                ev(f"document.querySelector({selector!r}).scrollIntoView({{block:'center'}});document.querySelector({selector!r}).focus()")
                call('Input.dispatchKeyEvent',dict(type='keyDown',key='Enter',code='Enter',text='\r',windowsVirtualKeyCode=13))
                call('Input.dispatchKeyEvent',dict(type='keyUp',key='Enter',code='Enter',windowsVirtualKeyCode=13))
            def prompt(text):
                ev(f"askAiQuestion.value={json.dumps(text)};askAiQuestion.dispatchEvent(new Event('input'))")
            def permit(): ev('askAiConsent.click()')
            def idle():
                wait("!embroideryStudio.isBusy() && document.getElementById('status').textContent.startsWith('Preview ready')")
                wait('!embroideryAssistance.isBusy()')
            call('Emulation.setDeviceMetricsOverride',dict(width=1366,height=768,deviceScaleFactor=1,mobile=False))
            call('Page.navigate',dict(url=f'http://127.0.0.1:{server.server_port}/artwork/character.png'))
            wait('!!window.embroideryWorkspace'); idle()
            wait("askAiAvailability.textContent.includes('ready when')")
            ev("if(workflowBack.getClientRects().length)workflowBack.click()")
            click('#workflowAskAI'); ev("document.querySelector('.inspector').scrollTop=0")
            shot('ai-draft-empty.png')
            assert ev('askAiSend.disabled') and not calls
            before = ev('JSON.stringify(embroideryStudio.snapshot())')
            prompt('Keep the face, remove background, 60 mm wide.'); assert ev('askAiSend.disabled')
            permit(); click('#askAiSend'); assert ev('askAiSend.disabled')
            shot('ai-draft-loading.png')
            wait("!!document.getElementById('aiDraftApply')")
            assert len(calls)==2 and ev('JSON.stringify(embroideryStudio.snapshot())')==before
            assert ev("askAiMessages.querySelectorAll('img').length===0")
            assert ev("askAiMessages.textContent.includes('SAM2 unavailable')")
            ev("document.querySelector('.inspector').scrollTop=0")
            shot('ai-draft-review.png')
            click('#aiDraftArtwork'); assert ev("aiDraftArtwork.getAttribute('aria-pressed')==='true'")
            click('#aiDraftCutout')
            # Explicit apply uses the existing history owner, not saved design writes.
            click('#aiDraftEdit'); wait('aiDraftPreview.hidden'); idle()
            assert ev('embroideryStudio.snapshot().selection')=='assisted'
            assert ev('aiDraftPreview.hidden')
            click('#undo'); idle()
            assert ev('JSON.stringify(embroideryStudio.snapshot())')==before
            # Cached draft, then edit makes approval disappear.
            prompt('Keep the face, remove background, 60 mm wide.'); permit(); click('#askAiSend')
            wait("!!document.getElementById('aiDraftApply')"); assert len(calls)==2
            assert ev("aiDraftApply.getBoundingClientRect().bottom<=innerHeight")
            ev('embroideryStudio.apply({height_mm:75})'); idle()
            assert ev("!document.getElementById('aiDraftApply') && aiDraftPreview.hidden")
            # Cancel during first call prevents review and any late draft.
            prompt('A different draft'); permit(); click('#askAiSend'); time.sleep(.2); click('#askAiCancel'); time.sleep(2)
            assert ev("!document.getElementById('aiDraftApply')")
            # Offline retains prompt, no retry loop.
            ev("window.oldFetch=fetch;window.fetch=(u,a)=>u.startsWith('/ai-draft/')&&a?.method==='POST'?Promise.reject(Error('Offline test')):oldFetch(u,a)")
            prompt('Offline draft'); permit(); click('#askAiSend'); wait("askAiStatus.textContent==='Offline test'")
            assert ev("askAiQuestion.value==='Offline draft'")
            shot('ai-draft-error.png'); ev('window.fetch=window.oldFetch')
            # Apply-and-generate delegates one exact patch to the existing owner.
            prompt('Keep the face and prepare stitches.'); permit(); click('#askAiSend'); wait("!!document.getElementById('aiDraftApply')")
            ev('window.realAccept=embroideryStudio.acceptRefinement;window.appliedPatch=null;embroideryStudio.acceptRefinement=p=>{window.appliedPatch=p}')
            click('#aiDraftApply'); wait('window.appliedPatch!==null')
            assert ev('appliedPatch.selection')=='assisted'
            ev('embroideryStudio.acceptRefinement=window.realAccept')
            # Responsive, dark and reduced motion; warnings remain text, not colour only.
            click('#aiDraftRevise') if ev("!!document.getElementById('aiDraftRevise')") else None
            prompt('Keep the face for narrow review.'); permit(); click('#askAiSend'); wait("!!document.getElementById('aiDraftApply')")
            call('Emulation.setDeviceMetricsOverride',dict(width=390,height=844,deviceScaleFactor=1,mobile=True))
            call('Emulation.setEmulatedMedia',{'features':[{'name':'prefers-reduced-motion','value':'reduce'},{'name':'prefers-color-scheme','value':'dark'}]})
            ev("document.documentElement.dataset.theme='dark';askAiPanel.scrollIntoView({block:'start'})")
            time.sleep(.3); assert ev('document.documentElement.scrollWidth<=innerWidth')
            shot('ai-draft-narrow-dark.png')
            click('#aiDraftDiscard'); assert ev('aiDraftPreview.hidden')
            uncertain[0] = True
            prompt('Check uncertain hair.'); permit(); click('#askAiSend')
            wait("!!document.getElementById('aiDraftApply')")
            assert ev('aiDraftApply.disabled && !aiDraftEdit.disabled')
            assert ev("askAiMessages.textContent.includes('Cutout still needs checking')")
            shot('ai-draft-uncertain.png')
            print(json.dumps({'status':'passed','paid_calls':0,'synthetic_provider_calls':len(calls),
                'checks':['keyboard','consent','loading','before_after','XSS','fallback_notice','explicit_apply','undo','cache','stale','cancel','offline','generation_delegate','narrow_dark','uncertain_blocks_generation']}))
            ws.close()
        finally:
            browser.terminate(); browser.wait(timeout=10); server.shutdown()
            draft.BudgetedProvider,draft.readiness,draft.propose_mask=real


if __name__ == '__main__': main()
