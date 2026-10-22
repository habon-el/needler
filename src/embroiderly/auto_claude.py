"""Claude as the digitizer's judgement: looks at the picture, chooses settings,
makes stitches through Needler's own engine, looks at the result, and decides
what to change. Claude only calls the two tools below; Needler's preparation,
engine and release gate do all the stitching and checking.

Spending is capped per run and in total (prepaid credit protection). The key
comes from ANTHROPIC_API_KEY in the environment and is never stored or logged.
"""
import base64
import io
import json
import os
import time
from pathlib import Path

from PIL import Image, ImageDraw

MODEL = 'claude-opus-5-5'
# Claude Opus 5.5 prices, US dollars per token.
PRICE = dict(input=4e-6, output=20e-6, cache_write=5e-6, cache_read=.2e-6)
RUN_LIMIT = float(os.environ.get('NEEDLER_CLAUDE_RUN_LIMIT_USD', '0.40'))
TOTAL_LIMIT = float(os.environ.get('NEEDLER_CLAUDE_TOTAL_LIMIT_USD', '4.50'))
MAX_ATTEMPTS = 5

SYSTEM = """You are an expert machine-embroidery digitizer working inside Needler, a local digitizing app, \
for a beginner who cannot judge stitch settings themselves.

You get the person's picture, measured facts about it, and their optional request. Your job: get a design \
that sews cleanly at the size they want, with as few thread cuts and colour changes as the art allows, \
and that still looks like the picture.

Work like a careful human digitizer:
- Look at the picture first. Decide what it is (light lines on dark, black ink drawing, flat-colour logo, \
photo) and what matters in it.
- Call make_stitches with the settings you choose. Needler's own engine makes the stitches and runs the \
machine-file checks; you get the numbers back plus a drawing of the stitches. Look at that drawing \
critically: missing parts, lost detail, blobs, too many colours, broken lines, wrong size.
- Change only what the result tells you to change, then try again. You have at most {attempts} attempts.
- Keep the current size when the person gave none: change it only if the design cannot sew at that size, \nand then say why in the summary. Bigger designs mean more stitches, cuts and machine time.
- Sizes in the person's request refer to the sewn design itself. The tool reports the sewn size; \
height_mm sets the canvas, which may include empty margins, so rescale from the measured result.
- 3D puff (raised satin over foam) is available in colour mode. Use it when the person asks for puff, foam, raised or 3D. Only parts as wide as the foam is thick (3 mm for 3 mm foam, 2 mm for 2 mm foam) up to 6 mm puff; wider or thinner parts stay flat, and the result tells you which threads puffed. Bold lettering and outlines puff best; big solid areas and fine detail do not. If nothing puffs, change the size so the parts that matter fall in that range, and explain.
- Choose the fabric (Auto Fabric) from the person's request: t-shirt is stretch_knit, polo is pique, \
hoodie is fleece, cap is cap, and so on. Unknown: keep the current one.
- Choose the mode by what the picture is. black_lines is only for clean black line drawings on a plain white background. Shaded black-and-white art (engravings, pencil, halftone or textured backgrounds; measured_facts.shaded) is photo_lines: black_lines turns shading into specks and a honeycomb of lines.
- Illustrations with fine linework (faces, highlights, hatching) lose those lines in colour mode: use line_details light or all, and check the drawing that the detail came back without clutter.
- per_colour in each result shows where the thread cuts come from. Many cuts in one colour mean it is \
scattered in small pieces: fold it into a neighbouring colour with merge_colours, merge small details, or \
simplify. Same-colour parts that touch are already joined without cutting (branching).
- A badge or patch usually wants a satin border; a logo on a shirt usually does not.
- recent_sewouts (if any) are what the person saw on real fabric: correct for those first.
- If the person asks to keep the background, it must be stitched: use colour mode (line_art and black_lines leave the background as bare fabric).
- Pictures are often screenshots. Buttons, arrows, page dots, captions, watermarks or app frames are not part of the art: remove them with erase on your first attempt, and check the drawing that they are gone. With the whole picture stitched, an erase box is filled with the colour around it, so draw it just around the item.
- When you are satisfied, or out of attempts, call finish with the attempt to keep.

Every make_stitches call costs the person money and about 5 to 60 seconds, so do not try settings \
that cannot help. Write the note and summary fields for a beginner: short, plain words, no jargon. \
Never claim a design is safe to sew; a sample sew-out is always needed."""

