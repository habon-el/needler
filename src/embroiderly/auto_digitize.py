"""Digitize for me: choose settings, generate, check, adjust and retry.

Rules only, no model. Every attempt goes through the same /artwork route as
the studio buttons, so preparation, approval rules, the engine and the
release gate are unchanged. The person still approves before any download.
"""
import json
import re
import threading
import time
from pathlib import Path

import numpy as np
from PIL import Image

MAX_ATTEMPTS = 4
# Detail slider step -> smallest colour area kept, mm² (3 is the usual 1 mm²).
DETAIL_FLOOR_MM2 = {1: 8.0, 2: 3.0, 3: 1.0, 4: .5, 5: .25}
KINDS = {
    'line_art': 'Light line drawing on a dark background',
    'photo_lines': 'Photo in one thread colour (rows of zigzag that follow the shading)',
    'ink': 'Black ink drawing on a light background',
    'logo': 'Flat-colour artwork (logo, badge or clip art)',
    'photo': 'Photo or shaded artwork',
}


def classify(image, max_side=384):
    """Return (kind, facts) from pixels only. Deterministic and cheap."""
    rgba = image.convert('RGBA')
    rgba.thumbnail((max_side, max_side))
    data = np.asarray(rgba).astype(np.float32)
    alpha = data[..., 3] > 127
    if alpha.sum() < 16:
        alpha = np.ones(alpha.shape, bool)
    rgb = data[..., :3][alpha]
    lum = rgb @ np.array([.299, .587, .114], np.float32)
    sat = (rgb.max(1) - rgb.min(1)) / 255
    dark, bright, lit = (lum < 60).mean(), (lum > 200).mean(), (lum > 110).mean()
    facts = dict(dark=round(float(dark), 3), bright=round(float(bright), 3))
    # Strongly coloured areas (a red robe, a blue sky) make it colour art on a dark
    # background, not light line work: line modes would sew those areas as outlines.
    colourful = float(((sat > .35) & (lum > 50)).mean())
    facts['colourful'] = round(colourful, 3)
    if dark > .55 and .005 < lit < .35 and colourful < .03:
        return 'line_art', facts
    ink_pixels = lum < 90
    if bright > .6 and .003 < ink_pixels.mean() < .3 and float(sat[ink_pixels].mean() if ink_pixels.any() else 1) < .18:
        return 'ink', facts
    # Shaded black-and-white art (engravings, pencil, halftone): almost no colour and
    # many mid-greys. Black-ink mode would turn its shading into specks and a
    # honeycomb of lines; one-colour photo lines keep the tones.
    mid = float(((lum > 60) & (lum < 200)).mean())
    facts['mid_greys'] = round(mid, 3)
    if float(sat.mean()) < .06 and mid > .35:
        facts['shaded'] = True
        return 'photo', facts
    # Colour count from a median-cut palette; ignore colours under 1.5 %.
    small = Image.fromarray(np.asarray(rgba.convert('RGB'))).quantize(12, method=Image.Quantize.MEDIANCUT)
    counts = np.bincount(np.asarray(small)[alpha].ravel(), minlength=12) / max(1, alpha.sum())
    # Fewer than 12 colours in the picture means a shorter palette; pad it.
    palette = np.array((small.getpalette()[:36] + [0] * 36)[:36], np.float32).reshape(12, 3)
    colours = int((counts >= .015).sum())
    # Flat artwork: most pixels sit close to their palette colour.
    error = np.abs(np.asarray(rgba.convert('RGB'), np.float32)[alpha] - palette[np.asarray(small)[alpha]]).mean(1)
    flat = float((error < 18).mean())
    # A uniform border is background, not a thread colour.
    border = np.concatenate([np.asarray(small)[0], np.asarray(small)[-1], np.asarray(small)[:, 0], np.asarray(small)[:, -1]])
    background = bool(np.bincount(border).max() / len(border) > .8 and np.asarray(rgba)[..., 3].min() > 127)
    facts.update(colours=colours, flat=round(flat, 3), background=background)
    count = max(2, min(8, colours - (1 if background else 0)))
    facts['thread_colours'] = count
    return ('logo' if flat >= .75 else 'photo'), facts


