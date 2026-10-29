from pathlib import Path
import subprocess

def test_display_labels_do_not_change_stored_values():
    script=Path('src/embroiderly/static/ui-language.js').resolve()
    subprocess.run(['node','-e',"""
const assert=require('node:assert/strict'),{label}=require(process.argv[1]);
assert.equal(label('Original',true),'Artwork');
assert.equal(label('Artwork',true),'Plan');
assert.equal(label('Artwork'), 'Artwork');
assert.equal(label('Regions: 4'), 'Objects: 4');
assert.equal(label('Cut: red cross'), 'Trim: red cross');
assert.equal(label('Drop'), 'Remove');
assert.equal(label('mask_holes_mm2'), 'mask_holes_mm2');
""",str(script)],check=True)


def test_only_changed_nodes_are_relabelled():
    # Walking the whole page on every change froze the studio during playback.
    script=Path('src/embroiderly/static/ui-language.js').resolve()
    subprocess.run(['node','-e',"""
const assert=require('node:assert/strict'),{roots}=require(process.argv[1]);
const text={nodeType:3},card={nodeType:1},other={nodeType:1};
assert.deepEqual(roots([{type:'characterData',target:text},{type:'characterData',target:text}]),[text]);
assert.deepEqual(roots([{type:'childList',target:other,addedNodes:[card]},{type:'attributes',target:other}]),[card]);
assert.deepEqual(roots([{type:'childList',target:other,addedNodes:[]}]),[]);
""",str(script)],check=True)
    source=script.read_text(encoding='utf-8')
    observer=source[source.index('function start()'):]
    assert 'refresh(root)' in observer and 'roots(records)' in observer
    assert 'if(next!==node.nodeValue)node.nodeValue=next' in source
