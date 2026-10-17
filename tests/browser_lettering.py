"""Text studio acceptance on disposable data only."""
if __name__ == '__main__':
    from browser_workspace_isolated import main
    main(('browser_lettering.py',))
    raise SystemExit

import base64
from pathlib import Path
from browser_helpers import call, ev, wait

call('Emulation.setDeviceMetricsOverride', dict(width=1440,height=1000,deviceScaleFactor=1,mobile=False))
call('Page.navigate', dict(url=WORKSPACE_URL))
wait("!!document.getElementById('textTool') && !embroideryStudio.isBusy()")
before=ev('JSON.stringify(embroideryStudio.snapshot())')
ev("document.getElementById('textTool').click()")
wait("!document.getElementById('letteringCreate').disabled")
assert ev("document.getElementById('letteringFont').options.length>=30")
ev("document.getElementById('letteringWords').value='Baby 0689';document.getElementById('letteringWords').dispatchEvent(new Event('input'))")
wait("!document.getElementById('letteringCreate').disabled")
Path('outputs/lettering-desktop.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',dict(format='png'))['result']['data']))
ev("document.getElementById('letteringWords').value='';document.getElementById('letteringWords').dispatchEvent(new Event('input'))")
wait("document.getElementById('letteringStatus').textContent.includes('200')")
assert ev("document.getElementById('letteringCreate').disabled")
ev("document.getElementById('letteringWords').value='Hello';document.getElementById('letteringWords').dispatchEvent(new Event('input'))")
wait("!document.getElementById('letteringCreate').disabled")
call('Input.dispatchKeyEvent',dict(type='keyDown',key='Escape',code='Escape'))
wait("!document.getElementById('letteringDialog').open && document.activeElement.id==='textTool'")
ev("document.getElementById('textTool').click()")
wait("!document.getElementById('letteringCreate').disabled")
assert ev("document.getElementById('letteringWords').value==='Hello'")
ev("document.getElementById('letteringCreate').click()")
wait("!document.getElementById('letteringOpen').hidden")
assert before==ev('JSON.stringify(embroideryStudio.snapshot())')
url=ev("document.getElementById('letteringOpen').href")
call('Page.navigate',dict(url=url))
wait("!!document.getElementById('textTool') && !embroideryStudio.isBusy()")
ev("document.getElementById('textTool').click()")
wait("!document.getElementById('letteringCreate').disabled")
assert ev("document.getElementById('letteringWords').value==='Hello'")
call('Emulation.setDeviceMetricsOverride',dict(width=390,height=844,deviceScaleFactor=1,mobile=True))
wait('document.documentElement.scrollWidth<=innerWidth')
assert ev("document.getElementById('letteringDialog').getBoundingClientRect().width<=innerWidth")
Path('outputs/lettering-mobile.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',dict(format='png'))['result']['data']))
print('Text studio: catalogue, preview, validation, Escape, draft retention, create, reopen, non-mutation and narrow layout passed')