def parse_request(text):
    """Small plain-English parser: sizes, colour limits and an artwork type."""
    text = (text or '').lower()
    wish = {}
    unit = {'mm': 1, 'cm': 10, 'in': 25.4, 'inch': 25.4, 'inches': 25.4, '"': 25.4}
    for value, scale, axis in re.findall(r'(\d+(?:[.,]\d+)?)\s*(mm|cm|inches|inch|in|")\s*(wide|width|across|tall|high|height)?', text):
        mm = float(value.replace(',', '.')) * unit[scale]
        key = 'height_mm' if axis in ('tall', 'high', 'height') else 'width_mm'
        if 3 <= mm <= 400:
            wish[key] = round(mm, 1)
    match = re.search(r'(\d+)\s*(?:thread\s*)?colou?rs?', text)
    if match:
        wish['colours'] = max(2, min(8, int(match.group(1))))
    # Fabric preset: the item or fabric named in the request.
    for pattern, fabric in ((r'leather|suede|vinyl', 'leather'), (r'velvet|corduroy|velour', 'velvet'),
                            (r'chiffon|organza|tulle|sheer', 'sheer'), (r'\bmesh\b', 'mesh'),
                            (r'\bwool|hand ?knit|cardigan', 'wool'), (r'\blinen', 'linen'),
                            (r't-?shirt|tee\b|jersey|stretch|lycra|spandex', 'stretch_knit'),
                            (r'\bpolo|piqu', 'pique'), (r'fleece|hoodie|sweat ?shirt|sweater', 'fleece'),
                            (r'towel|terry|bathrobe', 'towel'), (r'\bcaps?\b|\bhats?\b|beanie', 'cap'),
                            (r'denim|jean', 'denim'), (r'\bsilk|\bsatin\b', 'satin_silk'),
                            (r'nylon|jacket|windbreaker|sport', 'nylon'), (r'cotton', 'cotton'),
                            (r'twill|canvas|tote', 'twill')):
        if re.search(pattern, text):
            wish['fabric'] = fabric
            break
    if re.search(r'\boutlines?\b|\boutlined\b', text):
        wish['outlines'] = True
    if re.search(r'keep\b.{0,25}back ?ground|back ?ground.{0,20}\b(stitch|sew|fill|keep)', text):
        wish['keep_background'] = True
    if re.search(r'\bpuff|\bfoam|\b3d\b|raised', text):
        wish['puff'] = True
        match = re.search(r'(\d(?:[.,]\d)?)\s*mm\s*foam', text)
        if match:
            wish['foam_mm'] = max(1.0, min(5.0, float(match.group(1).replace(',', '.'))))
    for pattern, kind in ((r'line[- ]?art|light lines', 'line_art'), (r'black lines|ink|sketch', 'ink'), (r'logo|badge', 'logo')):
        if re.search(pattern, text):
            wish['kind'] = kind
            break
    return wish


def plan(kind, facts, wish, image_size, saved):
    """Settings for the first attempt, on top of the person's saved choices."""
    w, h = image_size
    options = {k: v for k, v in saved.items() if k not in ('line_art', 'ink_only', 'count', 'cleanup_decisions', 'photo_style')}
    options.update(artwork_type='logo', line_art=kind == 'line_art', ink_only=kind == 'ink')
    if kind in ('logo', 'photo'):
        options['count'] = wish.get('colours', facts.get('thread_colours', 4) if kind == 'logo' else 6)
    if kind == 'photo' and not wish.get('colours'):
        # Photos used to go through the flat-colour logo path (6 blotchy colours). One thread in
        # rows whose zigzag follows the shading keeps the tones and sews without cuts.
        options.update(photo_style='one_colour', count=2, smooth=2, selection=options.get('selection', 'full'))
    if 'height_mm' in wish:
        options['height_mm'] = wish['height_mm']
    elif 'width_mm' in wish:
        options['height_mm'] = round(wish['width_mm'] * h / w, 1)
    options['height_mm'] = max(3, min(400, float(options.get('height_mm', 100))))
    if wish.get('puff') and kind in ('logo', 'photo'):
        options.update(puff=True, puff_foam_mm=wish.get('foam_mm', 3))
    if wish.get('fabric'):
        options['fabric_preset'] = wish['fabric']
    if wish.get('outlines') and kind == 'logo':
        # Add outlines: one dark running line around every colour, sewn last.
        options.update(outlines=True, outline_colour=wish.get('outline_colour', 'auto'))
    if wish.get('floor_mm2') and kind in ('logo', 'photo'):
        # The Detail slider: the smallest colour area kept (a details slider).
        options['floor_mm2'] = wish['floor_mm2']
    if kind in ('logo', 'photo') and facts.get('dark', 0) > .55 and facts.get('colourful', 0) >= .03:
        # Colour art on a dark background usually has light linework the fills lose (mixed mode).
        options.setdefault('line_details', 'light')
    if wish.get('keep_background'):
        # A saved subject cut-out would remove the background before stitching.
        options['selection'] = 'full'
        options.pop('rect', None)
    return options


