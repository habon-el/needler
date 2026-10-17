"""Before/after export gate. Run baseline before UI commits, verify after them."""
import hashlib,json,sys
from pathlib import Path
import pyembroidery as emb
from embroiderly.demo import sample_design
from embroiderly.export import export_design
from embroiderly.model import Design,Thread,Command,CommandKind

ROOT=Path(__file__).resolve().parents[1]
directory=ROOT/'work'/'workspace-boundary'
mode=sys.argv[1]
destination=directory/mode
destination.mkdir(parents=True,exist_ok=False)
export_design(sample_design(),destination,'shape')
# Simple hand-drawn L: a text-path fixture, not a font digitizing capability.
text=Design(threads=(Thread('#000000','black'),),commands=tuple(Command(CommandKind.STITCH,x,y) for x,y in [(0,0),(0,2),(0,4),(2,4),(4,4)]))
export_design(text,destination,'text-L')
photo=ROOT/'work/inkstitch-preview/prepared_4f845edb84f70f4d8c2d8f6d/design.pes'
pattern=emb.EmbPattern(str(photo))
emb.write_pes(pattern,str(destination/'photographic.pes'),{'version':6})
emb.write_dst(pattern,str(destination/'photographic.dst'))
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
hashes={p.name:digest(p) for p in destination.iterdir() if p.suffix in ('.pes','.dst')}
# Verify algorithm files separately: export equality alone cannot prove segmentation unchanged.
algorithms={str(p.relative_to(ROOT)):digest(p) for p in (ROOT/'src/embroiderly').glob('*.py') if p.name not in ('web.py',)}
record={'exports':hashes,'algorithms':algorithms,'photo_input':digest(photo),'scope':'deterministic shape and text-path export, photographic PES re-export; not an end-to-end segmentation claim'}
(destination/'manifest.json').write_text(json.dumps(record,indent=2))
if mode!='baseline':
    original=json.loads((directory/'baseline/manifest.json').read_text())
    assert record==original,'BOUNDARY FAILED: export or algorithm bytes differ; stop and report'
print(json.dumps(record,indent=2))
