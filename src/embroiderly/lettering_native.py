"""Typed text -> authored satin vectors -> written files -> shared release gate.

Artwork cleanup is deliberately absent. Drafts are immutable, content-addressed
and local. Approval binds the exact recipe and binaries; resizing rebuilds from
font vectors. A download rechecks the on-disk files, including cache hits.
"""
import base64
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
import time
import xml.etree.ElementTree as ET

import pyembroidery as emb
from flask import jsonify, request, send_file
from . import small_lettering
from .lettering_geometry import GRID, INK, SVG
from .lettering_size import width_fit
from .lettering_trial import BUSY, measure
from .machine_files import write_pair, read_pattern
from .release_gate import checked_bytes, record_context, ReleaseError, digest
from .export_findings import inspect, summary

VERSION = 1


def recipe(body):
    text, _, _, align = small_lettering.validate(body)
    width = width_fit(0, body.get('available_width_mm', 50))['available_width_mm']
    colour = body.get('colour', '#202020')
    if not isinstance(colour, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', colour):
        raise ValueError('Choose a thread colour.')
    settings = dict(text=text, font=body['font'], height_mm=float(body['height_mm']),
                    align=align, available_width_mm=width, colour=colour.lower())
    # Layout (spacing, baseline, letter order): only what differs from the plain line,
    # so earlier saved lettering keeps its cache key.
    plain = dict(letter_spacing_mm=0.0, line_spacing=1.0, baseline='straight', sequence='left',
                 frame='none', frame_mm=2.5, classic=False, ornament='none', envelope='none', join='closest')
    names = {'line_spacing': 'line_spacing_percent', 'radius_mm': 'arc_radius_mm'}
    for name, value in small_lettering.layout_options(body).items():
        if plain.get(name) != value:
            settings[names.get(name, name)] = round(value*100, 3) if name == 'line_spacing' else value
    if body.get('puff') is True:
        settings['puff'] = True
        settings['puff_foam_mm'] = small_lettering.puff_foam(body)
    elif body.get('fabric_custom'):
        # The user's own fabric: its checked values travel with the lettering (custom_fabrics.py).
        from .custom_fabrics import check
        settings['fabric_custom'] = check(body['fabric_custom'])
        settings['fabric_preset'] = settings['fabric_custom']['base']
    elif body.get('fabric_preset'):
        # Fabric preset for lettering; an unknown fabric is refused (generation_policy).
        from .generation_policy import preset_for
        settings['fabric_preset'] = preset_for({'fabric_preset': body['fabric_preset']})['fabric']
    return settings


def identity(settings):
    """Cache all output-affecting inputs, including installed font and code."""
    h = hashlib.sha256(json.dumps([VERSION, settings], sort_keys=True).encode())
    from .embroidery_fonts import FONTS, fingerprint as font_fingerprint
    from .stitch_engine import fingerprint as engine_fingerprint
    if settings.get('font') in FONTS:
        h.update(font_fingerprint(settings['font']).encode())
    h.update(engine_fingerprint().encode())
    for name in ('small_lettering', 'lettering_geometry', 'lettering_rails', 'ribbon_outline', 'lettering_source', 'lettering_coverage',
                 'lettering_rebuild', 'lettering_locks', 'lettering_native', 'machine_files',
                 'release_gate', 'export_findings', 'knockout_routing'):
        h.update(Path(__file__).with_name(name+'.py').read_bytes())
    return h.hexdigest()


def preview(bounds, spans, colour):
    x, y, right, bottom = bounds
    paths = ' '.join(f'M {a[0]} {a[1]} L {b[0]} {b[1]}' for a, b in spans)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x-1} {y-1} {right-x+2} {bottom-y+2}">'
           f'<path d="{paths}" fill="none" stroke="{colour}" stroke-width=".12"/></svg>')
    return 'data:image/svg+xml;base64,'+base64.b64encode(svg.encode()).decode()


def glyph_check(svg, text):
    root = ET.fromstring(svg)
    labels = [n.get('{http://www.inkscape.org/namespaces/inkscape}label', '')
              for n in root.iter(SVG+'g') if n.get(INK+'letter-group') == 'glyph']
    expected = Counter(c for c in text if c not in ' \n')
    if Counter(labels) != expected:
        missing = expected - Counter(labels)
        extra = Counter(labels) - expected
        describe = lambda counts: ', '.join(f'{char!r} × {count}' for char, count in sorted(counts.items())) or 'none'
        raise ValueError('The font did not keep every letter and punctuation mark. '
                         f'Missing: {describe(missing)}. Unexpected: {describe(extra)}. '
                         'Try different line breaks or another embroidery font. Nothing was approved.')
    return sum(expected.values())


