"""Explicit baseline update + fail-closed verification, including web and knowledge.

--record is a reviewed maintenance action, never called by ordinary tests.
The six original export hashes must still match even when recording modules.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import pyembroidery as emb
from embroiderly.demo import sample_design
from embroiderly.export import export_design
from embroiderly.model import Design,Thread,Command,CommandKind

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'tests/module-boundary.json'
digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()


def current():
    photo=ROOT/'work/inkstitch-preview/prepared_4f845edb84f70f4d8c2d8f6d/design.pes'
    if not photo.is_file():raise SystemExit('Photographic export fixture is unavailable; verification cannot run.')
    with tempfile.TemporaryDirectory(prefix='embroiderly-boundary-') as folder:
        target=Path(folder);export_design(sample_design(),target,'shape')
        design=Design(threads=(Thread('#000000','black'),),commands=tuple(Command(CommandKind.STITCH,x,y) for x,y in [(0,0),(0,2),(0,4),(2,4),(4,4)]))
        export_design(design,target,'text-L')
        pattern=emb.EmbPattern(str(photo))
        emb.write_pes(pattern,str(target/'photographic.pes'),{'version':6})
        emb.write_dst(pattern,str(target/'photographic.dst'))
        exports={p.name:digest(p) for p in sorted(target.iterdir()) if p.suffix in ('.pes','.dst')}
    paths=sorted((ROOT/'src/embroiderly').rglob('*.py'))+sorted((ROOT/'src/embroiderly/knowledge').rglob('*.json'))
    return {'exports':exports,'photo_input':digest(photo),
            'modules_and_knowledge':{str(p.relative_to(ROOT)):digest(p) for p in paths}}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--record',action='store_true');args=parser.parse_args()
    result=current()
    if args.record:
        original=json.loads((ROOT/'work/workspace-boundary/baseline/manifest.json').read_text())
        assert result['exports']==original['exports'] and result['photo_input']==original['photo_input'], 'Cannot bless an export regression'
        BASE.write_text(json.dumps(result,indent=2)+'\n')
        print('RECORDED current modules and knowledge; all six original exports byte-identical.')
    else:
        expected=json.loads(BASE.read_text())
        assert result==expected,'BOUNDARY FAILED: current module, knowledge or export hashes differ from committed baseline'
        print('PASS: all modules/knowledge match baseline; six exports byte-identical.')
