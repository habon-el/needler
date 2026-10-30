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
# Longest request read, in characters (the panel's box warns past it; static/auto-digitize.js).
REQUEST_LIMIT = 1000
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
    # Black outlines around coloured fills (a cartoon, clip art) are colour art: black-lines
    # mode would leave the fills out.
    if bright > .6 and .003 < ink_pixels.mean() < .3 and float(sat[ink_pixels].mean() if ink_pixels.any() else 1) < .18 \
            and colourful < .03:
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
    if background:
        # A plain background makes any picture look flat. Judge the subject alone: a colourful
        # photo of one object (a rose on white) is sewn in colour, with enough threads for its
        # shading and never fewer than its colour families (red and green stay apart).
        rgb_all = np.asarray(rgba.convert('RGB'), np.float32)
        edge = np.concatenate([rgb_all[0], rgb_all[-1], rgb_all[:, 0], rgb_all[:, -1]])
        subject = alpha & (np.abs(rgb_all-np.median(edge, axis=0)).max(2) > 40)
        if subject.mean() > .02:
            inside = subject[alpha]
            facts['hues'] = hue_families(rgb_all[subject])
            subject_flat = float((error[inside] < 18).mean())
            facts['subject_flat'] = round(subject_flat, 3)
            if subject_flat < .9 and float(((sat > .35) & (lum > 50))[inside].mean()) > .2:
                facts['object_photo'] = True
                facts['thread_colours'] = max(count, min(8, 2*max(1, facts['hues'])+2))
                return 'logo', facts
    return ('logo' if flat >= .75 else 'photo'), facts


def hue_families(rgb):
    """How many clearly different colour families (red, green, blue...) the pixels have:
    30 degree hue bins holding at least 5 % of the strongly coloured pixels, neighbours merged."""
    hsv = np.asarray(Image.fromarray(rgb.reshape(1, -1, 3).astype(np.uint8)).convert('HSV'), np.float32)[0]
    strong = hsv[(hsv[:, 1] > 90) & (hsv[:, 2] > 50)]
    if len(strong) < 20:
        return 0
    bins = np.bincount((strong[:, 0]*12/256).astype(int) % 12, minlength=12)/len(strong) >= .05
    # Neighbouring bins are one family (a red that leans orange): count the runs around the wheel.
    return int(sum(1 for i in range(12) if bins[i] and not bins[i-1])) or int(bins.all())


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
    # Detail wishes: keep small parts and more colours, and never trade them away on a retry.
    if re.search(r'(all|every|full|fine|lots of|more|keep(ing)?( the| all)?)\s+(the\s+)?details?|\bdetailed\b|\brealistic\b', text):
        wish['detail'] = 'more'
    elif re.search(r'\bsimple\b|\bsimpler\b|\bminimal\b|\bfewer details\b|\bless detail', text):
        wish['detail'] = 'less'
    if re.search(r'\boutlines?\b|\boutlined\b', text):
        wish['outlines'] = True
    # "Remove the white background and stitch the rose" asks to leave it out, not keep it.
    if re.search(r'keep\b.{0,25}back ?ground|back ?ground.{0,20}\b(stitch|sew|fill|keep)', text) and not re.search(
            r'\b(remove|delete|erase|drop|cut|without|no|lose|get rid of|leave out|take out|take off)\b.{0,25}back ?ground'
            r'|back ?ground.{0,10}\b(removed|off|out|gone)\b', text):
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
        options.pop('fabric_custom', None)
    if wish.get('outlines') and kind == 'logo':
        # Add outlines: one dark running line around every colour, sewn last.
        options.update(outlines=True, outline_colour=wish.get('outline_colour', 'auto'))
    if wish.get('detail') == 'more' and kind in ('logo', 'photo'):
        options['floor_mm2'] = DETAIL_FLOOR_MM2[4]
        if not wish.get('colours'):
            if kind == 'photo':
                options.pop('photo_style', None)
                options['count'] = 6
            options['count'] = min(8, int(options.get('count', 4))+1)
    elif wish.get('detail') == 'less' and kind in ('logo', 'photo'):
        options['floor_mm2'] = DETAIL_FLOOR_MM2[2]
        if not wish.get('colours'):
            options['count'] = max(2, int(options.get('count', 4))-1)
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


