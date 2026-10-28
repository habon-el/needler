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

The person's request leads. What they ask for (a style, a colour, a border, a size, a fabric, what to leave out) comes before every rule below, even when you would choose otherwise. Only what cannot sew or breaks the machine-file checks is not done; then say so and why, and do the closest thing that sews.

Work like a careful human digitizer:
- Look at the picture first. Decide what it is (light lines on dark, black ink drawing, flat-colour logo, \
photo) and what matters in it.
- On your first make_stitches call, give the plan: one line per thread colour (what it is in the picture, the style and why, in plain words). Give it again only when it changes.
- Call make_stitches with the settings you choose. Needler's own engine makes the stitches and runs the \
machine-file checks; you get the numbers back plus a drawing of the stitches. Look at that drawing \
critically: missing parts, lost detail, blobs, too many colours, broken lines, wrong size.
- Change only what the result tells you to change, then try again. You have at most {attempts} attempts.
- Keep the current size when the person gave none: change it only if the design cannot sew at that size, \nand then say why in the summary. Bigger designs mean more stitches, cuts and machine time.
- Sizes in the person's request refer to the sewn design itself. The tool reports the sewn size; \
height_mm sets the canvas, which may include empty margins, so rescale from the measured result.
- 3D puff (raised satin over foam) is available in colour mode. Use it when the person asks for puff, foam, raised or 3D. Only parts as wide as the foam is thick (3 mm for 3 mm foam, 2 mm for 2 mm foam) up to 6 mm puff; wider or thinner parts stay flat, and the result tells you which threads puffed. Bold lettering and outlines puff best; big solid areas and fine detail do not. If nothing puffs, change the size so the parts that matter fall in that range, and explain.
- Choose the fabric preset from the person's request: t-shirt is stretch_knit, polo is pique, \
hoodie is fleece, cap is cap, and so on. Unknown: keep the current one.
- Choose the mode by what the picture is. black_lines is only for clean black line drawings on a plain white background. Shaded black-and-white art (engravings, pencil, halftone or textured backgrounds; measured_facts.shaded) is photo_lines: black_lines turns shading into specks and a honeycomb of lines.
- Illustrations with fine linework (faces, highlights, hatching) lose those lines in colour mode: use line_details light or all, and check the drawing that the detail came back without clutter.
- per_colour in each result shows where the thread cuts come from. Many cuts in one colour mean it is \
scattered in small pieces: fold it into a neighbouring colour with merge_colours, merge small details, or \
simplify. Same-colour parts that touch are already joined without cutting (branching). per_colour also \
says what each colour's areas became: how many, their size, the widest part, the styles used, and \
style_refused with the reason when a style you chose did not suit some of its areas.
- A badge or patch usually wants a satin border; a logo on a shirt usually does not.
- Each thread colour can have its own area style and row direction (colour_styles), as the handbook \
describes. Use them where the art asks for it (gradient for a sky, satin for lettering, a different \
direction for neighbouring colours); the automatic choice is good for most areas. A big solid colour on a \
patch or jacket can be appliqué (colour_styles) when the person can cut and lay fabric.
- Cartoons with dark outlines in the art want outlines; tiny holes that cause cuts can be sewn over \
(colour_holes); density and sewing order stay as they are unless the fabric, the person or a sew-out asks.
- recent_sewouts (if any) are what the person saw on real fabric: correct for those first.
- If the person asks to keep the background, it must be stitched: use colour mode (line_art and black_lines leave the background as bare fabric).
- Pictures are often screenshots. Buttons, arrows, page dots, captions, watermarks or app frames are not part of the art: remove them with erase on your first attempt, and check the drawing that they are gone. With the whole picture stitched, an erase box is filled with the colour around it, so draw it just around the item.
- When you are satisfied, or out of attempts, call finish with the attempt to keep, how you followed the request (or what you could not do and why), and the tools you used.

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
             plan=dict(type='array', maxItems=8, description='Your plan, one line per thread colour; required on '
                       'the first call, then only when it changes.',
                       items=dict(type='object', additionalProperties=False, required=['colour', 'what', 'style', 'why'],
                                  properties=dict(colour=dict(type='string', pattern='^#[0-9a-fA-F]{6}$'),
                                                  what=dict(type='string', description='What it is in the picture, '
                                                            'a few words (sky, lettering, outline).'),
                                                  style=dict(type='string', description='How it is sewn, plain words.'),
                                                  why=dict(type='string', description='Why, a few plain words.')))),
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
             fabric=dict(type='string', description='Fabric it will be sewn on: sets density, pull compensation, '
                                                    'underlay and tie-offs (default twill).'),
             hoop=dict(type='string', description='Hoop it will be sewn in. Choose one only when the person names '
                                                  'their machine or hoop.'),
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
                         description='Outline around the whole design (colour mode): satin (1.6-6 mm wide, a clean '
                                     'badge edge), running (0.8-6 mm) or a decorative line stitch (width is the band '
                                     'it covers). style off removes it.',
                         properties=dict(style=dict(type='string'),
                                         width_mm=dict(type='number', minimum=.8, maximum=6),
                                         colour=dict(type='string', pattern='^#[0-9a-fA-F]{6}$'),
                                         motif=dict(type='string', description='Shape repeated by the motif border.'),
                                         pattern=dict(type='string', description='Shape of the pattern border.'),
                                         placement=dict(type='string', enum=['inside', 'center', 'outside'],
                                                        description='Satin only: the band lies inside the design\'s '
                                                                    'edge, on it (default) or outside it.'),
                                         line_inside=dict(type='boolean',
                                                          description='A triple-stitch line 1.2 mm inside the border, '
                                                                      'as on badges and frames.'))),
             colour_styles=dict(type='array', maxItems=8,
                                description='Stitch style and direction for every area of a thread colour (colour '
                                            'mode; thread colours from the latest result). Parts the style does not '
                                            'suit keep the automatic choice: satin only where satin forms, puff only '
                                            'as wide as the foam, fills and textures only on parts wider than about '
                                            '4.5 mm. Replaces earlier choices; [] returns every colour to automatic.',
                                items=dict(type='object', additionalProperties=False, required=['colour'],
                                           properties=dict(colour=dict(type='string', pattern='^#[0-9a-fA-F]{6}$'),
                                                           style=dict(type='string', description='Area style.'),
                                                           angle=dict(type='number', minimum=-180, maximum=180,
                                                                      description='Row direction in degrees, 0 = '
                                                                                  'horizontal; leave out for the '
                                                                                  'automatic one.')))),
             colour_holes=dict(type='array', maxItems=8,
                               description='Sew over the holes inside every area of a thread colour (colour mode): '
                                           'stitches run straight across, so no gap or extra cut opens at a tiny '
                                           'hole. Parts inside a hole that sew earlier are covered. Replaces earlier '
                                           'choices; [] keeps every hole open.',
                               items=dict(type='object', additionalProperties=False, required=['colour'],
                                          properties=dict(colour=dict(type='string', pattern='^#[0-9a-fA-F]{6}$'),
                                                          up_to_mm2=dict(type='number', minimum=.1, maximum=10000,
                                                                         description='Only holes up to this size are '
                                                                                     'sewn over; leave out for all.')))),
             sew_order=dict(type='string', enum=['colours', 'layers'],
                            description='colours (default): one pass per thread colour, fewest colour changes. '
                                        'layers: back to front, a part lying inside another is sewn after it even '
                                        'if its thread was used before (more colour changes, cleaner overlaps).'),
             density=dict(type='string', enum=['lighter', 'normal', 'denser'],
                          description='Space between fill rows and satin stitches for the whole design, on top of '
                                      'the fabric\'s own: lighter (12% wider, softer, fewer stitches), normal, denser '
                                      '(10% closer, more cover). Foam keeps its own.'),
             applique=dict(type='object', additionalProperties=False,
                           description='How appliqué pieces (style applique) work together; leave out to keep '
                                       'each piece on its own with a full satin edge.',
                           properties=dict(partial=dict(type='boolean', description='Fabric runs on under the parts '
                                                        'sewn on top of it; that edge gets no satin.'),
                                           combine=dict(type='boolean', description='Pieces of one colour share '
                                                        'their two stops.'),
                                           join=dict(type='boolean', description='Where two pieces meet, only '
                                                     "the later piece's satin covers the join."))),
             outlines=dict(type='object', additionalProperties=False, required=['on'],
                           description='Running-stitch outlines along the edges between colour areas (colour mode), '
                                       'sewn after all fills.',
                           properties=dict(on=dict(type='boolean'),
                                           colour=dict(type='string', pattern='^(#[0-9a-fA-F]{6}|auto)$',
                                                       description='One thread colour, or auto: a darker shade of '
                                                                   'each part\'s own thread (default #202020).'))),
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
             request=dict(type='string', description='One plain sentence: how you followed the person\'s request, '
                                                     'or what you could not do and why. Leave out when there was none.'),
             tools_used=dict(type='array', maxItems=10, items=dict(type='string'),
                             description='The tools you used, in plain words (satin border, gradient fill, holes '
                                         'sewn over, merged colours).'),
             check=dict(type='array', items=dict(type='string'), maxItems=4,
                        description='Specific things the person should look at before sewing, if any.'),
         ))),
]


