"""Trace current literal-button findings; never suppress unresolved findings."""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--audit',default='outputs/thread-surface-static-audit.json');parser.add_argument('--output',default='outputs/thread-surface-static-triage.json');args=parser.parse_args()
audit=json.loads((ROOT/args.audit).read_text())
scripts=list((ROOT/'src/embroiderly/static').glob('*.js'))
seen=Counter();rows=[]
for index,finding in enumerate(audit['findings'],1):
    path=ROOT/finding['file'];line=finding['line'];source=path.read_text().splitlines()[line-1]
    buttons=re.findall(r'<button\b[^>]*>.*?</button>',source)
    buttons=[b for b in buttons if not re.search(r'\bdisabled\b|\bonclick\b|type="submit"',b)]
    key=(str(path),line);offset=seen[key];seen[key]+=1
    button=buttons[offset] if offset<len(buttons) else ''
    match=re.search(r'\b(id|data-tool|data-view|data-library-view|data-bulk|data-demo|data-demo-play|data-stage|data-colour)="([^"]+)"',button)
    if match:
        attr,value=match.groups();needle=value if attr=='id' else '['+attr+']'
    elif 'data-cancel' in button:needle='[data-cancel]'
    elif path.stem=='library' and 'Undo' in button:needle="toast.querySelector('button')"
    else:needle='UNRESOLVED'
    hits=[f'{p.relative_to(ROOT)}:{i}' for p in [path,*scripts]
          for i,text in enumerate(p.read_text().splitlines(),1)
          if needle in text and ('onclick' in text or 'addEventListener' in text)]
    if path.stem=='machine':
        hits=[f'{path.relative_to(ROOT)}:{i}' for i,text in enumerate(path.read_text().splitlines(),1) if 'button.onclick=' in text]
    rows.append(dict(index=index,**finding,button=button,evidence=hits,
        disposition='not a problem' if hits else 'needs manual trace',
        reason='External/delegated handler found. This is source evidence, not a claim of runtime coverage.' if hits else 'Literal detector could not establish an action; not closed.'))
report=dict(source=args.audit,counts=dict(Counter(r['disposition'] for r in rows)),findings=rows)
(ROOT/args.output).write_text(json.dumps(report,indent=2)+'\n')
print(report['counts'])
for r in rows:
    if not r['evidence']:print(r['index'],r['file'],r['line'],r['button'])