TOOLS = [
    dict(name='make_stitches',
         description='Make stitches from the picture with these settings using Needler\'s engine, run the '
                     'machine-file checks, and return the measured result with a drawing of the stitches. '
                     'Settings you leave out keep their previous value.',
         input_schema=dict(type='object', additionalProperties=False, required=['note'], properties=dict(
             note=dict(type='string', description='One short sentence for the person: what you are trying and why.'),
             mode=dict(type='string', enum=['colour', 'line_art', 'black_lines', 'photo_lines'],
                       description='colour: fills and satin per colour area. line_art: light lines on a dark '
                                   'background become running stitches; the background stays empty. black_lines: '
                                   'black drawing on white; white stays empty. photo_lines: a photo in one thread '
                                   '(rows of zigzag whose width follows the shading; one continuous thread, few cuts) - '
                                   'usually the best choice for real photos and portraits.'),
             photo=dict(type='object', additionalProperties=False, description='photo_lines settings.',
                        properties=dict(row_mm=dict(type='number', minimum=.6, maximum=2,
                                                    description='Row spacing (default 1.0). Smaller = more detail and stitches.'),
                                        angle=dict(type='number', minimum=-180, maximum=180,
                                                   description='Row direction in degrees (default 0, horizontal).'),
                                        light_thread=dict(type='boolean',
                                                          description='Light thread on dark fabric (tones inverted).'),
                                        thread=dict(type='string', pattern='^#[0-9a-fA-F]{6}$'))),
             colours=dict(type='integer', minimum=2, maximum=8, description='Thread colours (colour mode).'),
             height_mm=dict(type='number', minimum=3, maximum=400, description='Canvas height in mm, margins included.'),
             merge_small_mm2=dict(type='number', minimum=0, maximum=25,
                                  description='Colour areas smaller than this are merged into neighbours (default 1).'),
             simplify=dict(type='integer', minimum=0, maximum=100, description='Simplify fine detail, 0 to 100 (default 0).'),
             smooth=dict(type='integer', minimum=0, maximum=3, description='Smooth colour boundaries, 0 to 3 (default 1).'),
             puff=dict(type='boolean', description='3D puff: raise parts 3-6 mm wide (2-6 mm on 2 mm foam) as satin over foam '
                                                   '(colour mode). The machine stops so foam can be placed.'),
             foam_mm=dict(type='number', enum=[2, 3], description='Puff foam thickness (default 3).'),
             fabric=dict(type='string', enum=['twill', 'cotton', 'denim', 'stretch_knit', 'pique', 'fleece', 'towel',
                                              'satin_silk', 'nylon', 'cap'],
                         description='Auto Fabric: sets density, pull compensation, underlay and tie-offs for the '
                                     'fabric it will be sewn on (default twill).'),
             line_details=dict(type='string', enum=['off', 'light', 'all'],
                               description='Mixed mode (colour mode): thin lines the fills lose are sewn on top as '
                                           'running stitches. light: light lines only (highlights, a white face on '
                                           'black). all: dark lines too (pen hatching). More detail, more stitches.'),
             merge_colours=dict(type='array', maxItems=6,
                                description='Fold a colour into another (thread colours from the latest result, '
                                            'same colour count): fewer scattered pieces and cuts. Replaces earlier merges.',
                                items=dict(type='object', additionalProperties=False, required=['colour', 'into'],
                                           properties=dict(colour=dict(type='string', pattern='^#[0-9a-fA-F]{6}$'),
                                                           into=dict(type='string', pattern='^#[0-9a-fA-F]{6}$')))),
             border=dict(type='object', additionalProperties=False, required=['style'],
                         description='Outline around the whole design: satin (1.6-6 mm wide, a clean badge edge) or '
                                     'running (0.8-6 mm). style off removes it.',
                         properties=dict(style=dict(type='string', enum=['off', 'running', 'satin']),
                                         width_mm=dict(type='number', minimum=.8, maximum=6),
                                         colour=dict(type='string', pattern='^#[0-9a-fA-F]{6}$'))),
             keep_background=dict(type='boolean', description='true: stitch the whole picture, background included '
                                  '(clears any saved subject cut-out). false: keep the current subject selection.'),
             erase=dict(type='array', maxItems=12, description='Boxes to remove from the picture before stitching '
                        '(screenshot buttons, page dots, captions, watermarks). Each box is fractions of the picture: '
                        '0,0 is the top left and 1,1 the bottom right. Replaces earlier erase boxes; [] removes none.',
                        items=dict(type='object', additionalProperties=False, required=['x0', 'y0', 'x1', 'y1'],
                                   properties={k: dict(type='number', minimum=0, maximum=1) for k in ('x0', 'y0', 'x1', 'y1')})),
             line_retrace_mm=dict(type='number', minimum=2, maximum=30,
                                  description='line_art only: how far the needle may travel back over sewn lines '
                                              'instead of cutting the thread (default 6). Higher means fewer cuts.'),
         ))),
    dict(name='finish',
         description='Stop and keep one attempt. Call this exactly once, at the end.',
         input_schema=dict(type='object', additionalProperties=False, required=['attempt', 'summary'], properties=dict(
             attempt=dict(type='integer', minimum=1, description='The attempt number to keep.'),
             summary=dict(type='string', description='Two or three plain sentences: what you made and why.'),
             check=dict(type='array', items=dict(type='string'), maxItems=4,
                        description='Specific things the person should look at before sewing, if any.'),
         ))),
]


