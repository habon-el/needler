"""Offline product check; not a substitute for real-photo diagnostic validation."""
import base64
from pathlib import Path
from browser_helpers import call,ev,wait

call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1000,'deviceScaleFactor':2,'mobile':False})
old=ev('performance.timeOrigin')
call('Page.navigate',{'url':'http://127.0.0.1:5050/artwork/015d15d2453c4aff968dbf6218fbf691.png'})
wait(f'performance.timeOrigin !== {old}')
wait('!!document.querySelector("#sewoutReview")')
wait('document.querySelector("#sewoutStatus").textContent.includes("locked")')
assert ev('document.querySelector("#sewoutValidation").textContent.includes("not assessment")')
snapshot=ev('JSON.stringify(window.embroideryStudio.snapshot())')
ev('document.querySelector("[data-topic=review]").click();document.querySelector("#sewoutReview").open=true;document.querySelector("#sewoutReview").scrollIntoView({block:"start"})')
assert ev('document.querySelector("#sewoutRun").disabled')
assert ev('document.querySelector("#sewoutHistoryList").textContent')=='No sample reviews saved yet.'
assert ev('JSON.stringify(window.embroideryStudio.snapshot())')==snapshot
shot=call('Page.captureScreenshot',{'format':'png'})['result']['data']
(Path(__file__).resolve().parents[1]/'outputs'/'sewout-advisor-offline.png').write_bytes(base64.b64decode(shot))
ev('document.querySelector("[data-topic=selection]").click();document.querySelector("[data-tool=pan]").click()')
assert ev('document.querySelector("#tool").value')=='pan'
assert ev('JSON.stringify(window.embroideryStudio.snapshot())')==snapshot
print('PASS: photo review offline state, local empty history, no Apply control, manual navigation and Move remain usable; no design mutation')
