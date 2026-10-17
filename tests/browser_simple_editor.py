"""UI checks on dedicated synthetic designs, never customer edits or paid calls."""
import base64
import json
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time


def main():
    stage = sys.argv[1]
    evidence = Path('.simple-ui-evidence').resolve()
    cases = json.loads((evidence/'ui-cleanup-cases.json').read_text())
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1',9229)) != 0
    with TemporaryDirectory(prefix='.simple-browser-', dir='.') as temporary:
        browser = subprocess.Popen(['chromium','--headless','--no-sandbox','--disable-gpu',
            '--remote-debugging-port=9229','--remote-allow-origins=*',
            '--user-data-dir='+str(Path(temporary).resolve()),'about:blank'],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            time.sleep(2)
            from browser_helpers import call,ev,wait,ws
            def shot(name):
                (evidence/(stage+'-'+name+'.png')).write_bytes(base64.b64decode(call('Page.captureScreenshot',dict(format='png'))['result']['data']))
            def go(path):
                call('Page.navigate',dict(url='http://127.0.0.1:5050'+path))
                wait('document.readyState==="complete"')
            def click(id): ev('document.getElementById('+json.dumps(id)+').click()')
            call('Emulation.setDeviceMetricsOverride',dict(width=1366,height=768,deviceScaleFactor=1,mobile=False))
            go('/');shot('start')
            go(cases['image']['page']);wait('!!window.DesignWorkflow && !embroideryStudio.isBusy()');time.sleep(1)
            ev('DesignWorkflow.show("edit")');shot('image-edit')
            before=ev('JSON.stringify(embroideryStudio.snapshot())')
            if stage=='after':
                assert not ev('document.getElementById("workflowExpert").open')
                assert ev('document.getElementById("canvasWidth").checkVisibility() && document.getElementById("canvasHeight").checkVisibility()')
                assert ev('document.querySelector(".inspector").scrollHeight<=document.querySelector(".inspector").clientHeight+2')
                click('workflowColours')
                assert ev('document.getElementById("topic-colours").checkVisibility() && !document.getElementById("workflowExpert").open')
                shot('colours');click('workflowBack')
                click('workflowBackground');assert ev('document.getElementById("topic-selection").checkVisibility()')
                shot('background');click('workflowBack')
                click('workflowDetails');assert ev('document.getElementById("checkMyDesign").checkVisibility()')
                assert not ev('document.getElementById("designReviewConsent").closest("details").open')
                shot('picture-review');click('checkMyDesign')
                wait('document.getElementById("designReviewStatus").textContent.includes("Nothing was changed")')
                assert before==ev('JSON.stringify(embroideryStudio.snapshot())')
                click('workflowBack')
                ev('document.getElementById("workflowExpert").open=true');shot('expert')
                ev('document.getElementById("workflowExpert").open=false')
                # Resize through the same owner, then Undo; no stitches generated.
                ev('document.getElementById("canvasWidth").value="50";document.getElementById("canvasWidth").dispatchEvent(new Event("change"))')
                wait('!embroideryStudio.isBusy() && Math.abs(embroideryStudio.snapshot().height_mm-37.5)<.01')
                assert ev('document.getElementById("workflowCanvasSize").textContent.includes("50.0")')
                click('undo');wait('!embroideryStudio.isBusy()');assert before==ev('JSON.stringify(embroideryStudio.snapshot())')
            ev('DesignWorkflow.show("check")');shot('check')
            ev('DesignWorkflow.show("download")');shot('download')
            if stage=='after':
                # Synthetic download refusal tests UI only; backend checks stay untouched.
                go(cases['image']['page']);wait('!!window.DesignWorkflow && embroideryStudio.hasPlayback() && !embroideryStudio.isBusy()');ev('DesignWorkflow.show("download")')
                ev('''window.realFetch=fetch;window.fetch=(url,args)=>String(url).includes('/studio-export/')?Promise.resolve(new Response(JSON.stringify({error:'Export blocked',issues:[{code:'short',location:{x_mm:1,y_mm:2,command:4},reason:'0.2 mm'},{code:'crossing',location:{x_mm:3,y_mm:4,command:9},reason:'a removed area'}]}),{status:422,headers:{'Content-Type':'application/json'}})):realFetch(url,args)''')
                click('workflowDownload');wait('document.getElementById("workflowDownloadError").textContent.includes("too short")')
                assert ev('document.getElementById("workflowDownloadError").textContent.includes("cross gaps")')
                assert ev('document.querySelectorAll("#workflowDownloadError li").length===2')
                shot('download-warning');ev('window.fetch=realFetch')
                click('workflowBackToChecks');assert ev('document.body.dataset.workflow==="check"')
                ev('DesignWorkflow.show("download");window.fetch=(url,args)=>String(url).includes("/studio-export/")?Promise.reject(Error("offline")):realFetch(url,args)')
                click('workflowDownload');wait('document.getElementById("workflowDownloadError").textContent.includes("connection")')
                # Real checked download reaches a nonempty blob, without saving into Downloads.
                call('Browser.setDownloadBehavior',dict(behavior='deny'))
                ev('window.fetch=realFetch;window.blobs=[];window.realCreate=URL.createObjectURL;URL.createObjectURL=b=>{blobs.push(b.size);return realCreate(b)}')
                click('workflowDownload');wait('window.blobs.length===1')
                assert ev('blobs[0]>500')
                # A reply for edited artwork must not download the previous design.
                ev('window.fetch=(url,args)=>String(url).includes("/studio-export/")?new Promise(resolve=>setTimeout(()=>resolve(new Response(new Uint8Array(100))),1200)):realFetch(url,args)')
                click('workflowDownload');ev('embroideryStudio.apply({height_mm:41})');time.sleep(1.6)
                assert ev('!blobs.includes(100) && document.getElementById("workflowDownload").disabled')  # Other preview audit blobs may be created.
                ev('window.fetch=realFetch;URL.createObjectURL=realCreate')
            go(cases['text']['page']);wait('!!window.DesignWorkflow && embroideryStudio.hasPlayback()');ev('DesignWorkflow.show("edit")');shot('text-edit')
            if stage=='after':
                assert ev('document.getElementById("nativeHeight").checkVisibility() && document.getElementById("nativeWidth").checkVisibility()')
                assert ev('document.querySelector(".inspector").scrollHeight<=document.querySelector(".inspector").clientHeight+2')
            go(cases['image']['page']);wait('!!window.DesignWorkflow && !embroideryStudio.isBusy()');ev('DesignWorkflow.show("edit")')
            if stage=='after':
                ev('document.getElementById("workflowDetails").focus()')
                call('Input.dispatchKeyEvent',dict(type='keyDown',key='Enter',code='Enter',text='\r',windowsVirtualKeyCode=13))
                call('Input.dispatchKeyEvent',dict(type='keyUp',key='Enter',code='Enter',windowsVirtualKeyCode=13))
                assert ev('document.getElementById("checkMyDesign").checkVisibility()')
            call('Emulation.setDeviceMetricsOverride',dict(width=390,height=844,deviceScaleFactor=1,mobile=False))
            ev('document.querySelector(".inspector").scrollIntoView({block:"start"})');shot('narrow')
            assert ev('document.documentElement.scrollWidth<=innerWidth')
            call('Emulation.setEmulatedMedia',dict(features=[dict(name='prefers-reduced-motion',value='reduce')]))
            ev('document.documentElement.dataset.theme="dark"');shot('dark')
            ws.close();print('PASS '+stage+': editor screenshots and applicable interaction checks',flush=True)
        finally:
            browser.terminate();browser.wait(timeout=15)


if __name__=='__main__': main()
