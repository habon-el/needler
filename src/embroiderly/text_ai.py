"""Claude for the Text page: the person describes what they want ("curve it down, 3D puff
for a cap") and Claude chooses the text settings. Claude only calls the two tools below;
Needler's own advice check (small_lettering.advice) measures every choice, and nothing is
stitched until the screen presses Make stitches with the settings returned.

Spending shares auto_claude's per-run and total limits and its spend file.
"""
import json
from pathlib import Path

from . import auto_claude, small_lettering

MAX_TURNS = 8

SYSTEM = """You set up embroidery lettering inside Needler, a local digitizing app, for a beginner.

You get the person's current text settings, the fonts installed, and what they asked for. Choose the \
settings that do what they asked, then call check_text: Needler lays the letters out (no stitches yet) and \
tells you every problem, each with a suggested fix, plus the measured width. Fix the problems and check \
again. As soon as a check is clean, call finish with those settings; one to three checks are usually enough.

- Change only what the request is about; keep everything else as it is.
- Never change the words unless the person asks for different words.
- Curved text: shape arc_over is an arch (the middle is higher, like the top of a badge); arc_under is a \
smile (the middle is lower, like the bottom of a badge). "Curve down" or "curve at the bottom" means \
arc_under. curve_degrees is how far round a circle the words reach: 60 is gentle, 120 is strong, 180 is a half circle.
- Shape circle puts the words round a whole circle circle_mm across: the first line over the top, an optional \
second line along the bottom (a badge or patch ring). Shape wave is one S-shaped wave; wave_percent is how high \
it rises (3 gentle, 6 usual, 10 strong); short words need a gentle wave.
- Arch, smile and wave text must be one line; a circle takes at most two.
- fixed_length_mm spreads or squeezes the letters so one line is exactly that long (e.g. "make it exactly \
90 mm long"); leave it out otherwise. The check says the shortest or longest it can be.
- Monograms: initials as the words (e.g. "JAM"), classic true for the bigger middle initial, and a frame \
(circle, oval, square, diamond, hexagon, shield, heart) if asked. The frame makes the design bigger than the letters. \
An ornament (crown above, laurel round the sides and bottom, swirls left and right, divider line below) if asked.
- 3D puff needs a bold font with even strokes; the check lists which fonts can puff. Puff ignores fabric.
- Products: a cap front is usually 45-55 mm tall and at most about 110 mm wide; a left chest about 80-90 mm \
wide; a sleeve about 60-75 mm wide; a jacket back up to about 280 mm wide. Set max_width_mm to the space on \
the item. Fabric: t-shirt stretch_knit, polo pique, hoodie fleece, cap cap, towel towel.
- Write the note for a beginner: one or two short sentences in plain words, no jargon. Never claim the \
design is safe to sew; a sample sew-out is always needed."""

FIELDS = dict(  # tool name -> the screen's value name
    text='text', font='font', height_mm='height_mm', max_width_mm='available_width_mm', align='align',
    colour='colour', shape='baseline', curve_degrees='arc_degrees', letter_spacing_mm='letter_spacing_mm',
    line_spacing_percent='line_spacing_percent', sequence='sequence', puff='puff', foam_mm='puff_foam_mm',
    fabric='fabric_preset', frame='frame', frame_mm='frame_mm', classic='classic',
    ornament='ornament', circle_mm='circle_mm', wave_percent='wave_percent', fixed_length_mm='fit_length_mm')


def tools(fonts, fabrics):
    settings = dict(type='object', additionalProperties=False, description='Only the settings to change.', properties=dict(
        text=dict(type='string', maxLength=200, description='The words (only when the person asks for new words).'),
        font=dict(type='string', enum=sorted(fonts)),
        height_mm=dict(type='number', minimum=2, maximum=300, description='Height of the stitched words, all lines.'),
        max_width_mm=dict(type='number', minimum=5, maximum=400, description='The widest the words may be on the item.'),
        align=dict(type='string', enum=['left', 'center', 'right']),
        colour=dict(type='string', pattern='^#[0-9a-fA-F]{6}$', description='Thread colour.'),
        shape=dict(type='string', enum=['straight', 'arc_over', 'arc_under', 'circle', 'wave']),
        curve_degrees=dict(type='number', minimum=20, maximum=240),
        circle_mm=dict(type='number', minimum=10, maximum=500, description='Circle shape: the size across, inside the letters.'),
        wave_percent=dict(type='number', minimum=2, maximum=25, description='Wave shape: how high it rises.'),
        fixed_length_mm=dict(type='number', minimum=5, maximum=1000,
                             description='One line spread or squeezed to exactly this length.'),
        letter_spacing_mm=dict(type='number', minimum=-2, maximum=10),
        line_spacing_percent=dict(type='number', minimum=70, maximum=250),
        sequence=dict(type='string', enum=['left', 'centre'], description='centre: sew from the middle letter out (caps).'),
        puff=dict(type='boolean', description='3D puff: satin over foam.'),
        foam_mm=dict(type='number', enum=[2, 3]),
        fabric=dict(type='string', enum=sorted(fabrics)),
        frame=dict(type='string', enum=['none', 'circle', 'oval', 'square', 'diamond', 'hexagon', 'shield', 'heart'],
                   description='A satin frame around the words (not with 3D puff).'),
        frame_mm=dict(type='number', minimum=1.6, maximum=5, description='Frame satin width (default 2.5).'),
        classic=dict(type='boolean',
                     description='Classic monogram: two or three initials, the middle one bigger, straight line.'),
        ornament=dict(type='string', enum=['none', 'crown', 'laurel', 'swirls', 'divider'],
                      description='A satin ornament round the words (not with 3D puff).')))
    return [
        dict(name='check_text', description='Lay the letters out with these settings (no stitches) and list every '
             'problem with a suggested fix, the measured width and the heights allowed.',
             input_schema=dict(type='object', additionalProperties=False, required=['settings'],
                               properties=dict(settings=settings))),
        dict(name='finish', description='Keep these settings. Call this exactly once, at the end.',
             input_schema=dict(type='object', additionalProperties=False, required=['settings', 'note'], properties=dict(
                 settings=settings, note=dict(type='string', description='One or two plain sentences: what you set and why.')))),
    ]