def available():
    import importlib.util
    return bool(os.environ.get('ANTHROPIC_API_KEY')) and importlib.util.find_spec('anthropic') is not None


def png_block(image, side=1024):
    image = image.convert('RGB')
    image.thumbnail((side, side))
    data = io.BytesIO()
    image.save(data, 'PNG', optimize=True)
    return dict(type='image', source=dict(type='base64', media_type='image/png',
                                          data=base64.standard_b64encode(data.getvalue()).decode()))


def draw_stitches(playback, side=900):
    """Flat drawing of the sewn path (jumps omitted) for Claude to look at."""
    sewn, prior = [], None
    for step in playback.get('steps', []):
        if step['t'] == 'stitch' and prior is not None:
            sewn.append((prior, (step['x'], step['y']), step.get('color', '#000000')))
        prior = (step['x'], step['y'])
    if not sewn:
        return Image.new('RGB', (200, 200), '#d8d2c4')
    xs = [p[0] for a, b, _ in sewn for p in (a, b)]
    ys = [p[1] for a, b, _ in sewn for p in (a, b)]
    x0, y0, w, h = min(xs), min(ys), max(max(xs) - min(xs), 1), max(max(ys) - min(ys), 1)
    scale = (side - 40) / max(w, h)
    image = Image.new('RGB', (int(w * scale) + 40, int(h * scale) + 40), '#d8d2c4')
    draw = ImageDraw.Draw(image)
    width = max(1, round(.35 * scale))
    for a, b, colour in sewn:
        draw.line([(20 + (a[0] - x0) * scale, 20 + (a[1] - y0) * scale),
                   (20 + (b[0] - x0) * scale, 20 + (b[1] - y0) * scale)], fill=colour, width=width)
    return image


class Spend:
    """Running cost of one job, plus a persisted all-time total."""

    def __init__(self, store):
        self.store, self.run = Path(store), 0.0
        self.total = json.loads(self.store.read_text()).get('usd', 0.0) if self.store.is_file() else 0.0

    def add(self, usage):
        cost = (usage.input_tokens * PRICE['input'] + usage.output_tokens * PRICE['output'] +
                (usage.cache_creation_input_tokens or 0) * PRICE['cache_write'] +
                (usage.cache_read_input_tokens or 0) * PRICE['cache_read'])
        self.run += cost
        self.total += cost
        self.store.write_text(json.dumps(dict(usd=round(self.total, 6))))

    def room(self):
        if self.total >= TOTAL_LIMIT:
            return f'Needler has used ${self.total:.2f} of Claude credit, its ${TOTAL_LIMIT:.2f} limit.'
        if self.run >= RUN_LIMIT:
            return f'This design reached its ${RUN_LIMIT:.2f} Claude limit.'
        return None


def per_colour(playback):
    """[{colour, cuts}] per thread, from the sewn steps."""
    colours, counts, thread = playback.get('colors', []), {}, 0
    for step in playback.get('steps', []):
        if step['t'] == 'color_change':
            thread += 1
        elif step['t'] == 'trim' and thread < len(colours):
            counts[colours[thread]] = counts.get(colours[thread], 0) + 1
    return [dict(colour=c, cuts=counts.get(c, 0)) for c in dict.fromkeys(colours)]