def write_and_check(folder, settings, generated):
    (folder/'source.svg').write_text(generated['svg'])
    (folder/'plan.json').write_text(json.dumps(generated['plan']))
    pattern = emb.EmbPattern(str(folder/'plan.json'))
    for thread in pattern.threadlist:
        thread.set_color(*(int(settings['colour'][i:i+2], 16) for i in (1, 3, 5)))
    write_pair(pattern, folder/'design.pes', folder/'design.dst', {'version': 6})
    source = generated['rebuild_report']
    # Safety net: a connecting thread that still crosses bare fabric (a notch where
    # two strokes meet) is replaced by a tie-off, a cut and a tie-in on the other
    # side, as for picture designs. Designs that already pass are not touched.
    written = read_pattern(folder/'design.pes')
    if any(i['code'] in ('crossing', 'travel') for i in inspect(written, source['mask'], source.get('grid', GRID), source['origin'])):
        from .knockout_routing import protect
        try:
            generated['rebuild_report']['safety_cuts'] = protect(written, source['mask'], source.get('grid', GRID), source['origin'])
        except ValueError:
            pass  # the checks below report what is left
        else:
            for thread in written.threadlist:
                thread.set_color(*(int(settings['colour'][i:i+2], 16) for i in (1, 3, 5)))
            write_pair(written, folder/'design.pes', folder/'design.dst', {'version': 6}, repair_spacing=True)
    record_context(folder, source['mask'], source.get('grid', GRID), source['origin'])
    reports, issues = {}, {}
    for fmt in ('pes', 'dst'):
        written = read_pattern(folder/('design.'+fmt))
        reports[fmt], bounds, spans = measure(written)
        issues[fmt] = inspect(written, source['mask'], source.get('grid', GRID), source['origin'])
        from .lettering_coverage import missing_columns
        issues[fmt].extend(missing_columns(generated['svg'], written))
        reports[fmt]['missing_columns'] = sum(i['code'] == 'missing_piece' for i in issues[fmt])
        reports[fmt]['crossings'] = sum(i['code'] == 'crossing' for i in issues[fmt])
        reports[fmt]['uncut_travel'] = sum(i['code'] == 'travel' for i in issues[fmt])
    return reports, issues, bounds, spans


def build(folder, settings):
    started = time.monotonic()
    generated = small_lettering.generate(settings, native=True)
    glyphs = glyph_check(generated['svg'], settings['text'])
    source = generated['rebuild_report']
    reports, issues, bounds, spans = write_and_check(folder, settings, generated)
    lock_adjustment = None
    all_issues = [issue for group in issues.values() for issue in group]
    # One bounded retry, only for short segments. Unknown/crossing/missing-part
    # failures do not authorize a lock change. Existing passing files are untouched.
    if all_issues and all(issue['code'] == 'short' for issue in all_issues):
        from .lettering_locks import explicit_locks
        vector, changes = explicit_locks(generated['svg'])
        if changes:
            from .lettering_rebuild import rebuild
            vector, plan, _ = rebuild(vector)
            candidate = {**generated, 'svg': vector, 'plan': plan}
            glyph_check(vector, settings['text'])
            with TemporaryDirectory(prefix='lock-review-', dir=folder) as temporary:
                draft = Path(temporary)
                after, remaining, new_bounds, new_spans = write_and_check(draft, settings, candidate)
                if not any(remaining.values()):
                    checked_bytes(draft, 'dst')
                    lock_adjustment = dict(before_short=reports['dst']['short'],
                                           after_short=after['dst']['short'],
                                           pattern='explicit 0.6 mm securing stitches')
                    for name in ('source.svg', 'plan.json', 'design.pes', 'design.dst', 'release-context.json'):
                        shutil.copyfile(draft/name, folder/name)
                    reports, issues, bounds, spans = after, remaining, new_bounds, new_spans
    wide_letters = None
    if any(issues.values()) and small_lettering.split_satin(*small_lettering.validate(settings)[:3],
                                                             settings.get('puff') is True):
        # Big letters are split satin; where the font's traced columns, enlarged, let
        # stitches cross a letter hole, the same letters at the same height are tatami fill.
        candidate = small_lettering.generate(settings, native=True, fill=True)
        with TemporaryDirectory(prefix='wide-fill-', dir=folder) as temporary:
            draft = Path(temporary)
            after, remaining, new_bounds, new_spans = write_and_check(draft, settings, candidate)
            if not any(remaining.values()):
                for name in ('source.svg', 'plan.json', 'design.pes', 'design.dst', 'release-context.json'):
                    shutil.copyfile(draft/name, folder/name)
                reports, issues, bounds, spans = after, remaining, new_bounds, new_spans
                generated, source, wide_letters = candidate, candidate['rebuild_report'], 'fill'
    # Letter parts the satin columns leave bare (wider than a thread), with locations.
    # Reported, not yet a download block: square terminals of block fonts still show some.
    from .lettering_coverage import bare_patches
    bare = bare_patches(generated['svg'])
    fit = width_fit(reports['dst']['width_mm'], settings['available_width_mm'])
    passed = not any(issues.values()) and fit['fits']
    if passed:
        # Exactly the same gate as the main app, not a trial-only bypass.
        checked_bytes(folder, 'dst')
    result = dict(recipe=settings, reports=reports, issues=issues, fit=fit,
                  checks_passed=passed, approved=False,
                  image=preview(bounds, spans, settings['colour']),
                  nominal_height_mm=generated['nominal_height_mm'],
                  source_glyphs=glyphs, source_columns=source['columns'],
                  extra_component_cuts=source['added_cuts'], lock_adjustment=lock_adjustment,
                  seconds=round(time.monotonic()-started, 2),
                  pending=['Density and repeated-penetration assessment',
                           'Visual readability and a physical sew-out on your fabric'],
                  wide_letters=wide_letters, bare_patches=bare,
                  message=('File checks passed. '+('These big letters are sewn as fill, not satin, so no stitch '
                                                    'crosses a letter hole. ' if wide_letters else '')+
                           'Review the lettering before saving.' if passed else
                           'No download yet. '+(summary(issues['dst'])+'. ' if issues['dst'] else '')+
                           ('The words are wider than your chosen space. ' if not fit['fits'] else '')+
                           'Try a different embroidery font, a larger letter size or more lines. Nothing was shrunk or removed.'))
    (folder/'result.json').write_text(json.dumps(result, sort_keys=True))
    return result


