"""Compare real audit fixtures without modifying them; outputs go to a temp folder."""
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
import numpy as np
import pyembroidery as emb
from PIL import Image
from embroiderly.demo import sample_design
from embroiderly.export import _pattern
from embroiderly.model import Design,Thread,Command,CommandKind
from embroiderly.machine_files import write_pair,read_pattern
from embroiderly.engine import digitize
from embroiderly.release_gate import checked_bytes,ReleaseError

ROOT=Path(__file__).resolve().parents[1]
AUDIT=Path('/tmp/needlora-readonly-20260930-89kslgb3')
digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    out=Path(tempfile.mkdtemp(prefix='output-safety-final-'))
    rows=[];baseline=json.loads((ROOT/'tests/module-boundary.json').read_text())['exports']
    fixtures={'shape':_pattern(sample_design()),'text-L':_pattern(Design(threads=(Thread('#000000','black'),),commands=tuple(Command(CommandKind.STITCH,x,y) for x,y in [(0,0),(0,2),(0,4),(2,4),(4,4)])))}
    photo=ROOT/'work/inkstitch-preview/prepared_4f845edb84f70f4d8c2d8f6d/design.pes'
    fixtures['photographic']=emb.EmbPattern(str(photo))
    for name,pattern in fixtures.items():
        folder=out/name;folder.mkdir();old=folder/'old';old.mkdir();new=folder/'new';new.mkdir()
        settings={'version':6} if name=='photographic' else {}
        # Exact pre-fix writer calls, checked against the committed six hashes.
        emb.write_pes(pattern,str(old/(name+'.pes')),settings)
        emb.write_dst(pattern,str(old/(name+'.dst')))
        write_pair(pattern,new/(name+'.pes'),new/(name+'.dst'),settings)
        row={'fixture':name,'files':{}}
        for fmt in ('pes','dst'):
            before=old/(name+'.'+fmt);after=new/(name+'.'+fmt)
            assert digest(before)==baseline[before.name],('original fixture changed',before.name)
            row['files'][fmt]={'old_sha256':digest(before),'new_sha256':digest(after),'changed':before.read_bytes()!=after.read_bytes(),
                'before_trims':emb.EmbPattern(str(before)).count_stitch_commands(emb.TRIM),'after_trims':read_pattern(after).count_stitch_commands(emb.TRIM)}
        assert row['files']['pes']['after_trims']==row['files']['dst']['after_trims']
        rows.append(row)
    original=json.loads((AUDIT/'generation-results.json').read_text())
    for name in ['two-circles-normal','two-circles-knockout','hello-world-normal','hello-world-knockout','preview-tatami','preview-satin','preview-raised_satin']:
        src=AUDIT/'app/work/uploads'/(name+'.png');folder=out/name;folder.mkdir()
        source=folder/src.name;shutil.copy2(src,source);shutil.copy2(src.with_suffix('.prep.json'),source.with_suffix('.prep.json'))
        # Physical height from the audit's own recorded playback/measurement.
        old=AUDIT/'app/work/inkstitch-preview'/name
        if not (old/'playback.json').exists():old=AUDIT/'cold'/name/'result'
        reference=AUDIT/'app/work/inkstitch-preview'/name.replace('-knockout','-normal')/'playback.json'
        old_play=json.loads(reference.read_text())
        try:result=digitize(source,folder/'result',old_play['height_mm'])
        except ValueError as error:
            rows.append({'fixture':name,'generation_blocked':str(error),'before_error':original.get(name,{}).get('error')})
            continue
        row={'fixture':name,'files':{},'release':{}}
        for fmt in ('pes','dst'):
            before=old/('design.'+fmt);after=folder/'result'/('design.'+fmt)
            row['files'][fmt]={'old_sha256':digest(before) if before.exists() else None,'new_sha256':digest(after),'changed':before.read_bytes()!=after.read_bytes() if before.exists() else 'new file',
                'before_trims':emb.EmbPattern(str(before)).count_stitch_commands(emb.TRIM) if before.exists() else None,'after_trims':read_pattern(after).count_stitch_commands(emb.TRIM)}
            try:checked_bytes(folder/'result',fmt);row['release'][fmt]='released'
            except ReleaseError as error:row['release'][fmt]={'blocked':str(error),'location':error.location}
        assert row['files']['pes']['after_trims']==row['files']['dst']['after_trims']
        rows.append(row)
    # Exact original circles, normal cache first, then knockout, versus cold.
    normal=AUDIT/'app/work/uploads/two-circles-normal.png'
    selected=AUDIT/'app/work/uploads/two-circles-knockout.png'
    height=json.loads((AUDIT/'app/work/inkstitch-preview/two-circles-normal/playback.json').read_text())['height_mm']
    digitize(normal,out/'cache-warm'/'normal',height)
    digitize(selected,out/'cache-warm'/'selected',height)
    digitize(selected,out/'cache-cold'/'selected',height)
    equality={fmt:digest(out/'cache-warm/selected'/('design.'+fmt))==digest(out/'cache-cold/selected'/('design.'+fmt)) for fmt in ('pes','dst')}
    assert all(equality.values())
    report={'scope':'Exact old six hashes verified; fresh generation from original audit images; custom explicit-trim DST readback. No physical sew-out.',
            'fixtures':rows,'original_circles_warm_cold_identical':equality}
    (out/'results.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2));print('EVIDENCE',out)


if __name__=='__main__':main()