def adjust(options, kind, issues, attempt, least=2, detail=None):
    """Next settings, or None when no rule applies. Returns (options, kind, why).
    least: fewest thread colours allowed (the picture's colour families stay apart).
    detail='more': the person asked for detail, so small parts and colours are not traded away."""
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
        if detail == 'more':
            if kinds <= {'cuts'}:
                return None   # cuts are the price of the detail asked for: keep it
            # Smoother edges and merged specks first; then one colour fewer at a time, never
            # merging different colour families (red and green stay apart).
            if floor < 2.5:
                nxt['floor_mm2'] = round(min(2.5, max(1.0, floor * 2.5)), 2)
                nxt['simplify'] = min(100, int(options.get('simplify', 0)) + 30)
                nxt['smooth'] = min(3, int(options.get('smooth', 1)) + 1)
                return nxt, kind, (f"Smoothing edges and merging only specks smaller than {nxt['floor_mm2']:g} mm² "
                                   "to make it sewable; your colours stay.")
            if kind == 'ink' or int(options.get('count', 4)) <= max(2, least):
                return None
            nxt['count'] = int(options.get('count', 4)) - 1
            return nxt, kind, (f"Using {nxt['count']} colours: thin bands of shading were too small to sew. "
                               "Different colours (like red and green) stay separate.")
        nxt['floor_mm2'] = round(min(25, max(2.5, floor * 2.5)), 1)
        nxt['simplify'] = min(100, int(options.get('simplify', 0)) + 30)
        nxt['smooth'] = min(3, int(options.get('smooth', 1)) + 1)
        why = f"Merging details smaller than {nxt['floor_mm2']} mm² and smoothing edges"
        if 'cuts' in kinds and kind != 'ink' and int(options.get('count', 4)) > max(2, least):
            nxt['count'] = int(options.get('count', 4)) - 1
            why += f", and using {nxt['count']} colours"
        return nxt, kind, why + ' to make it easier to sew.'
    return None


