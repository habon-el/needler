"""Settings UI test; restores the user's preferences after all mutations."""
import base64
import json
from pathlib import Path
import requests
from browser_helpers import call, ev, wait

base = 'http://127.0.0.1:5050'
original = requests.get(base + '/api/settings', timeout=10).json()['values']
out = Path(__file__).resolve().parents[1] / 'outputs'
try:
    call('Emulation.setDeviceMetricsOverride', {'width':1440,'height':1000,'deviceScaleFactor':2,'mobile':False})
    old = ev('performance.timeOrigin')
    call('Page.navigate', {'url':base + '/artwork/015d15d2453c4aff968dbf6218fbf691.png'})
    wait(f'performance.timeOrigin !== {old}')
    wait('!!document.querySelector("#openSettings") && !document.querySelector(".settings-panel select").disabled')
    snapshot = ev('JSON.stringify(window.embroideryStudio.snapshot())')
    ev('document.querySelector("#openSettings").focus(); document.querySelector("#openSettings").click()')
    wait('!document.querySelector(".settings-panel select").disabled')
    for theme in ['dark', 'light', 'system']:
        ev(f'''(() => {{ const s=document.querySelector('[name="theme"]');s.value={json.dumps(theme)};s.dispatchEvent(new Event('change')); }})()''')
        wait('document.querySelector(".settings-feedback").textContent === "Saved on this computer"')
        assert requests.get(base + '/api/settings', timeout=10).json()['values']['theme'] == theme
        if theme != 'system':
            assert ev('document.documentElement.dataset.theme') == theme
        if theme == 'dark':
            shot = call('Page.captureScreenshot', {'format':'png'})['result']['data']
            (out / 'settings-dark-2x.png').write_bytes(base64.b64decode(shot))
    call('Emulation.setEmulatedMedia', {'features':[{'name':'prefers-color-scheme','value':'dark'}]})
    wait('document.documentElement.dataset.theme === "dark"')
    call('Emulation.setEmulatedMedia', {'features':[{'name':'prefers-color-scheme','value':'light'}]})
    wait('document.documentElement.dataset.theme === "light"')
    assert ev('JSON.stringify(window.embroideryStudio.snapshot())') == snapshot
    call('Input.dispatchKeyEvent', {'type':'keyDown','key':'Escape','code':'Escape','windowsVirtualKeyCode':27})
    call('Input.dispatchKeyEvent', {'type':'keyUp','key':'Escape','code':'Escape','windowsVirtualKeyCode':27})
    wait('!document.querySelector(".settings-panel").open')
    assert ev('document.activeElement.id') == 'openSettings'
    call('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':2,'mobile':True})
    ev('document.querySelector("#openSettings").click()')
    wait('!document.querySelector(".settings-panel select").disabled')
    assert ev('document.querySelector(".settings-panel").getBoundingClientRect().width <= innerWidth')
    # A stale revision is surfaced, not silently retried over another window.
    current = requests.get(base + '/api/settings', timeout=10).json()
    requests.patch(base + '/api/settings', json={'values':{'density':'compact'},'revision':current['revision']}, timeout=10).raise_for_status()
    ev('document.querySelector("[name=theme]").dispatchEvent(new Event("change"))')
    wait('document.querySelector(".settings-feedback").textContent.includes("another window")')
    assert not ev('document.querySelector("[data-retry]").hidden')
    print('PASS: theme saves, live system theme, immutable design, Escape/focus, narrow modal, conflict recovery')
finally:
    current = requests.get(base + '/api/settings', timeout=10).json()
    requests.patch(base + '/api/settings', json={'values':original,'revision':current['revision']}, timeout=10).raise_for_status()
    call('Emulation.setEmulatedMedia', {'features':[]})