def assess(result):
    """Problems worth another attempt, most serious first."""
    issues = []
    if result.get('error'):
        issues.append(dict(kind='error', text=result['error']))
        return issues
    if result.get('gate'):
        issues.append(dict(kind='gate', text=result['gate']))
    stitches, trims = result['stitches'], result['trims']
    if trims > 15 and trims * 120 > stitches:
        issues.append(dict(kind='cuts', text=f'{trims} thread cuts for {stitches} stitches; the machine will stop often.'))
    return issues


def score(result, wish=None):
    if result.get('error'):
        return 1e9
    off = max((abs(result[k] - wish[k]) / wish[k] for k in ('width_mm', 'height_mm') if (wish or {}).get(k)), default=0)
    return (1e6 if result.get('gate') else 0) + 1000 * result['trims'] / max(1, result['stitches']) + 500 * off


def adjust(options, kind, issues, attempt):
    """Next settings, or None when no rule applies. Returns (options, kind, why)."""
    text = ' '.join(i['text'] for i in issues)
    kinds = {i['kind'] for i in issues}
    nxt = dict(options)
    if 'No drawn lines' in text and kind == 'line_art':
        nxt.update(line_art=False, count=4)
        return nxt, 'logo', 'No light lines were found, so it is treated as colour artwork instead.'
    if kinds & {'error', 'gate'} or 'cuts' in kinds:
        if kind == 'line_art':
            retrace = float(options.get('line_retrace_mm', 6))
            if 'cuts' not in kinds or retrace >= 24:
                return None
            nxt['line_retrace_mm'] = retrace * 2
            return nxt, kind, f"Letting the needle travel back over sewn lines for up to {retrace * 2:g} mm instead of cutting the thread."
        floor = float(options.get('floor_mm2', 1))
        nxt['floor_mm2'] = round(min(25, max(2.5, floor * 2.5)), 1)
        nxt['simplify'] = min(100, int(options.get('simplify', 0)) + 30)
        nxt['smooth'] = min(3, int(options.get('smooth', 1)) + 1)
        why = f"Merging details smaller than {nxt['floor_mm2']} mm² and smoothing edges"
        if 'cuts' in kinds and kind != 'ink' and int(options.get('count', 4)) > 2:
            nxt['count'] = int(options.get('count', 4)) - 1
            why += f", and using {nxt['count']} colours"
        return nxt, kind, why + ' to make it easier to sew.'
    return None


def size_fit(wish, result, options):
    """Scale the canvas so the sewn design matches a requested width or height."""
    for key, label in (('width_mm', 'width'), ('height_mm', 'height')):
        target, actual = wish.get(key), result.get(key)
        if target and actual and abs(actual - target) / target > .03:
            height = max(3, min(400, round(float(options['height_mm']) * target / actual, 1)))
            if height != options['height_mm']:
                return {**options, 'height_mm': height}, f'{target:g} mm {label}'
    return None


