"""Custom fabric settings: one of the fabric presets with the user's own stitch values.

A custom fabric is {id, name, base, row_spacing_mm, satin_spacing_mm, satin_pull_mm,
fill_underlay, max_stitch_length_mm}. The user's own are kept for every design in
work/fabrics.json; the chosen one is also copied into the design settings
(fabric_custom), so a design sews the same after the saved fabric is changed or deleted."""
import json
import math
from uuid import uuid4

# Our own bounds: wide enough for any real fabric, narrow enough that a typo cannot
# make a design that jams the needle or sews bare.
LIMITS = {'row_spacing_mm': (.25, 1.0, 'Fill spacing'), 'satin_spacing_mm': (.25, .8, 'Satin spacing'),
          'satin_pull_mm': (0.0, .6, 'Pull compensation'), 'max_stitch_length_mm': (2.0, 7.0, 'Longest fill stitch')}
MAX_SAVED = 30


def check(body):
    """The custom fabric with its values checked and rounded; ValueError names the bad value."""
    from .generation_policy import presets
    if not isinstance(body, dict):
        raise ValueError('Enter a name and the stitch values for your fabric.')
    name = body.get('name')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 40:
        raise ValueError('Give the fabric a name of up to 40 characters.')
    if body.get('base') not in {r['fabric'] for r in presets()}:
        raise ValueError('Start your fabric from one of the listed fabrics.')
    fabric = dict(name=name.strip(), base=body['base'])
    if isinstance(body.get('id'), str) and body['id'].startswith('mine-') and len(body['id']) <= 20:
        fabric['id'] = body['id']
    for key, (low, high, label) in LIMITS.items():
        value = body.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f'{label} must be {low:g}–{high:g} mm.')
        fabric[key] = round(float(value), 2)
    if type(body.get('fill_underlay')) is not bool:
        raise ValueError('Choose whether fills get underlay.')
    fabric['fill_underlay'] = body['fill_underlay']
    return fabric


def saved(root):
    try:
        value = json.loads((root/'work'/'fabrics.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    return [f for f in value if isinstance(f, dict)] if isinstance(value, list) else []


def _write(root, fabrics):
    target = root/'work'/'fabrics.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(fabrics, indent=1), encoding='utf-8')
    temporary.replace(target)


def save(root, body):
    """Add a custom fabric, or replace the saved one with the same id. Returns (fabric, saved list)."""
    fabric = check(body)
    fabrics = saved(root)
    at = next((n for n, f in enumerate(fabrics) if f.get('id') == fabric.get('id')), None)
    if at is None:
        if len(fabrics) >= MAX_SAVED:
            raise ValueError(f'You can keep up to {MAX_SAVED} fabrics. Delete one first.')
        fabric['id'] = 'mine-'+uuid4().hex[:10]
        fabrics.append(fabric)
    else:
        fabrics[at] = fabric
    _write(root, fabrics)
    return fabric, fabrics


def delete(root, fabric_id):
    fabrics = saved(root)
    kept = [f for f in fabrics if f.get('id') != fabric_id]
    if len(kept) == len(fabrics):
        raise ValueError('That fabric is no longer saved.')
    _write(root, kept)
    return kept
