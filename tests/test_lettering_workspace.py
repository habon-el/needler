"""The workspace uses the native recipe/files, not image preparation."""
import json
from pathlib import Path

import pyembroidery as emb
import pytest
from jinja2 import FileSystemLoader
from test_lettering_native import client, BODY
from embroiderly.lettering_workspace import workspace_data, register
from embroiderly.machine_files import read_pattern


def test_workspace_reads_exact_dst_without_rasterizing_or_rewriting(client, monkeypatch):
    c, store, calls = client
    data = c.post('/lettering/native/check', json=BODY).json
    folder = store/data['id']
    before = {p.name:p.read_bytes() for p in folder.iterdir() if p.is_file()}
    from embroiderly import preparation, engine
    def forbidden(*a, **kw):
        raise AssertionError('Native letters must never pass through picture processing')
    monkeypatch.setattr(preparation, 'prepare', forbidden)
    monkeypatch.setattr(engine, 'digitize', forbidden)
    view = workspace_data(folder, data['id'])
    written = read_pattern(folder/'design.dst')
    assert view['result']['recipe'] == data['recipe']
    assert view['image'].startswith('data:image/svg+xml;base64,')
    assert [(s['x'],s['y']) for s in view['playback']['steps']] == [(x/10,y/10) for x,y,_ in written.stitches]
    assert view['playback']['trim_count'] == written.count_stitch_commands(emb.TRIM)
    assert before == {p.name:p.read_bytes() for p in folder.iterdir() if p.is_file()}
    assert not list(store.rglob('*.png'))


def test_workspace_routes_and_invalid_ids(client):
    c, store, calls = client
    register(c.application, store.parent.parent)
    c.application.jinja_loader = FileSystemLoader(str(Path('src/embroiderly/templates').resolve()))
    data = c.post('/lettering/native/check', json=BODY).json
    page = c.get('/text/'+data['id'])
    assert page.status_code == 200
    assert b'window.nativeTextConfig=' in page.data
    assert b'"text": "A"' in page.data
    assert c.get('/text/not-a-recipe').status_code == 404
    assert c.get('/lettering/native/no/workspace-data').status_code == 422
    view = c.get('/lettering/native/'+data['id']+'/workspace-data')
    assert view.status_code == 200 and view.json['result']['id'] == data['id']


def test_corrupted_machine_pair_cannot_be_shown_as_checked(client):
    c, store, calls = client
    data = c.post('/lettering/native/check', json=BODY).json
    folder = store/data['id']
    (folder/'design.pes').write_bytes(b'broken')
    with pytest.raises(ValueError, match='changed since generation'):
        workspace_data(folder, data['id'])


def test_resize_uses_new_font_recipe_and_keeps_original_version(client):
    c, store, calls = client
    first = c.post('/lettering/native/check', json=BODY).json
    original = (store/first['id']/'design.dst').read_bytes()
    second = c.post('/lettering/native/check', json={**BODY,'height_mm':4}).json
    assert second['id'] != first['id']
    assert [b['height_mm'] for b in calls] == [5,4]
    assert second['approved'] is False
    assert (store/first['id']/'design.dst').read_bytes() == original
    assert json.loads((store/first['id']/'result.json').read_text())['recipe']['height_mm'] == 5


def _text_preview_run(tmp_path, steps, source=None):
    """Runs text-make.js's typing preview with a stand-in page; returns what each step left on screen."""
    import shutil, subprocess
    source = source or (Path(__file__).resolve().parents[1]/'src/embroiderly/static/text-make.js').read_text(encoding='utf-8')
    start = source.index('/* Instant letter preview')
    block = source[start:source.index('/* Every problem at once', start)]
    harness = r"""
const handlers={}, timers=[], frames=[], drawn=[];
const listen=(target)=>(type,fn)=>{(handlers[target+type]=handlers[target+type]||[]).push(fn)};
const field=(value)=>({value,addEventListener:(type,fn)=>listen('field')(type,fn)});
const fields={letteringWords:field('habonimana'),nativeFont:field('damion'),nativeHeight:field('15.8'),nativeBaseline:field('straight')};
const context={font:'',fillStyle:'',clearRect(){},fillRect(){},save(){},restore(){},translate(){},rotate(){},
 measureText:t=>({width:10*t.length,actualBoundingBoxAscent:70,actualBoundingBoxDescent:5,fontBoundingBoxAscent:80,fontBoundingBoxDescent:20}),
 fillText:t=>drawn.push(t)};
const page={clientWidth:600,clientHeight:300,offsetLeft:0,offsetTop:0,offsetParent:{},classList:{contains:()=>false},closest:()=>null};
page.parentElement={append:o=>{o.parentElement=page.parentElement},style:{}};
const document={addEventListener:listen('document'),getElementById:id=>fields[id]||null,
 querySelectorAll:()=>[page],createElement:()=>({style:{},getContext:()=>context,hidden:true}),fonts:{add(){}}};
const window={nativeTextConfig:{},addEventListener:listen('window'),embroideryStudio:{hasPlayback:()=>stitches}};
let stitches=false;
const getComputedStyle=()=>({position:'relative'});
class FontFace{load(){return Promise.resolve(this)}}
const requestAnimationFrame=fn=>{frames.push(fn);return frames.length}, cancelAnimationFrame=()=>{};
const setTimeout=fn=>timers.push(fn);
""" + block + r"""
const settle=()=>new Promise(r=>queueMicrotask(()=>queueMicrotask(()=>queueMicrotask(r))));
const fire=(key)=>(handlers[key]||[]).forEach(fn=>fn({}));
const shown=()=>drawn.some(t=>/press Make stitches/.test(t));
(async()=>{
 handlers.documentDOMContentLoaded.forEach(fn=>fn());
 const out=[];
 for(const step of STEPS){
  drawn.length=0;
  if(step==='stitches'){stitches=true;fire('documentlettering:result')}
  if(step==='timer')timers.splice(0).forEach(fn=>fn());
  if(step==='edit'){stitches=false;fire('fieldinput')}
  if(step==='resize')fire('windowresize');
  while(frames.length){await frames.shift()();await settle()}
  await settle();out.push(shown());
 }
 console.log(JSON.stringify(out));
})();
""".replace('STEPS', json.dumps(steps))
    script = tmp_path/'preview.js'
    script.write_text(harness, encoding='utf-8')
    run = subprocess.run([shutil.which('node'), str(script)], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


@pytest.mark.skipif(not __import__('shutil').which('node'), reason='needs Node')
def test_typing_preview_never_covers_current_stitches(tmp_path):
    # Saved stitches load before the delayed first preview: Compare showed the font
    # preview at its own scale, saying "press Make stitches", beside real stitches.
    assert _text_preview_run(tmp_path, ['stitches', 'timer', 'resize']) == [False, False, False]
    # Edited words clear the stitches: the preview is back until the next stitches.
    assert _text_preview_run(tmp_path, ['stitches', 'edit', 'stitches']) == [False, True, False]
    # A new page with words and no stitches yet still previews them.
    assert _text_preview_run(tmp_path, ['timer']) == [True]
