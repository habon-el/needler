"""Exercise real pointer gestures on disposable artwork, never the customer file."""
if __name__ == '__main__':
    from browser_workspace_isolated import main
    main(('browser_selection_rectangle.py',))
    raise SystemExit

from browser_helpers import call, ev, wait

call('Emulation.setDeviceMetricsOverride', dict(width=1440, height=1000, deviceScaleFactor=1, mobile=False))
call('Page.navigate', dict(url=WORKSPACE_URL))
wait("!!window.embroideryStudio && !embroideryStudio.isBusy() && document.getElementById('status').textContent.startsWith('Preview ready')")
ev("window.selectionRequests=0;window.originalFetch=window.fetch;window.fetch=(...args)=>{if(args[1]?.method==='POST'&&String(args[0]).startsWith('/artwork/'))selectionRequests++;return originalFetch(...args)}")
baseline = ev('JSON.stringify(embroideryStudio.snapshot())')
undo_before = ev("document.getElementById('undo').disabled")


def point(x, y):
    return ev(f"(()=>{{const c=document.getElementById('original'),r=c.getBoundingClientRect(),s=Math.min(c.width/600,c.height/500)*.92;return {{x:r.left+(c.width-600*s)/2+{x}*s,y:r.top+(c.height-500*s)/2+{y}*s}}}})()")


def mouse(kind, x, y, buttons=0):
    call('Input.dispatchMouseEvent', dict(type=kind, **point(x, y), button='left', buttons=buttons, clickCount=1))


for end in [(200, 200), (300, 200), (200.1, 200.1)]:
    mouse('mousePressed', 200, 200, 1)
    mouse('mouseMoved', *end, 1)
    mouse('mouseReleased', *end)
    assert ev('JSON.stringify(embroideryStudio.snapshot())') == baseline, 'A click/flat box must not replace the subject'
    assert ev('selectionRequests') == 0
    assert ev("document.getElementById('undo').disabled") == undo_before
    assert 'unchanged' in ev("document.getElementById('status').textContent")

mouse('mousePressed', 5, 5, 1)
mouse('mouseMoved', 590, 490, 1)
assert ev('JSON.stringify(embroideryStudio.snapshot())') == baseline, 'Rectangle remains a draft during drag'
call('Input.dispatchKeyEvent', dict(type='keyDown', key='Escape', code='Escape', windowsVirtualKeyCode=27))
mouse('mouseReleased', 590, 490)
assert ev('JSON.stringify(embroideryStudio.snapshot())') == baseline
assert ev('selectionRequests') == 0

mouse('mousePressed', 5, 5, 1)
mouse('mouseMoved', 590, 490, 1)
mouse('mouseReleased', 590, 490)
wait("selectionRequests===1 && !embroideryStudio.isBusy() && document.getElementById('status').textContent.startsWith('Preview ready')")
assert ev("embroideryStudio.snapshot().selection") == 'grabcut'
ev("document.getElementById('undo').click()")
wait("!embroideryStudio.isBusy() && document.getElementById('status').textContent.startsWith('Preview ready')")
assert ev('JSON.stringify(embroideryStudio.snapshot())') == baseline

call('Emulation.setDeviceMetricsOverride', dict(width=390, height=844, deviceScaleFactor=1, mobile=False))
ev("document.getElementById('original').scrollIntoView({block:'center'})")
mouse('mousePressed', 200, 200, 1)
mouse('mouseReleased', 200, 200)
assert ev('JSON.stringify(embroideryStudio.snapshot())') == baseline
assert ev('document.documentElement.scrollWidth<=innerWidth')
print('PASS: click/flat/tiny boxes preserve selection and history; no failed request; draft/Esc; valid drag; Undo; 390px viewport.')
