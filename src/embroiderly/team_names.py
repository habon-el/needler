"""Team names: one lettering setup, many names, one checked machine file per name.

Each name is the Text page's own recipe with only the words changed, built (or
reused from the cache) by lettering_native.make, one at a time under the same
lock. Every name keeps the one height chosen, so all names match: a name wider
than the max width is reported with the height that would fit, never resized.
The zip holds only names whose files passed; each file is read back through
the release gate (converted_bytes) as it is added.
"""
import io
import json
import math
from pathlib import Path
import re
import unicodedata
import zipfile

from flask import jsonify, request, send_file
from . import lettering_native as native
from .export_findings import summary
from .release_gate import FORMATS, ReleaseError, converted_bytes

MAX_NAMES = 50
MAX_CHARS = 40
# File names Windows will not create, whatever the extension.
RESERVED = {'con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(1, 10)), *(f'lpt{i}' for i in range(1, 10))}


def names(text):
    """The names typed, one per line (blank lines skipped), within the limits."""
    if not isinstance(text, str):
        raise ValueError('Type one name per line.')
    found = [' '.join(line.split()) for line in unicodedata.normalize('NFC', text).splitlines()]
    found = [name for name in found if name]
    if not found:
        raise ValueError('Type one name per line.')
    if len(found) > MAX_NAMES:
        raise ValueError(f'Use at most {MAX_NAMES} names at a time. You typed {len(found)}.')
    long = [name for name in found if len(name) > MAX_CHARS]
    if long:
        raise ValueError(f'Keep each name to {MAX_CHARS} letters or fewer: {long[0][:MAX_CHARS]}…')
    return found


def file_name(name):
    """A name safe on every computer and machine USB stick: plain letters, digits, - and _."""
    plain = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
    plain = re.sub(r'[^A-Za-z0-9_-]+', '-', plain).strip('-_.')[:MAX_CHARS] or 'name'
    return plain+'_' if plain.lower() in RESERVED else plain


def file_names(found):
    """One distinct file name per name, in order (a repeated name gets -2, -3 …)."""
    used, out = set(), []
    for name in found:
        base = file_name(name)
        candidate, count = base, 1
        while candidate.lower() in used:
            count += 1
            candidate = f'{base}-{count}'
        used.add(candidate.lower())
        out.append(candidate)
    return out


def row(name, key, result):
    """One line of the summary: size, stitches, and why a name has no file."""
    dst = result['reports']['dst']
    fit = result['fit']
    checks_ok = not any(result['issues'].values())
    item = dict(name=name, id=key, width_mm=dst['width_mm'], height_mm=dst['height_mm'],
                stitches=dst['stitches'], fits=fit['fits'], ready=bool(result['checks_passed']), reason=None)
    if not checks_ok:
        item['reason'] = 'Did not pass the file checks: '+summary(result['issues']['dst'] or result['issues']['pes'])+'.'
    elif not fit['fits']:
        # The height that would fit, offered as a choice for all names (never applied here).
        height = float(result['recipe']['height_mm'])
        item['fit_height_mm'] = math.floor(height*fit['available_width_mm']/max(dst['width_mm'], 1e-6)*10)/10
        item['reason'] = (f"{dst['width_mm']:g} mm wide, more than your max width of {fit['available_width_mm']:g} mm. "
                          'Not resized.')
    return item


def register(app, root):
    store = Path(root)/'work'/'lettering-native'

    def problem(error, status=422):
        if not isinstance(error, ValueError):
            app.logger.exception('Team names failed')
        message = str(error) if isinstance(error, ValueError) else 'Team names could not finish. Please retry.'
        return jsonify(error=message), status

    @app.post('/lettering/native/team/list')
    def team_list():
        # Check the list before anything is built: limits and the file each name gets.
        body = request.get_json(silent=True) or {}
        try:
            found = names(body.get('names'))
        except ValueError as error:
            return problem(error, 400)
        return jsonify(names=[dict(name=n, file=f) for n, f in zip(found, file_names(found))])

    @app.post('/lettering/native/team/name')
    def team_name():
        # One name with the shared setup; the page asks for the names one after another.
        body = request.get_json(silent=True)
        try:
            if not isinstance(body, dict):
                raise ValueError('Expected lettering settings.')
            found = names(body.get('text'))
            if len(found) != 1:
                raise ValueError('Send one name at a time.')
            name = found[0]
        except ValueError as error:
            return problem(error, 400)
        try:
            settings = native.recipe({**body, 'text': name})
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            # Letters the font lacks, a height this name cannot have …: reported for this name only.
            return jsonify(name=name, id=None, ready=False, fits=False, reason=str(error))
        if not native.BUSY.acquire(blocking=False):
            return jsonify(error='Another lettering check is running. Please retry shortly.'), 409
        try:
            key, folder, _ = native.make(store, settings)
            return jsonify(row(name, key, native.load(folder, key)))
        except (ValueError, TypeError, KeyError, OSError) as error:
            if isinstance(error, ValueError):
                return jsonify(name=name, id=None, ready=False, fits=False, reason=str(error))
            return problem(error)
        finally:
            native.BUSY.release()

    @app.post('/lettering/native/team/zip')
    def team_zip():
        # Only names whose files passed, all with one setup, each re-read through the release gate.
        body = request.get_json(silent=True) or {}
        try:
            fmt = body.get('format')
            if fmt not in FORMATS:
                raise ValueError('Choose a supported machine format.')
            entries = body.get('names')
            if not isinstance(entries, list) or not entries:
                raise ValueError('Make the names first.')
            if len(entries) > MAX_NAMES:
                raise ValueError(f'Use at most {MAX_NAMES} names at a time.')
            listed = [e.get('name') if isinstance(e, dict) else None for e in entries]
            found = names('\n'.join(n for n in listed if isinstance(n, str)))
            if found != listed:
                raise ValueError('Make the names again before downloading.')
            shared = None
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
                for entry, filename in zip(entries, file_names(found)):
                    key = entry.get('id')
                    if not isinstance(key, str) or not re.fullmatch(r'[a-f0-9]{64}', key):
                        raise ValueError(f'{entry["name"]} has no checked file yet. Make all names again.')
                    folder = store/key
                    result = native.load(folder, key)
                    if result['recipe']['text'] != entry['name']:
                        raise ValueError('Make the names again before downloading.')
                    if not result['checks_passed']:
                        raise ValueError(f'{entry["name"]} is not ready: '+result['message'])
                    setup = json.dumps({k: v for k, v in result['recipe'].items() if k != 'text'}, sort_keys=True)
                    if shared is not None and setup != shared:
                        raise ValueError('These names were made with different settings. Make all names again.')
                    shared = setup
                    try:
                        data = converted_bytes(folder, fmt)
                    except ReleaseError as error:
                        raise ValueError(f'{entry["name"]}: {error}') from None
                    archive.writestr(f'{filename}.{fmt}', data)
        except (ValueError, KeyError, OSError) as error:
            return problem(error)
        return send_file(io.BytesIO(buffer.getvalue()), mimetype='application/zip',
                         as_attachment=True, download_name=f'team-names-{fmt}.zip')