def _move(draft, target):
    """Rename a finished draft folder into place. On Windows a virus scanner may
    still hold a file just written; wait briefly and retry (team names make many)."""
    for attempt in range(6):
        try:
            draft.rename(target)
            return
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(.1*(attempt+1))


def make(store, settings):
    """Build, or reuse, the checked files for one recipe (the caller holds BUSY).
    Returns the key, its folder and whether the stitches were already made."""
    store = Path(store)
    key = identity(settings)
    folder = store/key
    store.mkdir(parents=True, exist_ok=True)
    cached = (folder/'result.json').is_file()
    if not cached:
        # Available width is a fit constraint, not a generation input.
        # Keep one checked geometry pair when only that space changes.
        geometry_settings = {**settings, 'available_width_mm': 400.0}
        geometry = store/'geometry'/identity(geometry_settings)
        geometry.parent.mkdir(exist_ok=True)
        geometry_cached = (geometry/'result.json').is_file()
        if not geometry_cached:
            with TemporaryDirectory(prefix='draft-', dir=store) as temporary:
                build(Path(temporary), geometry_settings)
                _move(Path(temporary), geometry)
        with TemporaryDirectory(prefix='draft-', dir=store) as temporary:
            draft = Path(temporary)
            for filename in ('source.svg', 'plan.json', 'design.pes', 'design.dst', 'release-context.json'):
                shutil.copyfile(geometry/filename, draft/filename)
            result = json.loads((geometry/'result.json').read_text())
            result['recipe'] = settings
            result['fit'] = width_fit(result['reports']['dst']['width_mm'], settings['available_width_mm'])
            result['checks_passed'] = not any(result['issues'].values()) and result['fit']['fits']
            if not result['fit']['fits']:
                fit = result['fit']
                result['message'] = (f"The words are {fit['actual_width_mm']:g} mm wide, more than your max width of "
                                     f"{fit['available_width_mm']:g} mm. Make Max width larger or the text smaller. Nothing was resized.")
            (draft/'result.json').write_text(json.dumps(result, sort_keys=True))
            _move(Path(temporary), folder)
        cached = geometry_cached
    return key, folder, cached


def load(folder, key):
    result = json.loads((folder/'result.json').read_text())
    if identity(result['recipe']) != key:
        raise ValueError('The font or software changed. Rebuild these words before downloading.')
    result['id'] = key
    result['approved'] = (folder/'approved.json').is_file()
    return result


