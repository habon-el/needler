"""Reuse verified existing routing only for bijective thread substitutions."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from .engine_cache import lookup

def geometry(svg):
    root=ET.parse(svg).getroot()
    shapes={}
    root_attributes=dict(root.attrib)
    for node in root:
        if node.tag.split('}')[-1]=='metadata':
            root_attributes['metadata']=ET.tostring(node,encoding='unicode')
            continue
        if node.tag.split('}')[-1] in ('defs','use'):
            # Origin commands are geometry: compare them exactly, never ignore them.
            root_attributes.setdefault('commands',[]).append(ET.tostring(node,encoding='unicode'))
            continue
        if node.tag.split('}')[-1]!='path':raise ValueError('Unsupported SVG element')
        attrs=dict(node.attrib);attrs.pop('id',None)
        style=dict(part.split(':',1) for part in attrs.pop('style').split(';') if part)
        colour=style.pop('fill')
        key=json.dumps([attrs,style],sort_keys=True)
        if key in shapes:raise ValueError('Ambiguous duplicate geometry')
        shapes[key]=colour
    return root_attributes,shapes

def colour_mapping(old_svg,new_svg):
    a,old=geometry(old_svg);b,new=geometry(new_svg)
    if a!=b or old.keys()!=new.keys():return None
    mapping={}
    for shape,colour in old.items():
        target=new[shape]
        if colour in mapping and mapping[colour]!=target:return None
        mapping[colour]=target
    if len(set(mapping.values()))!=len(mapping):return None
    return mapping

def routing_policy(alpha, scale, settings):
    import hashlib
    from .engine_cache import digest
    return dict(version=1, knockout=bool(settings.get('colour_knockouts')),
                scale=float(scale), shape=list(alpha.shape),
                mask=hashlib.sha256(alpha.tobytes()).hexdigest(),
                guard=digest(Path(__file__).with_name('knockout_routing.py')),
                writer=digest(Path(__file__).with_name('machine_files.py')),
                spacing=digest(Path(__file__).with_name('stitch_spacing.py')),
                generation=digest(Path(__file__).with_name('generation_policy.py')),
                repair=digest(Path(__file__).with_name('repair_pipeline.py')),
                locks=digest(Path(__file__).with_name('lock_repair.py')),
                start_locks=digest(Path(__file__).with_name('start_lock_repair.py')),
                gaps=digest(Path(__file__).with_name('gap_repair.py')),
                fabric_presets=digest(Path(__file__).with_name('knowledge')/'generation.json'))


def reuse(directory,svg,policy=None):
    """Only completed, hash-verified engine outputs qualify; never guess routing."""
    if policy is None:return None
    for manifest in sorted(Path(directory).parent.glob('*/verified-cache.json')):
        prior=manifest.parent
        if prior==Path(directory):continue
        try:
            record=json.loads(manifest.read_text())
            if record.get('routing_policy') != policy:continue
            mapping=colour_mapping(prior/'design.svg',svg)
            if mapping is None:continue
            # Inspect inexpensive geometry first, hash every artifact only for a match.
            if lookup(prior,record['key']) is None:continue
            plan=json.loads((prior/'engine-plan.json').read_text())
            for thread in plan['threadlist']:
                old=thread['color']
                if old not in mapping:raise ValueError('Unmapped thread')
                thread['color']=mapping[old]
            return json.dumps(plan).encode(),prior/'design.pes'
        except (OSError,ValueError,KeyError,TypeError,ET.ParseError):
            continue
    return None