class AutoDigitizer:
    def __init__(self, app, root):
        self.app, self.root = app, Path(root)
        self.uploads, self.decisions = self.root / 'work' / 'uploads', self.root / 'work' / 'decisions'
        self.jobs, self.lock = {}, threading.Lock()

    def start(self, name, request_text='', use_claude=False, choices=None):
        path = self.uploads / Path(name).name
        if not path.is_file():
            raise FileNotFoundError(name)
        if (self.decisions / (path.name + '.lettering.json')).is_file():
            raise ValueError('This design is picture-based text. Use Text with an embroidery font instead.')
        with self.lock:
            job = self.jobs.get(path.name)
            if job and job['state'] == 'running':
                raise RuntimeError('Digitize for me is already working on this design.')
            job = dict(state='running', steps=[], request=request_text[:300], started=time.time(), result=None,
                       use_claude=bool(use_claude), choices=choices or {})
            self.jobs[path.name] = job
        threading.Thread(target=self._run, args=(path, job), daemon=True).start()
        return job

    def status(self, name):
        name = Path(name).name
        job = self.jobs.get(name)
        if job:
            return job
        stored = self.decisions / (name + '.auto.json')
        return json.loads(stored.read_text()) if stored.is_file() else None

    def _log(self, job, text):
        job['steps'].append(dict(at=round(time.time() - job['started'], 1), text=text))

    def _attempt(self, path, options, drop_below=.8, keep_playback=False):
        client = self.app.test_client()
        url = '/artwork/' + path.name
        for _ in range(6):
            response = client.post(url, json=dict(options=options, digitize=True, subject_confirmed=True))
            body = response.get_json(silent=True) or {}
            if body.get('code') != 'cleanup_review_required':
                break
            # Pending cleanup: keep visible details, let specks under 0.8 mm go.
            decisions = dict(options.get('cleanup_decisions', {}))
            for item in body['report']['cleanup_review']:
                if item['decision'] == 'pending':
                    decisions[item['id']] = 'drop' if max(item['width_mm'], item['height_mm']) < drop_below else 'keep'
            options = {**options, 'cleanup_decisions': decisions}
        for _ in range(3):
            # Details the fill converter cannot sew (often hatching one pixel wide) block the
            # whole colour design. Merge exactly those into their neighbours and retry.
            if 'Stitching would leave out' not in (body.get('error') or ''):
                break
            report = (client.post(url, json=dict(options=options, subject_confirmed=True)).get_json(silent=True) or {}).get('report') or {}
            blockers = [b['bounds'] for b in report.get('generation_blockers', [])]
            decisions = dict(options.get('cleanup_decisions', {}))
            changed = [item['id'] for item in report.get('cleanup_review', [])
                       if decisions.get(item['id']) != 'drop' and any(
                           item['bounds'][0] <= b[2] and b[0] <= item['bounds'][2] and
                           item['bounds'][1] <= b[3] and b[1] <= item['bounds'][3] for b in blockers)]
            if changed:
                decisions.update(dict.fromkeys(changed, 'drop'))
                options = {**options, 'cleanup_decisions': decisions}
            else:
                # Not a cleanup item (e.g. left by smoothing): paint it with the colour around it.
                paint = self._paint_specks(path, blockers)
                if not paint:
                    break
                options = {**options, 'edits': [*options.get('edits', []), *paint]}
            response = client.post(url, json=dict(options=options, digitize=True, subject_confirmed=True))
            body = response.get_json(silent=True) or {}
        if response.status_code != 200:
            return dict(error=body.get('error') or f'Generation failed ({response.status_code}).'), options
        playback, report = body.get('playback') or {}, body.get('report') or {}
        # Size of the sewn design itself, not the canvas with its empty margins.
        sewn = [s for s in playback.get('steps', []) if s['t'] == 'stitch'] or [dict(x=0, y=0)]
        xs, ys = [s['x'] for s in sewn], [s['y'] for s in sewn]
        result = dict(stitches=playback.get('stitch_count', 0), trims=playback.get('trim_count', 0),
                      colours=len(playback.get('colors', [])), prepared=body.get('prepared_name'),
                      width_mm=round(max(xs) - min(xs), 1), height_mm=round(max(ys) - min(ys), 1),
                      puff=playback.get('puff'))
        if keep_playback:
            result['playback'] = playback
        from .release_gate import checked_bytes, ReleaseError
        try:
            checked_bytes(self.root / 'work' / 'inkstitch-preview' / Path(result['prepared']).stem, 'dst')
        except ReleaseError as error:
            result['gate'] = str(error)
        return result, options

    def _paint_specks(self, path, boxes, limit=40):
        """Paint edits giving each tiny unsewable detail the commonest colour just around it."""
        # Blocker boxes are in the working picture (at most 768 px), like every edit.
        from .preparation import load_image
        rgb = np.asarray(load_image(path).convert('RGB'))
        h, w = rgb.shape[:2]
        edits = []
        for x0, y0, x1, y1 in boxes[:limit]:
            if (x1-x0) * (y1-y0) > 16:
                continue
            ring = rgb[max(0, y0-3):min(h, y1+3), max(0, x0-3):min(w, x1+3)].reshape(-1, 3)
            values, counts = np.unique(ring, axis=0, return_counts=True)
            colour = '#%02x%02x%02x' % tuple(int(v) for v in values[counts.argmax()])
            edits.append(dict(kind='paint', colour=colour, radius=max(1, (max(x1-x0, y1-y0)+1)//2),
                              points=[[min(w-1, (x0+x1)/2), min(h-1, (y0+y1)/2)]], auto=True))
        return edits

    def _run(self, path, job):
        try:
            with Image.open(path) as image:
                kind, facts = classify(image)
                size = image.size
            wish = {**parse_request(job['request']), **job.get('choices', {})}
            if wish.get('kind'):
                self._log(job, f"You asked for {KINDS[wish['kind']].lower()}.")
                kind = wish['kind']
            else:
                self._log(job, f'Looked at the picture: {KINDS[kind].lower()}.')
            if wish.get('keep_background') and kind in ('line_art', 'ink'):
                # Line modes leave the background as bare fabric; keeping it needs colour mode.
                kind = 'logo'
                facts = {**facts, 'thread_colours': facts.get('thread_colours', 4)}
                self._log(job, 'You asked to keep the background, so it is stitched in colour too.')
            saved_file = self.decisions / (path.name + '.preparation.json')
            saved = json.loads(saved_file.read_text()) if saved_file.is_file() else {}
            options = plan(kind, facts, wish, size, saved)
            if kind == 'logo' and not wish.get('keep_background') and not options.get('colour_knockouts'):
                # Colour roles: a plain border colour is background (omitted), not a thread.
                from .colour_knockout import proposal_patch
                with Image.open(path) as image:
                    patch = proposal_patch(image, options)
                if patch:
                    options.update(patch)
                    self._log(job, f"Leaving out the plain background ({patch['colour_knockouts'][-1]['colour']}); "
                                   "say “keep the background” to stitch it.")
            attempts, finish = [], None
            if job.get('use_claude'):
                from . import auto_claude
                try:
                    self._log(job, 'Asking Claude to look at the picture and choose the settings…')
                    drop = iter([.8] + [1.5] * 10)
                    attempts, finish = auto_claude.run(job, path, kind, facts, wish, options,
                                                       lambda o: self._attempt(path, o, next(drop), True),
                                                       lambda text: self._log(job, text))
                except Exception as error:  # Claude unavailable: the rules still work offline.
                    self._log(job, f'Claude could not help ({str(error)[:160]}). Switching to the built-in rules.')
                    attempts, finish = [], None
            if not [a for a in attempts if not a.get('error')]:
                attempts = self._rules(job, path, kind, wish, options)
            self._finish(job, path, kind, facts, wish, attempts, finish)
        except Exception as error:  # Report, never crash the server thread.
            job['state'] = 'failed'
            job['result'] = dict(ok=False, problem=str(error))
            self._log(job, 'Stopped: ' + str(error))
        finally:
            job['finished'] = time.time()
            stored = self.decisions / (path.name + '.auto.json')
            temp = stored.with_suffix('.tmp')
            temp.write_text(json.dumps(job, default=str))
            temp.replace(stored)

    def _rules(self, job, path, kind, wish, options):
        describe = {'line_art': 'line-art mode: each line becomes a running stitch, the dark background stays empty',
                    'ink': 'black-lines mode: white stays empty, lines become running stitches',
                    'logo': f"{options.get('count')} thread colours with fills and satin for thin parts",
                    'photo': ("one-colour photo lines: one thread in rows whose zigzag follows the shading"
                              if options.get('photo_style') == 'one_colour' else
                              f"{options.get('count')} thread colours; photos are hard to stitch, so expect to review it")}[kind]
        self._log(job, f"Chose {describe}; {options['height_mm']:g} mm high.")
        attempts, fits = [], 0
        for number in range(1, MAX_ATTEMPTS + 1):
            self._log(job, f'Attempt {number}: making stitches…')
            result, options = self._attempt(path, options, .8 if number == 1 else 1.5)
            result.update(options=options, kind=kind, number=number)
            attempts.append(result)
            issues = assess(result)
            fit = size_fit(wish, result, options) if not result.get('error') and fits < 2 else None
            if not issues and fit:
                fits += 1
                self._log(job, f"Attempt {number}: sewn size is {result['width_mm']:g} × {result['height_mm']:g} mm; "
                               f"rescaling to match the {fit[1]} you asked for.")
                options = fit[0]
                continue
            if not issues:
                self._log(job, f"Attempt {number}: {result['stitches']:,} stitches, {result['trims']} cut{'' if result['trims'] == 1 else 's'}, "
                               f"{result['width_mm']:g} × {result['height_mm']:g} mm sewn. All checks passed.")
                break
            self._log(job, f"Attempt {number}: " + ' '.join(i['text'] for i in issues))
            step = adjust(options, kind, issues, number)
            if not step or number == MAX_ATTEMPTS:
                self._log(job, 'No further automatic fix applies; keeping the best attempt.')
                break
            options, kind, why = step
            self._log(job, why)
        return attempts

    def _finish(self, job, path, kind, facts, wish, attempts, finish):
        chosen = None
        if finish:
            chosen = next((a for a in attempts if a['number'] == finish.get('attempt') and not a.get('error')), None)
        best = chosen or min(attempts, key=lambda a: score(a, wish))
        if best is not attempts[-1] and not best.get('error'):
            # The last attempt is what is saved; put the chosen one back.
            self._log(job, f"Restoring attempt {best['number']}, the one to keep.")
            restored, _ = self._attempt(path, best['options'], 1.5)
            best = {**restored, 'kind': best['kind'], 'number': best['number'], 'options': best['options']}
        ok = not best.get('error') and not best.get('gate')
        job['result'] = dict(ok=ok, kind=best.get('kind', kind), facts=facts, attempts=len(attempts),
                             stitches=best.get('stitches'), trims=best.get('trims'), colours=best.get('colours'),
                             width_mm=best.get('width_mm'), height_mm=best.get('height_mm'),
                             problem=best.get('error') or best.get('gate'),
                             issues=[i['text'] for i in assess(best)])
        if best.get('options', {}).get('puff') and not best.get('puff') and not best.get('error'):
            job['result']['issues'].append('3D puff was asked for, but no part is wide enough to hold the foam (3–6 mm, or 2–6 mm with 2 mm foam) at this size, so it is sewn flat. '
                                           'Try another size, 2 mm foam, or puff bold lettering instead.')
        elif best.get('puff'):
            job['result']['puff'] = best['puff']
        if finish:
            job['result'].update(summary=str(finish.get('summary', ''))[:800],
                                 check=[str(c)[:300] for c in finish.get('check', [])][:4])
        if job.get('claude_usd') is not None:
            job['result']['claude_usd'] = job['claude_usd']
        job['state'] = 'done' if ok else 'needs_review'
        self._log(job, 'Done. Review it in 3D, then approve and download.' if ok else
                  'Finished with a problem it could not fix automatically. See the note below.')


def register_auto_digitize(app, root):
    from flask import abort, jsonify, request
    runner = AutoDigitizer(app, root)

    @app.post('/api/auto-digitize/<name>')
    def auto_digitize_start(name):
        body = request.get_json(silent=True) or {}
        # Panel controls: outline checkbox and Detail slider (1 fewer … 5 more; 3 keeps the default).
        choices = {}
        if body.get('outlines') is True:
            choices['outlines'] = True
        if body.get('detail') in (1, 2, 4, 5):
            choices['floor_mm2'] = DETAIL_FLOOR_MM2[body['detail']]
        try:
            job = runner.start(name, str(body.get('request', '')), body.get('use_claude') is True, choices)
        except FileNotFoundError:
            abort(404)
        except (RuntimeError, ValueError) as error:
            return jsonify(error=str(error)), 409
        return jsonify(job), 202

    @app.get('/api/auto-digitize/<name>')
    def auto_digitize_status(name):
        job = runner.status(name)
        return (jsonify(job), 200) if job else (jsonify(state='none'), 200)

    @app.get('/api/auto-digitize-claude')
    def auto_digitize_claude():
        # Whether a key is set and what has been spent; never the key itself.
        from . import auto_claude
        spent = auto_claude.Spend(runner.decisions / 'claude-spend.json').total
        return jsonify(available=auto_claude.available(), spent_usd=round(spent, 2),
                       run_limit_usd=auto_claude.RUN_LIMIT, total_limit_usd=auto_claude.TOTAL_LIMIT)
