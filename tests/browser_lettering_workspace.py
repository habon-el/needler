"""Real typed-letter workspace integration, on an isolated app/browser."""
if __name__ == '__main__':
    from browser_workspace_isolated import main
    main(('browser_lettering_workspace.py',))
    raise SystemExit

import base64
from pathlib import Path
from browser_helpers import call, ev, wait

call('Emulation.setDeviceMetricsOverride',dict(width=1440,height=1000,deviceScaleFactor=1,mobile=False))
call('Page.navigate',dict(url=WORKSPACE_URL))
wait("!!window.embroideryStudio && !embroideryStudio.isBusy() && !!document.getElementById('textTool')")
ev("document.getElementById('textTool').click()")
wait("document.getElementById('letteringStatus').textContent.startsWith('Preview ready')")
ev("document.getElementById('letteringWords').value='jesus is\\nkings';document.getElementById('letteringWords').dispatchEvent(new Event('input',{bubbles:true}));document.getElementById('nativeCheck').click()")
wait("!document.getElementById('nativeCheck').disabled",timeout=260)
assert not ev("document.getElementById('nativeApprove').disabled")
ev("document.getElementById('nativeApprove').click()")
wait("!document.getElementById('nativeDownloads').hidden")
url=ev("document.getElementById('nativeWorkspaceLink').href")
call('Page.navigate',dict(url=url))
wait("!!window.NativeWorkspace && embroideryStudio.hasPlayback() && !document.getElementById('exportDst').hidden",timeout=60)
assert ev("document.getElementById('letteringDialog').open") is False
assert ev("document.getElementById('letteringWords').value")=='jesus is\nkings'
assert ev("document.getElementById('designSize').textContent").endswith('stitched text')
print('PASS: saved native text opens in the main canvas:',ev("document.getElementById('designSize').textContent"))
Path('outputs/lettering-workspace-desktop.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',dict(format='png'))['result']['data']))

# Capture all mutation routes: none may be /artwork, /lettering/create or image preparation.
ev("window.textFetch=window.fetch;window.textRequests=[];window.fetch=(url,opts)=>{window.textRequests.push(String(url));return window.textFetch(url,opts);}")
ev("document.getElementById('run').click()")
assert ev("document.getElementById('run').textContent.includes('Pause')")
ev("document.getElementById('finish').click();document.getElementById('exportDst').click()")
wait("document.getElementById('status').textContent.startsWith('DST file checked')")
# A release failure stays in-page and preserves the words; never open raw JSON.
ev("window.capturedFetch=window.fetch;window.fetch=(url,opts)=>String(url).endsWith('/download/dst')?Promise.resolve(new Response(JSON.stringify({error:'Test release refusal: rebuild these stitches.'}),{status:422,headers:{'Content-Type':'application/json'}})):window.capturedFetch(url,opts);document.getElementById('exportDst').click()")
wait("document.getElementById('status').textContent.includes('Download not released. Test release refusal')")
assert ev("location.pathname.startsWith('/text/') && document.getElementById('letteringWords').value==='jesus is\\nkings'")
ev("window.fetch=window.capturedFetch")
print('PASS: refused download stays in-page, preserves words, and opens no JSON error page.')
ev("document.getElementById('nativeHeight').value='4';document.getElementById('nativeHeight').dispatchEvent(new Event('input',{bubbles:true}))")
assert ev("!embroideryStudio.hasPlayback() && document.getElementById('exportDst').hidden && document.getElementById('save').disabled")
ev("document.getElementById('stitch').click()")
wait("embroideryStudio.hasPlayback() && !document.getElementById('stitch').disabled",timeout=260)
assert ev("document.getElementById('nativeHeight').value")=='4'
assert ev("document.getElementById('exportDst').hidden")
ev("document.getElementById('save').click()")
wait("!document.getElementById('exportDst').hidden",timeout=40)
ev("document.getElementById('exportPes').click()")
wait("document.getElementById('status').textContent.startsWith('PES file checked')")
requests=ev('window.textRequests')
assert not any('/artwork/' in p or '/lettering/create' in p or '/studio-export/' in p for p in requests),requests
print('PASS: main Update stitches regenerates the font; Save and downloads use that native plan. No raster calls:',requests)

# Undo a size edit, then regenerate. Unsupported sizes preserve words and block export.
ev("document.getElementById('undo').click()")
assert ev("document.getElementById('nativeHeight').value")=='5'
assert ev("document.getElementById('exportDst').hidden")
ev("document.getElementById('nativeHeight').value='3';document.getElementById('nativeHeight').dispatchEvent(new Event('input',{bubbles:true}));document.getElementById('stitch').click()")
assert ev("document.activeElement.id")=='nativeHeight'
assert ev("document.getElementById('nativeHeight').getAttribute('aria-invalid')")=='true'
assert ev("document.getElementById('letteringWords').value")=='jesus is\nkings'
print('PASS: resize Undo; unsupported size stays explicit, no substitution, export invalidated.')

call('Emulation.setDeviceMetricsOverride',dict(width=390,height=844,deviceScaleFactor=1,mobile=False))
ev("document.getElementById('nativeHeight').scrollIntoView({block:'center'})")
assert ev('document.documentElement.scrollWidth<=innerWidth+1')
Path('outputs/lettering-workspace-mobile.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',dict(format='png'))['result']['data']))
print('PASS: narrow workspace controls remain reachable.')
