"""Printable worksheet for the machine operator: the design at actual size, its size and
counts, the sewing sequence with the closest machine threads, stops, fabric, backing and a
hoop that fits. One self-contained HTML page; the browser prints it or saves it as PDF.
Everything comes from the stitch plan that the machine files were written from."""
from datetime import date
from html import escape
import math

# Sewing-time estimate: the same assumptions as the time shown in the studio.
STITCHES_PER_MINUTE = 600
TRIM_SECONDS = 2
COLOUR_CHANGE_SECONDS = 15
# Common round-number hoop sewing fields (mm), smallest first; the first that fits is suggested.
HOOPS = [(100, 100), (130, 180), (160, 260), (200, 200), (200, 300), (240, 350), (360, 200)]
HOOP_MARGIN_MM = 10


def blocks(steps, colours):
    """The sewing sequence: one block per thread change, with its stitches and cuts."""
    out, index = [], 0
    current = dict(colour=colours[0] if colours else '#000000', stitches=0, trims=0)
    for step in steps:
        if step['t'] == 'color_change':
            out.append(current)
            index += 1
            current = dict(colour=colours[index] if index < len(colours) else step.get('color', '#000000'),
                           stitches=0, trims=0)
        elif step['t'] == 'stitch':
            current['stitches'] += 1
        elif step['t'] == 'trim':
            current['trims'] += 1
    out.append(current)
    return [b for b in out if b['stitches']]


def hoop_for(width, height):
    """Smallest listed hoop the design fits in with a margin, either way round."""
    for w, h in HOOPS:
        if (width+HOOP_MARGIN_MM <= w and height+HOOP_MARGIN_MM <= h) or \
                (width+HOOP_MARGIN_MM <= h and height+HOOP_MARGIN_MM <= w):
            return w, h
    return None


def summary(playback, fabric=None):
    steps, colours = playback.get('steps', []), playback.get('colors', [])
    sewn = [s for s in steps if s['t'] == 'stitch']
    if not sewn:
        raise ValueError('This design has no stitches yet. Check stitches first.')
    xs, ys = [s['x'] for s in sewn], [s['y'] for s in sewn]
    width, height = max(xs)-min(xs), max(ys)-min(ys)
    sequence = blocks(steps, colours)
    from .thread_matching import rank_threads, CHARTS
    puff = playback.get('puff') or {}
    puff_threads = set(puff.get('threads', []))
    # One thread chart for the whole design (the one closest overall), so the operator
    # pulls threads from a single brand rather than a mix.
    distinct = sorted({b['colour'] for b in sequence})
    def total(brand):
        return sum(rank_threads(c, brands=[brand], limit=1)[0]['delta_e'] for c in distinct)
    try:
        chart = min(CHARTS, key=total)
    except (ValueError, IndexError):
        chart = None
    for number, block in enumerate(sequence):
        try:
            match = rank_threads(block['colour'], brands=[chart] if chart else None, limit=1)
        except ValueError:
            match = []
        block['thread'] = f"{match[0]['brand']} {match[0]['code']} {match[0]['name']}" if match else ''
        notes = []
        if number in puff_threads:
            notes.append(f"Stop before: lay {puff.get('foam_mm', 3):g} mm puff foam over the outline")
        elif number and block['colour'] == sequence[number-1]['colour']:
            notes.append('Machine stop (same thread)'+(': place or trim the appliqué fabric' if playback.get('applique') else ''))
        block['notes'] = notes
    changes = max(0, len(sequence)-1)
    trims = sum(1 for s in steps if s['t'] == 'trim')
    seconds = len(sewn)/STITCHES_PER_MINUTE*60+trims*TRIM_SECONDS+changes*COLOUR_CHANGE_SECONDS
    policy = playback.get('generation_policy') or {}
    fabric = dict(fabric or {})
    return dict(width=width, height=height, left=min(xs), top=min(ys), stitches=len(sewn), trims=trims,
                changes=changes, minutes=math.ceil(seconds/60), sequence=sequence, hoop=hoop_for(width, height),
                fabric=fabric.get('label') or policy.get('fabric_preset', ''),
                backing=fabric.get('backing') or policy.get('backing') or '',
                topping=fabric.get('topping') or policy.get('topping') or '',
                stabilizer=fabric.get('stabilizer') or policy.get('stabilizer') or '',
                start=(sewn[0]['x'], sewn[0]['y']))


def picture(steps, info):
    """The sewn path at actual size (millimetre units): one polyline per run of stitches,
    plus the centre mark and the start point."""
    pad = 6
    left, top = info['left']-pad, info['top']-pad
    width, height = info['width']+2*pad, info['height']+2*pad
    runs, run, colour = [], [], None
    for step in steps:
        if step['t'] == 'stitch':
            if run and step.get('color') != colour:
                runs.append((colour, run)); run = [run[-1]]
            colour = step.get('color', '#000000')
            run.append((step['x'], step['y']))
        elif run:
            runs.append((colour, run)); run = []
    if run:
        runs.append((colour, run))
    lines = ''.join(
        f'<polyline fill="none" stroke="{escape(c)}" stroke-width=".35" stroke-linejoin="round" '
        f'points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}"/>' for c, pts in runs if len(pts) > 1)
    cx, cy = info['left']+info['width']/2, info['top']+info['height']/2
    sx, sy = info['start']
    marks = (f'<path d="M{cx-5:.1f} {cy:.1f}H{cx+5:.1f}M{cx:.1f} {cy-5:.1f}V{cy+5:.1f}" stroke="#d0021b" stroke-width=".25"/>'
             f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="1.2" fill="none" stroke="#0a8f3c" stroke-width=".4"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.1f}mm" height="{height:.1f}mm" '
            f'viewBox="{left:.1f} {top:.1f} {width:.1f} {height:.1f}">{lines}{marks}</svg>')