def register(app, root):
    store = Path(root)/'work'/'lettering-native'

    @app.context_processor
    def lettering_font_limits():
        fonts = small_lettering.fonts()
        return dict(native_fonts=list(fonts.items()),
                    native_font_sizes={key: small_lettering.size_limits(font) for key, font in fonts.items()},
                    native_puff_sizes={key: small_lettering.size_limits(font, True) for key, font in fonts.items()})


    def folder_for(key):
        if not re.fullmatch(r'[a-f0-9]{64}', key):
            raise ValueError('That saved lettering could not be found.')
        return store/key

    def problem(error, status=422):
        if not isinstance(error, ValueError):
            app.logger.exception('Native lettering operation failed')
        message = str(error) if isinstance(error, ValueError) else 'Lettering could not finish. Your open design is unchanged. Please retry.'
        return jsonify(error=message), status

    @app.post('/lettering/native/advice')
    def advice():
        # Every problem at once, with one-click fixes; nothing is built or saved.
        try:
            return jsonify(small_lettering.advice(request.get_json(silent=True)))
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            return problem(error, 400)

    @app.get('/lettering/native/thread')
    def thread_names():
        # Closest machine threads for the text colour (approximate; RGB charts are not measured thread).
        # ?chart= limits the matches to one chart; empty means every chart.
        from .thread_matching import rank_threads, CHARTS
        chart = request.args.get('chart') or None
        if chart is not None and chart not in CHARTS:
            return problem(ValueError('Choose one of the listed thread charts.'), 400)
        try:
            return jsonify(threads=rank_threads(request.args.get('hex', ''), brands=[chart] if chart else None, limit=3),
                           charts=list(CHARTS))
        except ValueError as error:
            return problem(error, 400)

    @app.post('/lettering/native/ask')
    def ask_ai():
        # Claude chooses the text settings; the screen applies them and makes the stitches.
        from . import text_ai
        body = request.get_json(silent=True) or {}
        try:
            values, note, left, usd = text_ai.ask(body.get('request'), body.get('values'), Path(root)/'work'/'decisions')
        except ValueError as error:
            return problem(error, 400)
        except Exception as error:
            app.logger.exception('Text AI failed')
            return jsonify(error='AI help could not finish: '+type(error).__name__+'. Your settings are unchanged.'), 502
        return jsonify(values=values, note=note, problems=left, claude_usd=usd)

    @app.post('/lettering/native/check')
    def check():
        try:
            settings = recipe(request.get_json(silent=True))
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            return problem(error, 400)
        if not BUSY.acquire(blocking=False):
            return jsonify(error='Another lettering check is running. Please retry shortly.'), 409
        try:
            key, folder, cached = make(store, settings)
            result = load(folder, key)
            # Detect corrupt/stale files even when returning a cached preview.
            if result['checks_passed']:
                checked_bytes(folder, 'dst')
            result['cached'] = cached
            return jsonify(result)
        except (ValueError, TypeError, KeyError, OSError, subprocess.SubprocessError) as error:
            return problem(error)
        finally:
            BUSY.release()

    @app.get('/lettering/native/<key>')
    def saved(key):
        try:
            return jsonify(load(folder_for(key), key))
        except (ValueError, KeyError, OSError) as error:
            return problem(error, 404)

    @app.post('/lettering/native/<key>/approve')
    def approve(key):
        try:
            folder = folder_for(key)
            result = load(folder, key)
            if request.get_json(silent=True) != {'approve': True}:
                raise ValueError('Review the lettering, then choose Save checked lettering.')
            if not result['checks_passed']:
                raise ValueError(result['message'])
            checked_bytes(folder, 'dst')
            # Repeated approval is idempotent. No regeneration or file scaling.
            approval = dict(context=digest((folder/'release-context.json').read_bytes()), key=key)
            (folder/'approved.json').write_text(json.dumps(approval, sort_keys=True))
            return jsonify(id=key, approved=True)
        except (ValueError, KeyError, OSError) as error:
            return problem(error)

    @app.get('/lettering/native/<key>/download/<fmt>')
    def download(key, fmt):
        try:
            from .release_gate import FORMATS, converted_bytes
            if fmt not in FORMATS:
                raise ValueError('Choose a supported machine format.')
            folder = folder_for(key)
            result = load(folder, key)
            if not (folder/'approved.json').is_file():
                raise ValueError('Review the lettering and choose Save checked lettering before downloading.')
            approval = json.loads((folder/'approved.json').read_text())
            if not result['checks_passed'] or approval != dict(context=digest((folder/'release-context.json').read_bytes()), key=key):
                raise ValueError('Rebuild and review this lettering before downloading.')
            data = converted_bytes(folder, fmt)
            return send_file(io.BytesIO(data), mimetype='application/octet-stream',
                             as_attachment=True, download_name='embroiderly-lettering.'+fmt)
        except (ValueError, KeyError, OSError) as error:
            return problem(error)
