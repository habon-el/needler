import base64
from pathlib import Path
from browser_helpers import call,ev,wait

call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False})
old=ev('performance.timeOrigin')
call('Page.navigate',{'url':'http://127.0.0.1:5050/artwork/black-lines-demo-20260923.png'})
wait(f'performance.timeOrigin !== {old}')
wait('document.readyState === "complete" && !!window.embroideryStudio')
wait('!document.querySelector("#inkOnly").disabled && document.querySelector("#swatches").children.length===1')
assert ev('document.querySelector("#inkOnly").checked')
ev('document.querySelector("[data-topic=colours]").click();document.querySelector("[data-view=prepared]").click()')
assert ev('window.embroideryStudio.snapshot().ink_only')
ev('document.querySelector("#inkOnly").click()')
wait('!document.querySelector("#inkOnly").disabled && document.querySelector("#swatches").children.length>1')
assert not ev('window.embroideryStudio.snapshot().ink_only')
ev('document.querySelector("#inkOnly").click()')
wait('!document.querySelector("#inkOnly").disabled && document.querySelector("#swatches").children.length===1')
ev('document.querySelector("[data-view=stitched]").click()')
wait('!document.querySelector("#run").disabled')
ev('document.querySelector("#run").click()')
wait('Number(document.querySelector("#timeline").value)>0')
ev('document.querySelector("#finish").click()')
assert ev('document.querySelector("#timeline").value===document.querySelector("#timeline").max')
shot=call('Page.captureScreenshot',{'format':'png'})['result']['data']
(Path(__file__).resolve().parents[1]/'outputs/black-lines-demo-20260923.png').write_bytes(base64.b64decode(shot))
print('PASS: persisted black-only intent; toggle restores normal colours; toggling back removes white; current saved playback advances and finishes.')
