"""Real native text check/save/download, with isolated temporary app/browser."""
if __name__ == '__main__':
    from browser_workspace_isolated import main
    main(('browser_native_lettering.py',))
    raise SystemExit

import base64
from pathlib import Path
from browser_helpers import call, ev, wait

call('Emulation.setDeviceMetricsOverride',dict(width=1440,height=1000,deviceScaleFactor=1,mobile=False))
call('Page.navigate',dict(url=WORKSPACE_URL))
wait("!!window.embroideryStudio && !embroideryStudio.isBusy()")
before=ev('JSON.stringify(embroideryStudio.snapshot())')
ev("document.getElementById('textTool').click()")
wait("document.getElementById('letteringStatus').textContent.startsWith('Preview ready')")
assert ev("document.getElementById('letteringArtworkOptions').open") is False
ev("document.getElementById('letteringWords').value='jesus is\\nkings';document.getElementById('letteringWords').dispatchEvent(new Event('input',{bubbles:true}));document.getElementById('nativeCheck').click()")
assert ev("document.getElementById('nativeCheck').disabled")
wait("!document.getElementById('nativeCheck').disabled", timeout=260)
result=ev("document.getElementById('nativeResult').textContent")
assert 'DST: 0 short, 0 long, 0 crossings' in result,result
assert 'PES: 0 short, 0 long, 0 crossings' in result,result
assert ev("document.getElementById('nativeDownloads').hidden")
assert not ev("document.getElementById('nativeApprove').disabled")
ev("document.getElementById('nativeApprove').click()")
wait("!document.getElementById('nativeDownloads').hidden")
bookmark=ev("document.getElementById('nativeBookmark').href")
ev("document.getElementById('nativeDst').click()")
wait("document.getElementById('nativeStatus').textContent.startsWith('DST file checked')")
ev("document.getElementById('nativePes').click()")
wait("document.getElementById('nativeStatus').textContent.startsWith('PES file checked')")
ev("document.getElementById('nativePreview').scrollIntoView({block:'center'})")
Path('outputs/native-lettering-desktop.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',dict(format='png'))['result']['data']))
assert ev('JSON.stringify(embroideryStudio.snapshot())')==before
print('PASS: native check, preview, explicit save, real DST/PES download, unchanged artwork:',result)

# Reload saved immutable recipe through a bookmark; no tracing/regeneration.
call('Page.navigate',dict(url=bookmark))
wait("!!window.NativeWorkspace && embroideryStudio.hasPlayback() && !document.getElementById('nativeDownloads').hidden")
assert ev("document.getElementById('letteringWords').value")=='jesus is\nkings'
ev("document.getElementById('nativeWidth').value='20';document.getElementById('nativeWidth').dispatchEvent(new Event('input',{bubbles:true}))")
assert ev("document.getElementById('nativeDownloads').hidden && document.getElementById('nativePreview').hidden")
ev("document.getElementById('nativeCheck').click()")
wait("!document.getElementById('nativeCheck').disabled",timeout=260)
assert ev("document.getElementById('nativeApprove').disabled")
assert ev("document.getElementById('nativeFit').textContent.startsWith('Too wide:')")
print('PASS: bookmark restores text; width edit invalidates downloads; too-wide words stay unscaled/unapproved.')

# A slow reply must not approve words edited after the request was sent.
ev("window.nativeRealFetch=window.fetch;window.fetch=(url,options)=>url==='/lettering/native/check'?new Promise(resolve=>{window.finishNativeTest=()=>resolve(new Response('{}',{status:200,headers:{'Content-Type':'application/json'}}));}):window.nativeRealFetch(url,options)")
ev("document.getElementById('nativeWidth').value='50';document.getElementById('nativeWidth').dispatchEvent(new Event('input',{bubbles:true}));document.getElementById('nativeCheck').click()")
assert ev("document.getElementById('nativeCheck').disabled")
ev("document.getElementById('letteringWords').value='New words';document.getElementById('letteringWords').dispatchEvent(new Event('input',{bubbles:true}));window.finishNativeTest()")
wait("!document.getElementById('nativeCheck').disabled")
assert ev("document.getElementById('nativePreview').hidden && document.getElementById('nativeDownloads').hidden && document.getElementById('nativeApprove').disabled")
ev("window.fetch=window.nativeRealFetch")
ev("document.getElementById('letteringWords').value='Hello 🦉';document.getElementById('letteringWords').dispatchEvent(new Event('input',{bubbles:true}));document.getElementById('nativeCheck').click()")
wait("!document.getElementById('nativeCheck').disabled")
assert ev("document.getElementById('nativeStatus').textContent.includes('does not contain')")
assert ev("document.getElementById('letteringWords').value")=='Hello 🦉'
print('PASS: slow stale reply cannot approve changed text; unsupported glyph error stays readable and words are preserved.')


call('Emulation.setDeviceMetricsOverride',dict(width=390,height=844,deviceScaleFactor=1,mobile=False))
assert ev("document.documentElement.scrollWidth<=innerWidth+1")
ev("document.getElementById('nativeHeight').value='3';document.getElementById('nativeCheck').click()")
assert ev("document.activeElement.id")=='nativeHeight'
assert ev("document.getElementById('nativeHeight').getAttribute('aria-invalid')")=='true'
ev("document.getElementById('nativeStatus').scrollIntoView({block:'center'})")
Path('outputs/native-lettering-mobile.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',dict(format='png'))['result']['data']))
ev("document.getElementById('textTool').click()")
wait("document.activeElement.id==='letteringWords'")
print('PASS: narrow workspace reflow; invalid size focuses field; Text tool focuses words.')
