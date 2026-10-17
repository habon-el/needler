"""UI-only proof: download via the running app; compare decoded machine data.

No existing output folder or installed-library source is inspected. The files
created alongside this script are the exports explicitly requested for this pass.
"""
import base64
import hashlib
import io
import json
from pathlib import Path
import sys
import time

import requests
from PIL import Image, ImageDraw
from embroiderly.machine_files import read_pattern

ROOT = Path(__file__).resolve().parent
BASE = 'http://127.0.0.1:5050'
session = requests.Session()
session.headers['Origin'] = BASE

def get(path):
    r = session.get(BASE + path, timeout=300)
    r.raise_for_status()
    return r

def post(path, body):
    r = session.post(BASE + path, json=body, timeout=300)
    if not r.ok:
        raise RuntimeError(f'{path}: {r.status_code} {r.text[:1500]}')
    return r.json()

def baseline():
    cases = {}
    for name, words, height in [('text', 'Hello World', 5), ('small-text', 'tiny', 4)]:
        result = post('/lettering/native/check', dict(text=words, font='small_font', height_mm=height,
                      available_width_mm=100, align='center', colour='#202020'))
        assert result['checks_passed'], result
        key = result['id']
        post(f'/lettering/native/{key}/approve', {'approve': True})
        cases[name] = dict(page='/text/'+key, url=f'/lettering/native/{key}/download/',
                           reports=result['reports'])
    image = Image.new('RGBA', (160, 120))
    ImageDraw.Draw(image).rectangle((30, 30, 130, 90), fill='#156958')
    data = io.BytesIO()
    image.save(data, format='PNG')
    r = session.post(BASE+'/upload', files={'image': ('UI proof rectangle.png', data.getvalue(), 'image/png')},
                     allow_redirects=False, timeout=60)
    assert r.status_code == 302, r.text
    name = r.headers['Location'].rsplit('/', 1)[-1]
    result = post('/artwork/'+name, dict(options=dict(selection='full', height_mm=40, colours=2,
        floor_mm2=0, mask_holes_mm2=0, smooth=0, simplify=0, protect_selection=True),
        digitize=True, subject_confirmed=True))
    cases['image'] = dict(page='/artwork/'+name, url='/studio-export/'+result['prepared_name']+'/')
    (ROOT/'ui-cleanup-cases.json').write_text(json.dumps(cases, indent=2))
    return cases

def exports(stage, cases):
    proof = {}
    for name, case in cases.items():
        proof[name] = {}
        for fmt in ('dst', 'pes'):
            blob = get(case['url']+fmt).content
            path = ROOT/f'ui-{stage}-{name}.{fmt}'
            path.write_bytes(blob)
            pattern = read_pattern(path)
            commands = [[float(x), float(y), int(c)] for x, y, c in pattern.stitches]
            digest = hashlib.sha256(json.dumps(commands, separators=(',', ':')).encode()).hexdigest()
            proof[name][fmt] = dict(commands=len(commands), stitch_data_sha256=digest)
            if stage == 'after':
                before = read_pattern(ROOT/f'ui-before-{name}.{fmt}')
                assert pattern.stitches == before.stitches, f'CHANGED STITCH DATA: {name} {fmt}'
    (ROOT/f'ui-{stage}-exports.json').write_text(json.dumps(proof, indent=2))
    print(json.dumps(proof, indent=2), flush=True)

if __name__ == '__main__':
    stage = sys.argv[1]
    cases = baseline() if stage == 'before' else json.loads((ROOT/'ui-cleanup-cases.json').read_text())
    exports(stage, cases)