def catalog(root=None):
    """Every listed choice Claude may make, read from Needler's own lists, so a style, border,
    fabric or hoop added to the app reaches Claude with it. root adds the person's own fabrics
    and hoops."""
    from . import custom_fabrics, hoops
    from .borders import OUTLINES
    from .generation_policy import presets
    from .region_stitches import CATALOG, VARIANTS
    from .stitch_paths import MOTIFS, PATTERNS
    fabrics = [dict(id=r['fabric'], name=r['label']) for r in presets()]
    listed = [dict(id=h['id'], name=f"{g['brand']} {h['name']}", width_mm=h['width_mm'], height_mm=h['height_mm'])
              for g in hoops.listed() for h in g['hoops']]
    if root is not None:
        for fabric in custom_fabrics.saved(Path(root)):
            try:
                custom_fabrics.check(fabric)
            except ValueError:
                continue
            if isinstance(fabric.get('id'), str):
                fabrics.append(dict(id=fabric['id'], name=fabric['name'] + ' (their own)', base=fabric['base']))
        listed += [dict(id=h['id'], name=h['name'] + ' (their own)', width_mm=h['width_mm'], height_mm=h['height_mm'])
                   for h in hoops.saved(Path(root)) if isinstance(h.get('id'), str)]
    return dict(fabrics=fabrics, hoops=listed, borders=['off', 'running', 'satin', *OUTLINES],
                motifs=list(MOTIFS), patterns=list(PATTERNS),
                area_styles=[dict(id=k, name=n, note=t) for k, n, t in CATALOG] +
                            [dict(id=f'{k}:{v}', name=f'{dict((c[0], c[1]) for c in CATALOG)[k]}: {n}')
                             for k, choices in VARIANTS.items() for v, n in choices[1:]])


