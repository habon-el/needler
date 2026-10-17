"""Bounded source scan, not an assertion that every match is an embroidery fact.

Raw term matches deliberately include labels, comments and identifiers so a
reviewer can see exclusions rather than trusting an artificially low count.
"""
import ast
import json
import re
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
units=re.compile(r'\d[\d .–²/—-]*(?:mm|inch|cm|°)')
terms=re.compile(r'\b(?:satin|tatami|underlay|density|pucker\w*|stabiliz\w*|stabilis\w*|thread|sewability|stitch|embroidery|fill)\b',re.I)
matches=[];python_messages=[]
for path in sorted((ROOT/'src/embroiderly').rglob('*')):
    if path.suffix not in ('.py','.js','.html'):continue
    text=path.read_text();relative=str(path.relative_to(ROOT))
    for number,line in enumerate(text.splitlines(),1):
        if units.search(line) or terms.search(line):
            matches.append({'file':relative,'line':number,'numeric_unit':bool(units.search(line)),'text':line})
    if path.suffix!='.py' or path.stem in ('export','simulation','knowledge_messages'):continue
    tree=ast.parse(text);parents={c:n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}
    for node in ast.walk(tree):
        if not isinstance(node,(ast.Constant,ast.JoinedStr)) or isinstance(parents.get(node),ast.JoinedStr):continue
        if isinstance(node,ast.Constant) and not isinstance(node.value,str):continue
        value=node.value if isinstance(node,ast.Constant) else ''.join(v.value if isinstance(v,ast.Constant) else '{}' for v in node.values)
        recommendation=path.stem=='regions' and any(s in value for s in ('interpreted as unstitched','linework:','provisional size','coverage method','conservative default'))
        if not units.search(value) and not recommendation:continue
        if isinstance(parents.get(node),ast.Expr):continue
        values={};parts=[]
        if isinstance(node,ast.JoinedStr):
            for v in node.values:
                if isinstance(v,ast.Constant):parts.append(v.value.replace('{','{{').replace('}','}}'))
                else:
                    key='v'+str(len(values));values[key]=ast.unparse(v.value)
                    spec=''.join(x.value for x in v.format_spec.values) if v.format_spec else ''
                    parts.append('{'+key+('!'+chr(v.conversion) if v.conversion!=-1 else '')+(':'+spec if spec else '')+'}')
            value=''.join(parts)
        python_messages.append({'file':relative,'line':node.lineno,'old':ast.get_source_segment(text,node),'text':value,'values':values})
report={'scope':'All src/embroiderly Python, JavaScript and HTML; excludes JSON knowledge data, tests and vendor dependencies.',
        'numeric_unit_lines':sum(r['numeric_unit'] for r in matches),'raw_term_or_unit_lines':len(matches),
        'python_numeric_messages_and_region_recommendations':python_messages,'raw_matches':matches,
        'limitation':'Raw matches are candidates, not a reviewed count of facts. JS/HTML and nonnumeric prose still require classification.'}
if len(sys.argv)>1:
    (ROOT/'outputs'/sys.argv[1]).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(python_messages))
