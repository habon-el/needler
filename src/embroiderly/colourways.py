"""Named colourways: colour versions of one design, each a name and its thread choices.

A colourway keeps the thread options of the design (`merges`: artwork colour -> thread colour,
and the border thread). Switching puts them back into the preparation options, so the stitches
and machine files are the active colourway's; a colour-only change reuses the verified routing
(thread_recolour.reuse). The list lives next to the design in work/decisions/<name>.colourways.json.
"""
import json
import re
from pathlib import Path
from uuid import uuid4

MAX_SAVED = 20
HEX = re.compile('#[0-9a-fA-F]{6}')


def _file(root, design):
    return Path(root)/'work'/'decisions'/(Path(design).name+'.colourways.json')


def saved(root, design):
    try:
        value = json.loads(_file(root, design).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    return [c for c in value if isinstance(c, dict)] if isinstance(value, list) else []


def _write(root, design, colourways):
    target = _file(root, design)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(colourways, indent=1), encoding='utf-8')
    temporary.replace(target)


def threads(value):
    """Checked thread choices: {merges: {hex: hex}, border_colour?: hex}, colours in lower case."""
    if not isinstance(value, dict) or set(value) - {'merges', 'border_colour'}:
        raise ValueError('Invalid thread colours.')
    merges = value.get('merges', {})
    if not isinstance(merges, dict) or len(merges) > 64 or not all(
            isinstance(v, str) and HEX.fullmatch(v) for pair in merges.items() for v in pair):
        raise ValueError('Invalid thread colours.')
    result = dict(merges={k.lower(): v.lower() for k, v in merges.items()})
    if 'border_colour' in value:
        if not isinstance(value['border_colour'], str) or not HEX.fullmatch(value['border_colour']):
            raise ValueError('Invalid thread colours.')
        result['border_colour'] = value['border_colour'].lower()
    return result


def _name(value, others):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 40:
        raise ValueError('Give the colourway a name of up to 40 characters.')
    if value.strip().casefold() in {c.get('name', '').casefold() for c in others}:
        raise ValueError('A colourway with this name already exists.')
    return value.strip()


def save(root, design, body):
    """Add a colourway: {name, threads}. Returns the saved list."""
    if not isinstance(body, dict):
        raise ValueError('Enter a name for the colourway.')
    colourways = saved(root, design)
    if len(colourways) >= MAX_SAVED:
        raise ValueError(f'You can keep up to {MAX_SAVED} colourways. Delete one first.')
    colourways.append(dict(id='cw-'+uuid4().hex[:10], name=_name(body.get('name'), colourways),
                           threads=threads(body.get('threads'))))
    _write(root, design, colourways)
    return colourways


def rename(root, design, ident, new_name):
    colourways = saved(root, design)
    found = next((c for c in colourways if c.get('id') == ident), None)
    if found is None:
        raise ValueError('That colourway is no longer saved.')
    found['name'] = _name(new_name, [c for c in colourways if c is not found])
    _write(root, design, colourways)
    return colourways


def delete(root, design, ident):
    colourways = saved(root, design)
    kept = [c for c in colourways if c.get('id') != ident]
    if len(kept) == len(colourways):
        raise ValueError('That colourway is no longer saved.')
    _write(root, design, kept)
    return kept


def register_colourways(app, root):
    from flask import request, jsonify

    def design(name):
        if not (Path(root)/'work'/'uploads'/Path(name).name).is_file():
            raise FileNotFoundError
        return Path(name).name

    def answer(action):
        try:
            return jsonify(saved=action())
        except FileNotFoundError:
            return jsonify(error='Design not found.'), 404
        except ValueError as error:
            return jsonify(error=str(error)), 404 if 'no longer saved' in str(error) else 400

    @app.get('/api/colourways/<name>')
    def colourway_list(name):
        return answer(lambda: saved(root, design(name)))

    @app.post('/api/colourways/<name>')
    def colourway_save(name):
        return answer(lambda: save(root, design(name), request.get_json(silent=True)))

    @app.patch('/api/colourways/<name>/<ident>')
    def colourway_rename(name, ident):
        body = request.get_json(silent=True)
        return answer(lambda: rename(root, design(name), ident, body.get('name') if isinstance(body, dict) else None))

    @app.delete('/api/colourways/<name>/<ident>')
    def colourway_delete(name, ident):
        return answer(lambda: delete(root, design(name), ident))