def tools(root=None):
    """TOOLS with every list filled in from catalog(root)."""
    import copy
    lists = catalog(root)
    built = copy.deepcopy(TOOLS)
    settings = built[0]['input_schema']['properties']
    settings['fabric'].update(enum=[f['id'] for f in lists['fabrics']])
    settings['fabric']['description'] += ' ' + '; '.join(f"{f['id']}: {f['name']}" for f in lists['fabrics']) + '.'
    settings['hoop'].update(enum=[h['id'] for h in lists['hoops']])
    settings['hoop']['description'] += ' Sewing field width x height: ' + '; '.join(
        f"{h['id']}: {h['name']} {h['width_mm']:g}x{h['height_mm']:g} mm" for h in lists['hoops']) + '.'
    border = settings['border']['properties']
    border['style']['enum'] = lists['borders']
    border['motif']['enum'] = lists['motifs']
    border['pattern']['enum'] = lists['patterns']
    style = settings['colour_styles']['items']['properties']['style']
    style['enum'] = [s['id'] for s in lists['area_styles']]
    style['description'] += ' ' + '; '.join(f"{s['id']}: {s['name']}" for s in lists['area_styles']) + '.'
    return built


HANDBOOK_PARTS = (('mode', 'Modes'), ('area', 'Area styles (per colour area)'), ('border', 'Borders'),
                  ('setting', 'Settings'), ('concept', 'How Needler sews'))


