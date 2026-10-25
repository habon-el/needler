"""Hoops: sewing fields by machine brand, the user's own saved hoops, and the hoop chosen for a
design. The design keeps the chosen hoop's id (`hoop_id`) and its sewing field as placed
(`piece_hoop_mm` = [width, height]; a hoop turned 90° has them swapped).

Sizes are the usable sewing field, not the frame's outside size; machines differ, so the menu
asks the user to check their manual."""
import json
import math
import re
from uuid import uuid4

# (name, width mm, height mm) as the hoop sits on the machine.
CATALOG = {
    'Common sizes': [('10 × 10 cm', 100, 100), ('13 × 18 cm', 130, 180), ('16 × 26 cm', 160, 260),
                     ('20 × 20 cm', 200, 200), ('20 × 30 cm', 200, 300), ('24 × 35 cm', 240, 350),
                     ('36 × 20 cm', 360, 200)],
    'Brother': [('4 × 4 in', 100, 100), ('5 × 7 in', 130, 180), ('6 × 10 in', 160, 260),
                ('8 × 8 in', 200, 200), ('8 × 12 in', 200, 300), ('14 × 8 in', 360, 200)],
    'Janome': [('A', 126, 110), ('SQ14', 140, 140), ('RE20', 170, 200), ('SQ20', 200, 200), ('RE28', 200, 280)],
    'Bernina': [('Medium', 100, 130), ('Large oval', 145, 255), ('Midi', 265, 165), ('Maxi', 210, 400),
                ('Jumbo', 260, 400)],
    'Husqvarna Viking': [('100 × 100', 100, 100), ('170 × 100', 170, 100), ('240 × 150', 240, 150),
                         ('260 × 200', 260, 200), ('360 × 200', 360, 200), ('360 × 260', 360, 260)],
    'Pfaff': [('120 × 115', 120, 115), ('240 × 150', 240, 150), ('260 × 200', 260, 200),
              ('360 × 200', 360, 200), ('360 × 350', 360, 350)],
    'Singer': [('10 × 10 cm', 100, 100), ('26 × 15 cm', 260, 150)],
}
MAX_SAVED = 50
MIN_MM, MAX_MM = 10, 1000
DEFAULT = 'common-100x100'


def _slug(text):
    return re.sub('[^a-z0-9]+', '-', text.lower()).strip('-')


def listed():
    """[{brand, hoops: [{id, name, width_mm, height_mm}]}] for the menu."""
    return [dict(brand=brand, hoops=[dict(id=f'{_slug(brand.split()[0])}-{w}x{h}', name=name, width_mm=w, height_mm=h)
                                     for name, w, h in hoops])
            for brand, hoops in CATALOG.items()]


def saved(root):
    """The user's own hoops, kept for every design in work/hoops.json."""
    try:
        value = json.loads((root/'work'/'hoops.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    return [h for h in value if isinstance(h, dict)] if isinstance(value, list) else []


def _write(root, hoops):
    target = root/'work'/'hoops.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(hoops, indent=1), encoding='utf-8')
    temporary.replace(target)


def save(root, body):
    """Add one of the user's hoops: {name, width_mm, height_mm}. Returns the saved list."""
    if not isinstance(body, dict):
        raise ValueError('Enter a hoop name, width and height.')
    name = body.get('name')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 40:
        raise ValueError('Give the hoop a name of up to 40 characters.')
    size = [body.get('width_mm'), body.get('height_mm')]
    if any(type(v) not in (int, float) or not math.isfinite(v) or not MIN_MM <= v <= MAX_MM for v in size):
        raise ValueError(f'Hoop width and height must be {MIN_MM}–{MAX_MM} mm.')
    hoops = saved(root)
    if len(hoops) >= MAX_SAVED:
        raise ValueError(f'You can keep up to {MAX_SAVED} hoops. Delete one first.')
    hoops.append(dict(id='mine-'+uuid4().hex[:10], name=name.strip(), width_mm=round(size[0], 1), height_mm=round(size[1], 1)))
    _write(root, hoops)
    return hoops


def delete(root, hoop_id):
    hoops = saved(root)
    kept = [h for h in hoops if h.get('id') != hoop_id]
    if len(kept) == len(hoops):
        raise ValueError('That hoop is no longer saved.')
    _write(root, kept)
    return kept


def find(root, hoop_id):
    """The hoop with this id, from the list or the user's own; None when unknown."""
    for group in listed():
        for hoop in group['hoops']:
            if hoop['id'] == hoop_id:
                return dict(hoop, brand=group['brand'])
    for hoop in saved(root):
        if hoop.get('id') == hoop_id:
            return dict(hoop, brand='My hoops')
    return None


def fits(width, height, field):
    """Room left on each side when the design is centred in the field (mm); negative = too big."""
    return round((field[0]-width)/2, 1), round((field[1]-height)/2, 1)