def recent_sewouts(work, limit=5):
    """The latest sew-out reviews the person recorded (Needler's sew-out review), newest first."""
    import sqlite3
    store = Path(work) / 'sewout-history.sqlite3'
    if not store.is_file():
        return []
    try:
        with sqlite3.connect(store) as db:
            rows = db.execute('SELECT design, created, report FROM sewout_history ORDER BY created DESC LIMIT ?',
                              (limit,)).fetchall()
    except sqlite3.Error:
        return []
    return [dict(design=d, when=time.strftime('%Y-%m-%d', time.localtime(c)), report=r[:1200]) for d, c, r in rows]


def settings_from(tool_input, options, size=None, image=None):
    nxt = dict(options)
    if tool_input.get('keep_background') is True:
        nxt['selection'] = 'full'
        nxt.pop('rect', None)
    if isinstance(tool_input.get('erase'), list) and size:
        # Claude's boxes become the same edits the Erase area tool makes. When the whole
        # picture is stitched, a hole would show bare fabric, so the box is painted with
        # the commonest colour along its edge instead (a button on a black background
        # becomes black).
        w, h = size
        edits = [e for e in nxt.get('edits', []) if not e.get('claude')]
        for box in tool_input['erase'][:12]:
            try:
                x0, x1 = sorted(min(w-1, max(0, float(box[k])*w)) for k in ('x0', 'x1'))
                y0, y1 = sorted(min(h-1, max(0, float(box[k])*h)) for k in ('y0', 'y1'))
            except (KeyError, TypeError, ValueError):
                continue
            if x1-x0 >= 1 and y1-y0 >= 1:
                edit = dict(kind='erase', shape='polygon', radius=1, claude=True,
                            points=[[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
                if nxt.get('selection', 'full') == 'full' and image is not None:
                    import numpy as np
                    a, b = int(x0), int(y0); c, d = int(x1)+1, int(y1)+1
                    edge = np.concatenate([image[b, a:c], image[d-1, a:c], image[b:d, a], image[b:d, c-1]])
                    values, counts = np.unique(edge, axis=0, return_counts=True)
                    edit.update(kind='paint', colour='#%02x%02x%02x' % tuple(int(v) for v in values[counts.argmax()]))
                edits.append(edit)
        nxt['edits'] = edits
    if isinstance(tool_input.get('merge_colours'), list):
        nxt['merges'] = {m['colour'].lower(): m['into'].lower() for m in tool_input['merge_colours']
                         if isinstance(m, dict) and isinstance(m.get('colour'), str) and isinstance(m.get('into'), str)
                         and m['colour'].lower() != m['into'].lower()}
    border = tool_input.get('border')
    if isinstance(border, dict) and border.get('style') in ('off', 'running', 'satin'):
        nxt['border_style'] = border['style']
        if border['style'] != 'off':
            nxt['border_width'] = float(border.get('width_mm', 2.5 if border['style'] == 'satin' else 1.0))
            if border.get('colour'):
                nxt['border_colour'] = border['colour'].lower()
    if tool_input.get('line_details') in ('off', 'light', 'all'):
        nxt['line_details'] = tool_input['line_details']
    if tool_input.get('fabric'):
        nxt['fabric_preset'] = tool_input['fabric']
    mode = tool_input.get('mode')
    if mode:
        nxt.update(line_art=mode == 'line_art', ink_only=mode == 'black_lines')
        if mode == 'photo_lines':
            nxt.update(photo_style='one_colour', count=2)
        else:
            nxt.pop('photo_style', None)
    photo = tool_input.get('photo')
    if isinstance(photo, dict):
        for key, name in (('row_mm', 'photo_row_mm'), ('angle', 'photo_angle'), ('thread', 'photo_thread')):
            if key in photo:
                nxt[name] = photo[key]
        if 'light_thread' in photo:
            nxt['photo_light_thread'] = photo['light_thread'] is True
    if 'puff' in tool_input:
        nxt['puff'] = tool_input['puff'] is True
    if 'foam_mm' in tool_input:
        nxt['puff_foam_mm'] = tool_input['foam_mm']
    for key, name in (('colours', 'count'), ('height_mm', 'height_mm'), ('merge_small_mm2', 'floor_mm2'),
                      ('simplify', 'simplify'), ('smooth', 'smooth'), ('line_retrace_mm', 'line_retrace_mm')):
        if key in tool_input:
            nxt[name] = tool_input[key]
    return nxt


def run(job, path, kind, facts, wish, options, attempt, log, client=None):
    """Drive one design with Claude. attempt(options) -> (result, options).
    Returns (attempts, finish) or raises; the caller falls back to the rules."""
    import anthropic
    client = client or anthropic.Anthropic(max_retries=2, timeout=180)
    spend = Spend(Path(path).parent.parent / 'decisions' / 'claude-spend.json')
    if spend.room():
        raise RuntimeError(spend.room())
    with Image.open(path) as image:
        picture = png_block(image)
    # Erase boxes are edits on the working picture (at most 768 px), not the upload.
    from .preparation import load_image
    import numpy as np
    frame = load_image(path)
    size, pixels = frame.size, np.asarray(frame.convert('RGB'))
    brief = dict(measured_facts=facts, first_guess=kind, request=job['request'] or '(none)',
                 recent_sewouts=recent_sewouts(Path(path).parent.parent),
                 parsed_request=wish, current_settings={k: options.get(k) for k in (
                     'line_art', 'ink_only', 'count', 'height_mm', 'floor_mm2', 'simplify', 'smooth', 'puff',
                     'selection', 'fabric_preset', 'line_details', 'photo_style')}, selection_meaning='full: whole picture is stitched; anything else: only the '
                     'saved subject cut-out is stitched and the background is left as bare fabric')
    messages = [dict(role='user', content=[picture, dict(type='text', text=
        'Here is the picture to digitize and what Needler measured:\n' + json.dumps(brief, indent=1))])]
    attempts, finish = [], None
    while finish is None:
        problem = spend.room()
        if problem:
            log(problem + ' Keeping the best attempt so far.')
            break
        response = client.beta.messages.create(
            model=MODEL, max_tokens=16000, system=SYSTEM.format(attempts=MAX_ATTEMPTS), tools=TOOLS,
            messages=messages, output_config=dict(effort='medium'), cache_control=dict(type='ephemeral'),
            betas=['server-side-fallback-2026-07-01'], fallbacks='default')
        spend.add(response.usage)
        job['claude_usd'] = round(spend.run, 4)
        if response.stop_reason == 'refusal':
            raise RuntimeError('Claude declined this picture.')
        if response.stop_reason == 'max_tokens':
            raise RuntimeError('Claude\'s reply was cut off.')
        messages.append(dict(role='assistant', content=response.content))
        calls = [b for b in response.content if b.type == 'tool_use']
        if not calls:
            break
        results = []
        for call in calls:
            data = call.input if isinstance(call.input, dict) else {}
            if call.name == 'finish':
                finish = data
                results.append(dict(type='tool_result', tool_use_id=call.id, content='Finished.'))
                continue
            if call.name != 'make_stitches' or not isinstance(data.get('note'), str):
                results.append(dict(type='tool_result', tool_use_id=call.id, is_error=True, content='Unknown tool or missing note.'))
                continue
            if len(attempts) >= MAX_ATTEMPTS:
                results.append(dict(type='tool_result', tool_use_id=call.id, is_error=True,
                                    content=f'No attempts left. Call finish with one of attempts 1-{len(attempts)}.'))
                continue
            log('Claude: ' + data['note'][:240])
            options = settings_from(data, options, size, pixels)
            number = len(attempts) + 1
            log(f'Attempt {number}: making stitches…')
            result, options = attempt(options)
            result.update(options=options, number=number, kind=('line_art' if options.get('line_art') else
                                                               'ink' if options.get('ink_only') else 'logo'))
            attempts.append(result)
            if result.get('error'):
                log(f'Attempt {number}: ' + result['error'][:240])
                results.append(dict(type='tool_result', tool_use_id=call.id, is_error=True,
                                    content=f"Attempt {number} failed: {result['error']}"))
                continue
            summary = {k: result.get(k) for k in ('stitches', 'trims', 'colours', 'width_mm', 'height_mm')}
            summary['per_colour'] = per_colour(result.get('playback') or {})
            summary.update(attempt=number, file_check=result.get('gate') or 'passed',
                           puff_threads=[t + 1 for t in (result.get('puff') or {}).get('threads', [])],
                           attempts_left=MAX_ATTEMPTS - len(attempts))
            log(f"Attempt {number}: {result['stitches']:,} stitches, {result['trims']} cuts, "
                f"{result['width_mm']:g} × {result['height_mm']:g} mm sewn" +
                ('.' if not result.get('gate') else '; file check failed.'))
            results.append(dict(type='tool_result', tool_use_id=call.id, content=[
                dict(type='text', text=json.dumps(summary)), png_block(draw_stitches(result['playback']))]))
        messages.append(dict(role='user', content=results))
    return attempts, finish
