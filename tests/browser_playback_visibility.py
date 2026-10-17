"""Exercise the existing player on synthetic designs, not customer artwork."""
import base64
import json
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else 'after'
    evidence = Path('.simple-ui-evidence').resolve()
    cases = json.loads((evidence/'ui-cleanup-cases.json').read_text())
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1', 9229)) != 0
    with TemporaryDirectory(prefix='.simple-browser-', dir='.', ignore_cleanup_errors=True) as temporary:
        browser = subprocess.Popen(['chromium', '--headless', '--no-sandbox', '--disable-gpu',
            '--remote-debugging-port=9229', '--remote-allow-origins=*',
            '--user-data-dir='+str(Path(temporary).resolve()), 'about:blank'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            time.sleep(2)
            from browser_helpers import call, ev, wait, ws
            def shot(name):
                (evidence/('playback-'+stage+'-'+name+'.png')).write_bytes(base64.b64decode(
                    call('Page.captureScreenshot', dict(format='png'))['result']['data']))
            def go(path):
                call('Page.navigate', dict(url='http://127.0.0.1:5050'+path))
                wait('document.readyState==="complete" && !!window.DesignWorkflow')
            def click(id):
                ev('document.getElementById('+json.dumps(id)+').click()')
            call('Emulation.setDeviceMetricsOverride', dict(width=1366, height=768, deviceScaleFactor=1, mobile=False))
            go('/text/new')
            assert ev('document.getElementById("run").checkVisibility() && document.getElementById("run").disabled')
            shot('empty')
            call('Emulation.setDeviceMetricsOverride', dict(width=390, height=844, deviceScaleFactor=1, mobile=False))
            ev('document.getElementById("run").scrollIntoView({block:"center"})')
            assert ev('document.documentElement.scrollWidth<=innerWidth')
            shot('narrow')
            call('Emulation.setEmulatedMedia', dict(features=[dict(name='prefers-reduced-motion', value='reduce')]))
            ev('document.documentElement.dataset.theme="dark"'); shot('dark')
            call('Emulation.setDeviceMetricsOverride', dict(width=1366, height=768, deviceScaleFactor=1, mobile=False))
            for kind in ['image', 'text']:
                go(cases[kind]['page'])
                wait('embroideryStudio.hasPlayback() && !embroideryStudio.isBusy()')
                ev('DesignWorkflow.show("edit")')
                shot(kind+'-edit')
                # This is the regression: old layout hides Play in Edit.
                assert ev('document.getElementById("run").checkVisibility()'), 'Play hidden in Edit'
                original = ev('JSON.stringify(embroideryStudio.snapshot())')
                for step in ['check', 'download', 'edit']:
                    ev('DesignWorkflow.show('+json.dumps(step)+')')
                    assert ev('document.getElementById("run").checkVisibility() && !document.getElementById("run").disabled')
                # Keyboard activation, actual timeline motion, pause/resume, seek.
                ev('document.getElementById("rate").value="1";document.getElementById("run").focus()')
                call('Input.dispatchKeyEvent', dict(type='keyDown', key='Enter', code='Enter', text='\r', windowsVirtualKeyCode=13))
                call('Input.dispatchKeyEvent', dict(type='keyUp', key='Enter', code='Enter', windowsVirtualKeyCode=13))
                wait('Number(document.getElementById("timeline").value)>0 && document.getElementById("run").textContent.includes("Pause")')
                assert ev('document.body.dataset.workflow==="check"')
                click('run')
                paused = ev('document.getElementById("timeline").value')
                time.sleep(.2)
                assert ev('document.getElementById("timeline").value') == paused
                click('run')
                wait('Number(document.getElementById("timeline").value)>'+paused)
                click('run')
                shot(kind+'-playing')
                click('rewind'); assert ev('document.getElementById("timeline").value==="0"')
                click('stepNext'); assert ev('document.getElementById("timeline").value==="1"')
                click('stepBack'); assert ev('document.getElementById("timeline").value==="0"')
                ev('document.getElementById("timeline").value="20";document.getElementById("timeline").dispatchEvent(new Event("input"))')
                assert ev('document.getElementById("timeline").value==="20"')
                click('finish')
                assert ev('document.getElementById("timeline").value===document.getElementById("timeline").max')
                assert ev('JSON.stringify(embroideryStudio.snapshot())') == original
                ev('DesignWorkflow.show("download")'); shot(kind+'-download')
                ev('DesignWorkflow.show("edit")')
                if kind == 'image':
                    ev('embroideryStudio.apply({height_mm:41})')
                else:
                    ev('document.getElementById("letteringWords").value="Changed";document.getElementById("letteringWords").dispatchEvent(new Event("input"))')
                wait('!embroideryStudio.hasPlayback() && document.getElementById("run").disabled')
                wait('document.getElementById("workflowPlaybackHint").textContent.includes("Check stitches")')
            ws.close()
            print('PASS: image/text playback, keyboard, pause/resume, seek, all steps, invalidation, empty, narrow and dark')
        finally:
            browser.terminate(); browser.wait(timeout=15)


if __name__ == '__main__':
    main()