def size_differs(wish, result):
    """The size asked for and the size the files sew, when they differ by more than 3 %."""
    notes = []
    for key, label in (('width_mm', 'wide'), ('height_mm', 'high')):
        target, actual = (wish or {}).get(key), result.get(key)
        if target and actual is not None and abs(actual - target) / target > .03:
            notes.append(f'You asked for {target:g} mm {label}; the files sew {actual:g} mm {label}.')
    return notes


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
            job = dict(state='running', steps=[], request=request_text[:REQUEST_LIMIT], started=time.time(),
                       result=None, use_claude=bool(use_claude), choices=choices or {})
            self.jobs[path.name] = job
            if len(request_text) > REQUEST_LIMIT:
                self._log(job, f'Your request is {len(request_text):,} characters; only the first '
                               f'{REQUEST_LIMIT:,} are read. Shorten it if the rest matters.')
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
                # Photos on a plain background leave many one-pixel specks along the edge;
                # stay under preparation's 500 paint strokes.
                paint = self._paint_specks(path, blockers)[:max(0, 480-len(options.get('edits', [])))]
                if not paint:
                    break
                options = {**options, 'edits': [*options.get('edits', []), *paint]}
            response = client.post(url, json=dict(options=options, digitize=True, subject_confirmed=True))
            body = response.get_json(silent=True) or {}
        if response.status_code != 200:
            return dict(error=body.get('error') or f'Generation failed ({response.status_code}).'), options
        playback, report = body.get('playback') or {}, body.get('report') or {}
        # Size of the sewn design itself, not the canvas with its empty margins: as the written
        # DST sews it (export_proof.py), or from the preview when the files were not measured.
        sewn = [s for s in playback.get('steps', []) if s['t'] == 'stitch'] or [dict(x=0, y=0)]
        xs, ys = [s['x'] for s in sewn], [s['y'] for s in sewn]
        proof = playback.get('export_proof') or {}
        result = dict(stitches=playback.get('stitch_count', 0), trims=playback.get('trim_count', 0),
                      # Thread colours sewn; a thread used twice counts once.
                      colours=len({c.lower() for c in playback.get('colors', [])}), prepared=body.get('prepared_name'),
                      width_mm=proof.get('width_mm', round(max(xs) - min(xs), 1)),
                      height_mm=proof.get('height_mm', round(max(ys) - min(ys), 1)),
                      puff=playback.get('puff'))
        if keep_playback:
            result['playback'] = playback
        from .release_gate import checked_bytes, ReleaseError
        try:
            checked_bytes(self.root / 'work' / 'inkstitch-preview' / Path(result['prepared']).stem, 'dst')
        except ReleaseError as error:
            result['gate'] = str(error)
            result['gate_detail'] = getattr(error, 'explanation', None)
        return result, options

    def _keep_inside(self, path, options):
        """Parts of the removed background colour that lie well inside the subject are the
        subject's own (colour_knockout.inside_subject): keep them, as the Subject step's
        part list would. Returns how many."""
        body = self.app.test_client().post('/artwork/' + path.name, json=dict(options=options, subject_confirmed=True))
        removals = ((body.get_json(silent=True) or {}).get('report') or {}).get('colour_knockouts') or []
        if not removals:
            return 0
        ids = [p['id'] for p in removals[-1].get('parts', []) if p.get('inside') and not p.get('review_hole')]
        if ids:
            operation = options['colour_knockouts'][-1]
            operation['restore_parts'] = list(dict.fromkeys([*operation.get('restore_parts', []), *ids]))
        return len(ids)

    def _paint_specks(self, path, boxes, limit=200):
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
            elif facts.get('object_photo'):
                self._log(job, 'Looked at the picture: a photo of one object on a plain background; it is sewn in colour.')
            else:
                self._log(job, f'Looked at the picture: {KINDS[kind].lower()}.')
            if wish.get('detail') == 'more':
                self._log(job, 'You asked for detail: small parts and more colours are kept.')
            # Different colour families (red and green) are never merged into one thread on a retry.
            job['least'] = facts.get('hues', 0)+1 if facts.get('hues', 0) >= 2 else 2
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
                if facts.get('object_photo'):
                    # A photo's edge blends into the background, so removing that colour leaves
                    # specks along it and in the highlights. Cut the object out by shape instead
                    # (the Subject step's cut-out).
                    from .preparation import load_image
                    w, h = load_image(path).size
                    options.update(selection='grabcut', rect=[2, 2, w-2, h-2], hints=[], edge=-2)
                    self._log(job, 'Cutting the object out of its plain background; say “keep the background” to stitch it.')
                elif patch:
                    options.update(patch)
                    self._log(job, f"Leaving out the plain background ({patch['colour_knockouts'][-1]['colour']}); "
                                   "say “keep the background” to stitch it.")
                    kept = self._keep_inside(path, options)
                    if kept:
                        self._log(job, f"Keeping {kept} part{'s' if kept > 1 else ''} of that colour inside the design "
                                       "(a cloud in a sky, say); they are sewn, not left out.")
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
                    self._log(job, f'Claude could not help ({auto_claude.clip(error, 200)}). Switching to the built-in rules.')
                    attempts, finish = [], None
            if [a for a in attempts if not a.get('error')]:
                job['decided_by'] = f"Claude ({job.get('claude_model')}), Anthropic's AI"
            else:
                attempts = self._rules(job, path, kind, wish, options)
                job['decided_by'] = "Needler's built-in rules (no AI)"
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
        if (wish.get('detail') == 'more' or kind == 'photo') and options['height_mm'] < 150 \
                and not wish.get('height_mm') and not wish.get('width_mm'):
            # Thread is about 0.4 mm wide: folds and veins a few millimetres across need room.
            self._log(job, f"Tip: at {options['height_mm']:g} mm, small details become a few millimetres or less and merge. "
                           "For more detail, ask for a bigger size, for example “15 cm tall”.")
        attempts, fits = [], 0
        attempts_allowed = MAX_ATTEMPTS + (2 if wish.get('detail') == 'more' else 0)
        for number in range(1, attempts_allowed + 1):
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
            step = adjust(options, kind, issues, number, least=job.get('least', 2), detail=wish.get('detail'))
            if not step or number == attempts_allowed:
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
            best = {**restored, 'kind': best['kind'], 'number': best['number'], 'options': best['options'],
                    'plan': best.get('plan')}
        ok = not best.get('error') and not best.get('gate')
        job['result'] = dict(ok=ok, kind=best.get('kind', kind), facts=facts, attempts=len(attempts),
                             stitches=best.get('stitches'), trims=best.get('trims'), colours=best.get('colours'),
                             width_mm=best.get('width_mm'), height_mm=best.get('height_mm'),
                             problem=best.get('error') or best.get('gate'),
                             problem_detail=(best.get('gate_detail') or {}).get('text'),
                             # The error or file check is already the problem above.
                             issues=[i['text'] for i in assess(best) if i['kind'] not in ('error', 'gate')]
                             + ([] if best.get('error') else size_differs(wish, best)),
                             decided_by=job.get('decided_by'))
        if best.get('options', {}).get('puff') and not best.get('puff') and not best.get('error'):
            job['result']['issues'].append('3D puff was asked for, but no part is wide enough to hold the foam (3–6 mm, or 2–6 mm with 2 mm foam) at this size, so it is sewn flat. '
                                           'Try another size, 2 mm foam, or puff bold lettering instead.')
        elif best.get('puff'):
            job['result']['puff'] = best['puff']
        if finish:
            from .auto_claude import clip
            job['result'].update(summary=clip(finish.get('summary'), 800),
                                 check=[clip(c, 300) for c in finish.get('check', [])][:4],
                                 request=clip(finish.get('request'), 400),
                                 tools_used=[clip(t, 60) for t in finish.get('tools_used', [])
                                             if isinstance(t, str)][:10],
                                 plan=list(best.get('plan') or [])[:8])
        if job.get('claude_usd') is not None:
            job['result']['claude_usd'] = job['claude_usd']
        if job.get('claude_usd') is not None:
            # What this run taught, for Claude's next picture (lessons.py). Losing it never fails the run.
            from . import lessons
            try:
                lessons.record(self.decisions, best.get('kind', kind), job.get('request'), attempts)
            except OSError:
                pass
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