def merged(values, settings):
    """The screen's values with Claude's changes; a curve keeps a sensible default."""
    out = dict(values)
    for name, value in (settings or {}).items():
        if name in FIELDS:
            out[FIELDS[name]] = value
    shape = out.get('baseline', 'straight')
    if shape in ('arc_over', 'arc_under'):
        out.setdefault('arc_degrees', 90)
    else:
        out.pop('arc_degrees', None)
    for name, default, used in (('circle_mm', 60, 'circle'), ('wave_percent', 6, 'wave')):
        if shape == used:
            out.setdefault(name, default)
        else:
            out.pop(name, None)
    out.pop('arc_radius_mm', None)
    if out.get('puff'):
        out.setdefault('puff_foam_mm', 3)
    return out


def measured(values):
    """What check_text tells Claude."""
    try:
        result = small_lettering.advice(values)
    except ValueError as error:
        return dict(problems=[dict(message=str(error))])
    report = dict(problems=result['problems'], heights_allowed_mm=result['height_range'])
    if values.get('puff'):
        report['fonts_that_can_puff'] = result['puff_fonts']
    if result['height_range'] and not result['problems']:
        try:
            report['width_mm'] = round(small_lettering.laid_out_width(values)+.5, 1)
        except ValueError:
            pass
    return report


def ask(request, values, decisions, client=None):
    """Returns (values for the screen, note, problems left, run cost in US dollars)."""
    if not isinstance(request, str) or not request.strip() or len(request) > 500:
        raise ValueError('Describe what you want in a few words (up to 500 characters).')
    if not isinstance(values, dict):
        raise ValueError('Expected the current text settings.')
    if client is None:
        if not auto_claude.available():
            raise ValueError('AI help needs an Anthropic API key (ANTHROPIC_API_KEY) on this computer.')
        import anthropic
        client = anthropic.Anthropic(max_retries=2, timeout=120)
    spend = auto_claude.Spend(Path(decisions)/'claude-spend.json')
    if spend.room():
        raise ValueError(spend.room())
    fonts = small_lettering.fonts()
    from .generation_policy import presets
    fabrics = [r['fabric'] for r in presets()]
    catalogue = {key: f['label'] for key, f in fonts.items()}
    current = {name: values[key] for name, key in FIELDS.items() if key in values}
    messages = [dict(role='user', content=json.dumps(dict(request=request.strip(), current_settings=current,
                                                          fonts=catalogue), indent=1))]
    working, note, finished = dict(values), '', False
    for turn in range(MAX_TURNS):
        if spend.room():
            break
        response = client.messages.create(model=auto_claude.MODEL, max_tokens=4000, system=SYSTEM,
                                          tools=tools(fonts, fabrics), messages=messages)
        spend.add(response.usage)
        if response.stop_reason == 'refusal':
            raise ValueError('Claude declined this request.')
        messages.append(dict(role='assistant', content=response.content))
        calls = [b for b in response.content if b.type == 'tool_use']
        if not calls:
            break
        results, checked = [], None
        for call in calls:
            proposal = merged(values, call.input.get('settings'))
            if call.name == 'finish':
                working, note, finished = proposal, str(call.input.get('note', ''))[:400], True
                results.append(dict(type='tool_result', tool_use_id=call.id, content='Kept.'))
            else:
                report = measured(proposal)
                # The best checked try so far: a clean one, else the latest.
                if checked is None or not report['problems']:
                    checked = proposal
                results.append(dict(type='tool_result', tool_use_id=call.id, content=json.dumps(report)))
        if finished:
            break
        if checked:
            working = checked
        if turn == MAX_TURNS-2:
            results.append(dict(type='text', text='That was your last check. Call finish now with the best settings.'))
        messages.append(dict(role='user', content=results))
    # Whatever Claude left unsolved, apply the check's own fixes, so Make stitches can work.
    for _ in range(3):
        fixes = [p['fix']['set'] for p in measured(working)['problems'] if 'fix' in p]
        if not fixes:
            break
        for change in fixes:
            working.update(change)
    left = measured(working)['problems']
    return working, note or 'Settings updated.', [p['message'] for p in left], round(spend.run, 4)