def page(playback, title, fabric=None, hoop=None):
    """hoop: the hoop chosen for the design, {name, field: [width, height] mm as placed}."""
    info = summary(playback, fabric)
    rows = ''.join(
        f'<tr><td>{n}</td><td><span class="chip" style="background:{escape(b["colour"])}"></span>{escape(b["colour"])}</td>'
        f'<td>{escape(b["thread"]) or "—"}</td><td class="num">{b["stitches"]:,}</td><td class="num">{b["trims"]}</td>'
        f'<td>{escape("; ".join(b["notes"]))}</td><td class="tick"></td></tr>'
        for n, b in enumerate(info['sequence'], 1))
    suggested = f'{info["hoop"][0]} × {info["hoop"][1]} mm or larger' if info['hoop'] else 'Larger than common hoops: split the design'
    if hoop:
        w, h = hoop['field']
        fits = info['width'] <= w and info['height'] <= h
        hoop = f'{hoop["name"]} ({w:g} × {h:g} mm)' + ('' if fits else f' is too small; use {suggested}')
    else:
        hoop = suggested
    facts = [('Size', f'{info["width"]:.1f} × {info["height"]:.1f} mm'), ('Stitches', f'{info["stitches"]:,}'),
             ('Thread changes', str(info['changes'])), ('Cuts', str(info['trims'])),
             ('Sewing time', f'about {info["minutes"]} min at {STITCHES_PER_MINUTE} stitches/min'), ('Hoop', hoop)]
    if info['fabric']:
        facts.append(('Fabric', info['fabric']))
    facts.append(('Backing', info['backing'] or info['stabilizer'] or 'Medium tear-away'))
    if info['topping']:
        facts.append(('Topping', info['topping']))
    fact_html = ''.join(f'<div><dt>{escape(k)}</dt><dd>{escape(v)}</dd></div>' for k, v in facts)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Worksheet · {escape(title)}</title>
<style>
body{{font:14px/1.45 system-ui,sans-serif;color:#1c1c1c;background:#fff;margin:0;padding:24px}}
header{{display:flex;justify-content:space-between;align-items:baseline;gap:16px;border-bottom:2px solid #1c1c1c;padding-bottom:8px}}
h1{{font-size:20px;margin:0}} h2{{font-size:15px;margin:22px 0 8px}}
dl{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:8px 18px;margin:14px 0}}
dt{{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:#666}} dd{{margin:0;font-weight:600}}
table{{border-collapse:collapse;width:100%}} th,td{{border-bottom:1px solid #ccc;padding:6px 8px;text-align:left;vertical-align:top}}
th{{font-size:11px;text-transform:uppercase;color:#666}} .num{{text-align:right;font-variant-numeric:tabular-nums}}
.chip{{display:inline-block;width:14px;height:14px;border:1px solid #888;border-radius:3px;margin-right:6px;vertical-align:-2px}}
.tick{{width:28px;border-left:1px solid #ccc}} .design{{overflow:auto;border:1px solid #ddd;padding:8px;background:#fafaf7}}
.legend{{font-size:12px;color:#555}} .muted{{color:#666;font-size:12px}}
button{{font:inherit;padding:8px 16px;border:1px solid #1c1c1c;background:#1c1c1c;color:#fff;border-radius:6px;cursor:pointer}}
@media print{{body{{padding:0}} button{{display:none}} .design{{border:0;overflow:visible;background:none}} h2{{break-after:avoid}} tr{{break-inside:avoid}}}}
@page{{margin:12mm}}
</style></head><body>
<header><h1>{escape(title)}</h1><span class="muted">Needler worksheet · {date.today().isoformat()}</span>
<button type="button" onclick="window.print()">Print or save as PDF</button></header>
<dl>{fact_html}</dl>
<h2>Sewing sequence</h2>
<table><thead><tr><th>#</th><th>Colour</th><th>Closest machine thread</th><th class="num">Stitches</th><th class="num">Cuts</th><th>Notes</th><th>✓</th></tr></thead>
<tbody>{rows}</tbody></table>
<p class="muted">Thread names are the closest catalogue colours (approximate); match them to your own threads.</p>
<h2>Design at actual size</h2>
<p class="legend">Print at 100% (no “fit to page”) to use it as a placement template.
<span style="color:#d0021b">+</span> design centre · <span style="color:#0a8f3c">○</span> first stitch.</p>
<div class="design">{picture(playback.get("steps", []), info)}</div>
<p class="muted">Always sew a test on the same fabric and backing before a production run.</p>
</body></html>'''


def fabric_info(preset):
    """The fabric preset's name, backing and topping, for the worksheet."""
    from .generation_policy import presets
    row = next((r for r in presets() if r['fabric'] == preset), None)
    return dict(label=row.get('label', preset), backing=row.get('backing'), topping=row.get('topping'),
                stabilizer=row.get('stabilizer', '')) if row else {}
