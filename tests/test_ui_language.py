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
assert.equal(label('Ink/Stitch trial'), 'Stitch generation');
assert.equal(label('mask_holes_mm2'), 'mask_holes_mm2');
""",str(script)],check=True)