def handbook():
    """The digitizer's handbook (knowledge/handbook.json) as text for Claude: every Needler tool,
    what it does, when to use it, when not, its limits; fabrics come from the fabric presets."""
    from .generation_policy import presets
    rows = json.loads(Path(__file__).with_name('knowledge').joinpath('handbook.json').read_text(encoding='utf-8'))['rows']
    lines = ["# Digitizer's handbook",
             "Every Needler tool: what it does, when to use it, when not, its limits. Tools marked "
             "(make_stitches: x) are yours to set with that setting; Needler applies the others itself "
             "or the person picks them in the studio. Know them all to judge each result and explain it."]
    for part, title in HANDBOOK_PARTS:
        lines += ['', '## ' + title]
        for row in rows:
            kind, _, ident = row['id'].partition(':')
            if kind != part:
                continue
            head = f"- {ident} ({row['tool']}" + (f"; make_stitches: {row['control']}" if row.get('control') else '') + ')'
            lines.append(f"{head}: {row['does']} Use: {row['use']} Avoid: {row['avoid']} Limits: {row['limits']}")
    lines += ['', '## Fabrics (density, pull, backing)']
    for r in presets():
        lines.append(f"- {r['fabric']} ({r['label']}): rows {r['row_spacing_mm']:g} mm, satin pull {r['satin_pull_mm']:g} mm, "
                     f"stitches up to {r['max_stitch_length_mm']:g} mm, " + ('underlay' if r['fill_underlay'] else 'no fill underlay') +
                     f". Backing: {r['backing']}" + (f"; topping: {r['topping']}" if r.get('topping') else '') + '.')
    return '\n'.join(lines)


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
    """Per thread colour: its cuts and what its areas became (count, sizes, widest part, styles
    used, and why a style chosen for the colour was refused), from the sewn steps and the engine."""
    colours, counts, thread = playback.get('colors', []), {}, 0
    for step in playback.get('steps', []):
        if step['t'] == 'color_change':
            thread += 1
        elif step['t'] == 'trim' and thread < len(colours):
            counts[colours[thread]] = counts.get(colours[thread], 0) + 1
    areas = {}
    for area in playback.get('areas', []):
        areas.setdefault(area['thread'].lower(), []).append(area)
    report = []
    for colour in dict.fromkeys(colours):
        row, own = dict(colour=colour, cuts=counts.get(colour, 0)), areas.get(colour.lower(), [])
        if own:
            styles, refused = {}, {}
            for area in own:
                styles[area['style']] = styles.get(area['style'], 0) + 1
                if area.get('refused'):
                    refused.setdefault((area['asked'], area['refused']), []).append(area)
            row.update(areas=len(own), area_mm2=round(sum(a['mm2'] for a in own), 1),
                       largest_mm2=max(a['mm2'] for a in own), widest_mm=max(a['width_mm'] for a in own),
                       styles_used=styles)
            if refused:
                row['style_refused'] = [dict(style=asked, areas=len(parts), why=why)
                                        for (asked, why), parts in list(refused.items())[:3]]
        report.append(row)
    return report


def plan_lines(plan):
    """Claude's plan as short lines for the person: 'Sky (#88aadd): gradient fill - soft blend'."""
    lines = []
    for item in plan[:8]:
        if not isinstance(item, dict):
            continue
        what, style, why = (str(item.get(k) or '').strip()[:80] for k in ('what', 'style', 'why'))
        if what and style:
            colour = str(item.get('colour') or '')[:7]
            lines.append(f"{what[0].upper() + what[1:]}{f' ({colour})' if colour else ''}: {style}" +
                         (f' - {why}' if why else ''))
    return lines


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


