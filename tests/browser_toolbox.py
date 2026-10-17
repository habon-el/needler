"""Tool discovery on an isolated app. No customer files or paid provider calls."""
import base64
import json
import logging
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import time

from werkzeug.serving import make_server
from embroiderly.web import create_app
from test_design_review import character, OPTIONS


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else 'after'
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1', 9229)) != 0
    evidence = Path('.simple-ui-evidence').resolve()
    evidence.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix='.toolbox-browser-', dir='.') as temporary:
        root = Path(temporary).resolve()
        app = create_app(root)
        character(root/'work/uploads/character.png')
        (root/'work/decisions/character.png.preparation.json').write_text(json.dumps(OPTIONS))
        server = make_server('127.0.0.1', 0, app, threaded=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        browser = subprocess.Popen(['chromium', '--headless', '--no-sandbox', '--disable-gpu',
            '--remote-debugging-port=9229', '--remote-allow-origins=*',
            '--user-data-dir='+str(root/'browser'), 'about:blank'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            time.sleep(2)
            from browser_helpers import call, ev, wait, ws
            def shot(name):
                (evidence/('toolbox-'+stage+'-'+name+'.png')).write_bytes(base64.b64decode(
                    call('Page.captureScreenshot', {'format':'png'})['result']['data']))
            def click(selector):
                ev(f"document.querySelector({selector!r}).scrollIntoView({{block:'center'}});document.querySelector({selector!r}).focus()")
                call('Input.dispatchKeyEvent', dict(type='keyDown', key='Enter', code='Enter', text='\r', windowsVirtualKeyCode=13))
                call('Input.dispatchKeyEvent', dict(type='keyUp', key='Enter', code='Enter', windowsVirtualKeyCode=13))
            call('Emulation.setDeviceMetricsOverride', dict(width=1366, height=768, deviceScaleFactor=1, mobile=False))
            call('Page.navigate', dict(url=f'http://127.0.0.1:{server.server_port}/artwork/character.png?view=stitched'))
            wait('!!window.DesignWorkflow && !!window.embroideryWorkspace')
            wait("!embroideryStudio.isBusy() && document.getElementById('status').textContent.startsWith('Preview ready')")
            # Explicit view suppresses unrelated automatic colour-removal proposals.
            ev("DesignWorkflow.show('edit');if(workflowBack.getClientRects().length)workflowBack.click();document.querySelector('.inspector').scrollTop=0")
            wait('!window.embroideryAssistance?.isBusy()')
            before = ev('JSON.stringify(embroideryStudio.snapshot())')
            shot('edit')
            if stage == 'after':
                assert ev('document.querySelectorAll("#workflowChoices button").length') == 7
                assert ev('document.querySelectorAll("#textTool").length') == 1
                assert ev('document.querySelector("#workflowChoices #textTool")!==null')
                assert ev('document.querySelector(".inspector").scrollHeight<=document.querySelector(".inspector").clientHeight+2')
                # Navigation is not a mutation; each button opens the original owner.
                for button, topic in [('workflowBackground','selection'),('workflowColours','colours'),
                        ('workflowStyles','styles'),('workflowBorders','borders'),('workflowDetails','review'),('workflowAskAI','ask')]:
                    click('#'+button)
                    assert ev(f"document.getElementById('topic-{topic}').checkVisibility()")
                    assert ev('document.activeElement.id') == 'topic-'+topic
                    assert ev('document.querySelectorAll("#topic-'+topic+'").length') == 1
                    assert ev('JSON.stringify(embroideryStudio.snapshot())') == before
                    shot(topic)
                    click('#workflowBack')
                    assert ev('document.activeElement.id') == button, (button, ev('document.activeElement.id'), ev('document.body.dataset.workflow'))
                click('#textTool')
                assert ev('letteringDialog.open')
                click('#letteringClose')
                assert ev('document.activeElement.id') == 'textTool'
                assert ev('JSON.stringify(embroideryStudio.snapshot())') == before
                # Opening AI and choosing a prompt never consents or sends.
                ev("window.paidRequests=0;window.realFetch=fetch;window.fetch=(u,a)=>{if(a?.method==='POST'&&(String(u).startsWith('/ai-draft/')||String(u).startsWith('/design-review/')))paidRequests++;return realFetch(u,a)}")
                click('#workflowAskAI')
                click('#askAiReviewExample')
                assert ev("askAiAdviceMode.getAttribute('aria-pressed')==='true' && !askAiConsent.checked && askAiSend.disabled")
                assert ev("askAiQuestion.value.includes('missing')")
                assert ev('paidRequests') == 0
                click('#askAiBackgroundExample')
                assert ev("askAiDraftMode.getAttribute('aria-pressed')==='true' && !askAiConsent.checked && askAiSend.disabled")
                assert ev('paidRequests') == 0
                assert ev('JSON.stringify(embroideryStudio.snapshot())') == before
                shot('ai')
                click('#workflowBack')
                ev('workflowExpert.open=true')
                assert ev("[...document.querySelectorAll('#workflowExpert [data-topic]')].filter(b=>b.checkVisibility()).map(b=>b.dataset.topic).join(',')") == 'size,details'
                ev('workflowExpert.open=false')
            for step in ['check', 'download']:
                ev(f"DesignWorkflow.show('{step}')")
                assert ev('document.querySelector(".transport").checkVisibility()')
            ev("DesignWorkflow.show('edit')")
            call('Emulation.setDeviceMetricsOverride', dict(width=390, height=844, deviceScaleFactor=1, mobile=True))
            call('Emulation.setEmulatedMedia', {'features':[{'name':'prefers-reduced-motion','value':'reduce'}]})
            ev("document.documentElement.dataset.theme='dark';workflowChoices.scrollIntoView({block:'center'})")
            time.sleep(.3)
            assert ev('document.documentElement.scrollWidth<=innerWidth')
            shot('narrow-dark')
            # Light theme and native text sibling retain their existing value owners.
            call('Emulation.setDeviceMetricsOverride', dict(width=1366, height=768, deviceScaleFactor=1, mobile=False))
            ev("document.documentElement.dataset.theme='light';document.querySelector('.inspector').scrollTop=0;window.scrollTo(0,0)")
            shot('light')
            if stage == 'after':
                assert ev("getComputedStyle(document.querySelector('#workflowBasics>.confirm')).color===getComputedStyle(document.querySelector('.inspector')).color")
                # Clear our unsent prompt explicitly before leaving (beforeunload guard).
                click('#workflowAskAI')
                click('#askAiClear')
                call('Page.navigate', dict(url=f'http://127.0.0.1:{server.server_port}/text/new'))
                wait('!!window.DesignWorkflow && !!window.nativeTextConfig')
                assert ev('nativeHeight.checkVisibility() && nativeWidth.checkVisibility()')
                assert ev('!document.getElementById("workflowChoices")')
                assert ev('document.querySelectorAll("#textTool").length') == 1
                click('#textTool')
                assert ev('document.activeElement.id') == 'letteringWords'
                assert ev('!letteringDialog.open')
                shot('native-text')
            print(json.dumps({'stage':stage,'status':'passed','paid_calls':0,'design_unchanged':True}))
            ws.close()
        finally:
            browser.terminate()
            browser.wait(timeout=10)
            server.shutdown()


if __name__ == '__main__':
    main()
