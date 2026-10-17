"""Reproducible, per-finding source trace. Not a runtime usability claim."""
import json
import re
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
audit=json.loads((ROOT/'outputs/advisory-static-audit-20260921.json').read_text())
seen=Counter();rows=[]
owners={'artwork':'preparation.js','editor':'editor.js','library':'library.js',
        'thread_controls':'thread-controls.js','workspace':'workspace.js'}
for index,finding in enumerate(audit['findings'],1):
    path=Path(finding['file']);line=finding['line'];stem=path.stem
    row={'finding':index,**finding}
    if finding['ruleId']=='form.novalidate-missing':
        row.update(disposition='fix now',status='fixed',reason='Retained constraints; declared shared inline validation, focus and duplicate-submit guard.',
                   evidence=['src/embroiderly/static/form-validation.js:4',str(path)])
    else:
        # The saved audit predates one inserted stylesheet line in artwork.html.
        source=(ROOT/path).read_text().splitlines()[line-1+(1 if stem=='artwork' else 0)]
        buttons=re.findall(r'<button\b[^>]*>.*?</button>',source)
        buttons=[b for b in buttons if not re.search(r'\bdisabled\b|\bonclick\b|type="submit"',b)]
        key=(str(path),line);offset=seen[key];seen[key]+=1
        button=buttons[offset] if offset<len(buttons) else ''
        match=re.search(r'\b(id|data-tool|data-view|data-library-view|data-bulk)="([^"]+)"',button)
        if match:
            attr,value=match.groups();needle=value if attr=='id' else '['+attr+']'
        elif stem=='library' and 'Undo' in button:needle="toast.querySelector('button')"
        elif 'data-cancel' in button:needle='[data-cancel]'
        else:needle='UNRESOLVED'
        owner=ROOT/'src/embroiderly/static'/owners[stem] if stem in owners else ROOT/path
        hits=[f'{owner.relative_to(ROOT)}:{i}' for i,text in enumerate(owner.read_text().splitlines(),1)
              if needle in text and ('onclick' in text or 'addEventListener' in text)]
        if stem=='machine':
            hits=[f'{path}:{i}' for i,text in enumerate(owner.read_text().splitlines(),1) if 'button.onclick=' in text]
        row.update(button=button,evidence=hits,
                   disposition='not a problem' if hits else 'fix later',
                   status='source handler verified; runtime coverage separate' if hits else 'unresolved',
                   reason='External/delegated JavaScript handler exists; literal-template detector does not trace it.' if hits else 'Could not resolve handler from the saved audit snapshot; requires manual trace before closure.')
    rows.append(row)
report={'source':'advisory-static-audit-20260921.json','counts':dict(Counter(r['disposition'] for r in rows)),'findings':rows}
target=ROOT/'outputs/advisory-static-triage-20260922.json'
target.write_text(json.dumps(report,indent=2)+'\n')
print(report['counts'])
for r in rows:
    if r['disposition']=='fix later':print(r['finding'],r['file'],r['line'],r['button'])
