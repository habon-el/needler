"""Isolated Chromium screenshots and interaction checks at 1366 × 768."""
import base64
import json
from pathlib import Path
import sys
import time
import requests
import websocket

ROOT = Path(__file__).resolve().parent
tabs = requests.get('http://127.0.0.1:9231/json').json()
tab = next(t for t in tabs if t['type'] == 'page')
ws = websocket.create_connection(tab['webSocketDebuggerUrl'], origin='http://localhost:9231', timeout=30)
seq = 0

def call(method, params=None):
    global seq
    seq += 1
    ws.send(json.dumps(dict(id=seq, method=method, params=params or {})))
    while True:
        r = json.loads(ws.recv())
        if r.get('id') == seq:
            if r.get('error'):
                raise RuntimeError(r)
            return r.get('result', {})

def ev(code):
    r = call('Runtime.evaluate', dict(expression=code, returnByValue=True, awaitPromise=True))
    if r.get('exceptionDetails'):
        raise RuntimeError(r)
    return r.get('result', {}).get('value')

def wait(code, limit=60):
    start = time.monotonic()
    while time.monotonic()-start < limit:
        if ev(code):
            return
        time.sleep(.2)
    raise RuntimeError('Browser wait failed: '+code)

def go(path):
    call('Page.navigate', dict(url='http://127.0.0.1:5050'+path))
    time.sleep(.3)
    wait('document.readyState === "complete" && !!document.body')
    time.sleep(1)

def shot(name):
    data = call('Page.captureScreenshot', dict(format='png'))['data']
    (ROOT/('ui-'+name+'.png')).write_bytes(base64.b64decode(data))

if __name__ == '__main__':
    stage = sys.argv[1]
    call('Page.enable')
    call('Emulation.setDeviceMetricsOverride', dict(width=1366, height=768, deviceScaleFactor=1, mobile=False))
    go('/')
    shot(stage+'-start')
    go('/designs')
    wait('document.querySelectorAll(".design-card").length > 0')
    if stage == 'after':
        wait('Array.from(document.querySelectorAll(".design-card .card-status")).every(e=>e.textContent!=="Loading")')
    shot(stage+'-library')
    cases = json.loads((ROOT/'ui-cleanup-cases.json').read_text())
    go(cases['text']['page'])
    wait('window.embroideryStudio && window.embroideryStudio.hasPlayback()')
    if stage == 'before':
        ev('document.querySelector("[data-view=original]").click()')
        shot(stage+'-edit')
        shot(stage+'-settings-closed')
        ev('document.querySelector("[data-view=stitched]").click()')
        shot(stage+'-check')
        ev('document.querySelector(".inspector").scrollTop=10000')
        shot(stage+'-download')
        shot(stage+'-settings-expert')
    else:
        for step in ('edit', 'check', 'download'):
            ev(f'document.querySelector("[data-workflow={step}]").click()')
            time.sleep(.3)
            shot(stage+'-'+step)
        ev('document.querySelector("[data-workflow=edit]").click()')
        shot(stage+'-settings-closed')
        ev('document.getElementById("workflowExpert").open=true;document.querySelector(".inspector").scrollTop=10000')
        shot(stage+'-settings-expert')
    print('Screenshots saved for '+stage, flush=True)
