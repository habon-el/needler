"""Isolated browser acceptance; synthetic artwork, no customer files edited."""
import base64
import json
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from werkzeug.serving import make_server
from embroiderly.web import create_app
from test_piece_layout import make_image,sample


def main():
    with tempfile.TemporaryDirectory(prefix='pieces-browser-') as directory:
        root=Path(directory);app=create_app(root)
        make_image(root/'work/uploads/pieces.png')
        _,options=sample()
        (root/'work/decisions/pieces.png.preparation.json').write_text(json.dumps(options))
        server=make_server('127.0.0.1',5064,app,threaded=True)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        browser=subprocess.Popen(['chromium','--headless','--no-sandbox','--disable-gpu','--remote-debugging-port=9229','--remote-allow-origins=*','--user-data-dir='+str(root/'browser'),'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            time.sleep(2)
            from browser_helpers import call,ev,wait
            call('Emulation.setDeviceMetricsOverride',dict(width=1440,height=1000,deviceScaleFactor=1,mobile=False))
            call('Page.navigate',dict(url='http://127.0.0.1:5064/artwork/pieces.png'))
            wait("!!window.PiecePanel && !embroideryStudio.isBusy() && !!document.querySelector('.piece-select')")
            ev("document.querySelector('.piece-layers details').open=true;document.querySelector('.piece-select').click()")
            assert ev("document.getElementById('pieceW').value")=='40.0'
            output=Path('outputs/piece-panel-verification');output.mkdir(parents=True,exist_ok=True)
            def screenshot(name):
                (output/name).write_bytes(base64.b64decode(call('Page.captureScreenshot',dict(format='png'))['result']['data']))
            screenshot('simple.png')
            ev("document.getElementById('pieceAdvanced').click()")
            screenshot('advanced.png')
            ev("document.getElementById('confirmed').checked=true;document.getElementById('pieceW').value='20';document.getElementById('pieceW').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}))")
            wait("!embroideryStudio.isBusy() && document.getElementById('pieceH').value==='20.0'",timeout=90)
            assert ev('embroideryStudio.hasPlayback()')
            ev("document.getElementById('undo').click()")
            wait("!embroideryStudio.isBusy() && document.getElementById('pieceW').value==='40.0'",timeout=90)
            ev("document.querySelector('.piece-select').click()")
            point=ev("(()=>{const c=document.getElementById('prepared'),r=c.getBoundingClientRect(),a=embroideryStudio.piecePoint({clientX:r.left,clientY:r.top},c),b=embroideryStudio.piecePoint({clientX:r.left+1,clientY:r.top},c),s=1/(b[0]-a[0]);return {x:r.left+(180-a[0])*s,y:r.top+(180-a[1])*s,s}})()")
            for kind,x,y,buttons in [('mousePressed',point['x'],point['y'],1),('mouseMoved',point['x']+10*point['s'],point['y']+5*point['s'],1)]:
                call('Input.dispatchMouseEvent',dict(type=kind,x=x,y=y,button='left',buttons=buttons,clickCount=1))
            assert ev("document.getElementById('pieceX').value")=='2.0'
            assert ev("document.getElementById('pieceY').value")=='1.0'
            call('Input.dispatchMouseEvent',dict(type='mouseReleased',x=point['x']+10*point['s'],y=point['y']+5*point['s'],button='left',buttons=0,clickCount=1))
            wait("!embroideryStudio.isBusy() && Math.abs(embroideryStudio.pieceReport().pieces[0].x_mm-2)<.001",timeout=90)
            ev("document.getElementById('undo').click()")
            wait("!embroideryStudio.isBusy() && document.getElementById('pieceX').value==='0.0'",timeout=90)
            ev("document.getElementById('pieceX').value='-13.1';document.getElementById('pieceX').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}))")
            wait("!embroideryStudio.isBusy() && Math.abs(embroideryStudio.pieceReport().pieces[0].x_mm+13.1)<.001",timeout=90)
            ev("document.getElementById('undo').click()")
            wait("!embroideryStudio.isBusy() && document.getElementById('pieceX').value==='0.0'",timeout=90)
            ev("document.getElementById('pieceLock').click()")
            wait("!embroideryStudio.isBusy() && document.getElementById('pieceLock').getAttribute('aria-label')==='Unlock piece'")
            assert ev("document.getElementById('pieceW').disabled")
            ev("document.getElementById('pieceLock').click()")
            wait("!embroideryStudio.isBusy() && !document.getElementById('pieceW').disabled")
            ev("document.getElementById('pieceW').value='bad';document.getElementById('pieceW').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}))")
            assert ev("document.getElementById('pieceW').value")=='40.0'
            ev("document.getElementById('pieceW').value='0.5';document.getElementById('pieceW').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}))")
            wait("!embroideryStudio.isBusy() && document.getElementById('pieceAudit').textContent.includes('RED')")
            assert ev("embroideryStudio.pieceReport().pieces.length")==1
            assert not ev('embroideryStudio.hasPlayback()')
            ev("document.getElementById('undo').click()")
            wait("!embroideryStudio.isBusy() && document.getElementById('pieceW').value==='40.0'",timeout=90)
            ev("document.getElementById('openSettings').click()")
            wait("!document.querySelector('select[name=units]').disabled")
            ev("document.querySelector('select[name=units]').value='in';document.querySelector('select[name=units]').dispatchEvent(new Event('change'))")
            wait("document.documentElement.dataset.units==='in'")
            assert ev("document.getElementById('pieceW').value")=='1.575'
            ev("document.querySelector('[data-close]').click()")
            call('Emulation.setDeviceMetricsOverride',dict(width=390,height=844,deviceScaleFactor=1,mobile=False))
            assert ev('document.documentElement.scrollWidth<=innerWidth')
            screenshot('narrow.png')
            print('PASS: Simple/Advanced, 40→20 linked resize, playback, Undo, lock/unlock, invalid input, tiny red retained, inches, 390px.')
            from PIL import Image,ImageDraw
            from embroiderly.preparation import prepare
            many=Image.new('RGBA',(400,400));draw=ImageDraw.Draw(many)
            for number in range(26):
                x=12+(number%6)*60;y=12+(number//6)*75
                draw.rectangle((x,y,x+35,y+35),fill=(30,70,140,255))
            source=root/'work/uploads/many.png';many.save(source)
            (root/'work/decisions/many.png.preparation.json').write_text(json.dumps(options))
            call('Emulation.setDeviceMetricsOverride',dict(width=1440,height=1000,deviceScaleFactor=1,mobile=False))
            call('Page.navigate',dict(url='http://127.0.0.1:5064/artwork/many.png'))
            wait("!!window.PiecePanel && !embroideryStudio.isBusy() && document.querySelectorAll('.piece-row').length===26")
            assert ev("document.querySelectorAll('#pieceList > details').length")==3
            assert ev("document.querySelectorAll('#pieceList > details[open]').length")==0
            assert ev("[...document.querySelectorAll('.piece-row')].filter(r=>r.checkVisibility()).length")==0
            screenshot('grouped-26.png')
            _,_,r=prepare(source,options);parts=r['piece_layout']['pieces']
            named={**options,'piece_edits':{parts[0]['id']:{'name':'Eye','group':'Head / Eyes'},parts[1]['id']:{'name':'Nose','group':'Head / Nose'}}}
            (root/'work/decisions/many.png.preparation.json').write_text(json.dumps(named))
            call('Page.navigate',dict(url='http://127.0.0.1:5064/artwork/many.png'))
            wait("!!window.PiecePanel && !embroideryStudio.isBusy() && !!document.querySelector('[data-group=Head]')")
            ev("document.querySelector('[data-group=Head]').open=true;document.getElementById('confirmed').checked=true;document.querySelector('[data-group=Head] > .piece-group-actions button[aria-label]').click()")
            wait("!embroideryStudio.isBusy() && embroideryStudio.pieceReport().pieces.filter(p=>!p.visible).length===2",timeout=120)
            assert ev("embroideryStudio.pieceReport().pieces.length")==26
            print('PASS: 26 rows become 3 collapsed groups; nested Head eye hides both children, retaining all 26 pieces.')
        finally:
            browser.terminate();browser.wait(timeout=15);server.shutdown()


if __name__=='__main__':main()
