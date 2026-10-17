"""CDP helpers for the isolated workspace test browser on port 9229."""
import json
import time
import requests
import websocket

ws = websocket.create_connection(requests.get('http://127.0.0.1:9229/json', timeout=10).json()[0]['webSocketDebuggerUrl'], origin='http://localhost:9229', timeout=20)
sequence = 0


def call(method, params):
    global sequence
    sequence += 1
    ws.send(json.dumps(dict(id=sequence, method=method, params=params)))
    while True:
        result = json.loads(ws.recv())
        if result.get('id') == sequence:
            assert not result.get('error'), result
            return result


def ev(code):
    result = call('Runtime.evaluate', dict(expression=code, returnByValue=True))['result']
    assert not result.get('exceptionDetails'), result
    return result['result'].get('value')


def wait(code, timeout=50):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if ev(code):
            return
        time.sleep(.2)
    raise AssertionError({'condition': code, 'page': ev('document.body.innerText')})