def settings_from(tool_input, options, size=None, image=None, root=None):
    nxt = dict(options)
    lists = catalog(root)
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
    if isinstance(border, dict) and border.get('style') in lists['borders']:
        nxt['border_style'] = border['style']
        if border['style'] != 'off':
            nxt['border_width'] = float(border.get('width_mm', {'satin': 2.5, 'running': 1.0}.get(border['style'], 2.0)))
            if border.get('colour'):
                nxt['border_colour'] = border['colour'].lower()
            for key, name in (('motif', 'motifs'), ('pattern', 'patterns')):
                if border.get(key) in lists[name]:
                    nxt['border_' + key] = border[key]
            if border.get('placement') in ('inside', 'center', 'outside'):
                nxt['border_placement'] = border['placement']
            if 'line_inside' in border:
                nxt['border_inner'] = 'triple' if border['line_inside'] is True else 'off'
    if isinstance(tool_input.get('colour_styles'), list):
        styles = {s['id'] for s in lists['area_styles']}
        nxt['colour_styles'], nxt['colour_angles'] = {}, {}
        for item in tool_input['colour_styles'][:8]:
            colour = item.get('colour') if isinstance(item, dict) else None
            if not (isinstance(colour, str) and len(colour) == 7 and colour[0] == '#'):
                continue
            if item.get('style') in styles:
                nxt['colour_styles'][colour.lower()] = item['style']
            if type(item.get('angle')) in (int, float) and -180 <= item['angle'] <= 180:
                nxt['colour_angles'][colour.lower()] = item['angle']
    if isinstance(tool_input.get('colour_holes'), list):
        nxt['colour_holes'] = {}
        for item in tool_input['colour_holes'][:8]:
            colour = item.get('colour') if isinstance(item, dict) else None
            if not (isinstance(colour, str) and len(colour) == 7 and colour[0] == '#'):
                continue
            limit = item.get('up_to_mm2')
            nxt['colour_holes'][colour.lower()] = limit if type(limit) in (int, float) and 0 < limit <= 10000 else 'all'
    for key, allowed in (('sew_order', ('colours', 'layers')), ('density', ('lighter', 'normal', 'denser'))):
        if tool_input.get(key) in allowed:
            nxt[key] = tool_input[key]
    applique = tool_input.get('applique')
    if isinstance(applique, dict):
        for name in ('partial', 'combine', 'join'):
            if isinstance(applique.get(name), bool):
                nxt['applique_'+name] = applique[name]
    outlines = tool_input.get('outlines')
    if isinstance(outlines, dict) and isinstance(outlines.get('on'), bool):
        nxt['outlines'] = outlines['on']
        colour = outlines.get('colour')
        if colour == 'auto' or isinstance(colour, str) and len(colour) == 7 and colour[0] == '#':
            nxt['outline_colour'] = colour.lower()
    if tool_input.get('line_details') in ('off', 'light', 'all'):
        nxt['line_details'] = tool_input['line_details']
    fabric = next((f for f in lists['fabrics'] if f['id'] == tool_input.get('fabric')), None)
    if fabric and 'base' in fabric:
        # The person's own fabric: stored whole, as the fabric menu does, so the design keeps
        # sewing the same if they later change or delete it.
        from .custom_fabrics import saved
        nxt.update(fabric_preset=fabric['base'],
                   fabric_custom=next(f for f in saved(Path(root)) if f.get('id') == fabric['id']))
    elif fabric:
        nxt['fabric_preset'] = fabric['id']
        nxt.pop('fabric_custom', None)
    hoop = next((h for h in lists['hoops'] if h['id'] == tool_input.get('hoop')), None)
    if hoop:
        nxt.update(hoop_id=hoop['id'], piece_hoop_mm=[hoop['width_mm'], hoop['height_mm']])
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
    root = Path(path).parent.parent.parent
    offered = tools(root)
    # The handbook rides with the instructions and is cached with them across attempts and runs.
    system = [dict(type='text', text=SYSTEM.format(attempts=MAX_ATTEMPTS)),
              dict(type='text', text=handbook(), cache_control=dict(type='ephemeral'))]
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
                     'selection', 'fabric_preset', 'line_details', 'photo_style', 'hoop_id', 'border_style',
                     'border_placement', 'border_inner', 'colour_styles', 'colour_angles', 'colour_holes',
                     'sew_order', 'density', 'outlines', 'outline_colour', 'applique_partial', 'applique_combine',
                     'applique_join')}, selection_meaning='full: whole picture is stitched; anything else: only the '
                     'saved subject cut-out is stitched and the background is left as bare fabric')
    messages = [dict(role='user', content=[picture, dict(type='text', text=
        'Here is the picture to digitize and what Needler measured:\n' + json.dumps(brief, indent=1))])]
    attempts, finish, plan = [], None, []
    while finish is None:
        problem = spend.room()
        if problem:
            log(problem + ' Keeping the best attempt so far.')
            break
        response = client.beta.messages.create(
            model=MODEL, max_tokens=16000, system=system, tools=offered,
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
            if isinstance(data.get('plan'), list) and data['plan']:
                plan = plan_lines(data['plan'])
                for line in plan:
                    log('Plan: ' + line)
            options = settings_from(data, options, size, pixels, root)
            number = len(attempts) + 1
            log(f'Attempt {number}: making stitches…')
            result, options = attempt(options)
            result.update(options=options, number=number, kind=('line_art' if options.get('line_art') else
                                                               'ink' if options.get('ink_only') else 'logo'))
            result['plan'] = plan
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
