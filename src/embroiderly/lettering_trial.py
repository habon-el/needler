"""Read-only embroidery-font trial. No machine downloads or saved-design writes.

Only length, dimensions and trim parity are measured here. Hole containment,
density, glyph preservation and machine compatibility remain release blockers.
"""
import base64
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import threading
import pyembroidery as emb
from flask import jsonify, request
from .machine_files import write_pair, read_pattern
from .release_gate import MIN_STITCH_MM, MAX_STITCH_MM
from .small_lettering import generate, validate
from .lettering_size import width_fit

BUSY = threading.Lock()


def measure(pattern):
    previous = [0, 0]
    points, spans, lengths = [], [], []
    attached = False
    for x, y, flags in pattern.stitches:
        if not all(math.isfinite(v) for v in (x,y)):
            raise ValueError('The generator returned invalid coordinates.')
        point = [x/10, y/10]
        kind = flags & emb.COMMAND_MASK
        if kind == emb.STITCH:
            length = math.dist(previous, point)
            if length > 1e-8:
                lengths.append(length)
            points.append(point)
            if attached:
                spans.append((previous, point))
            attached = True
        else:
            attached = False
        previous = point
    if not points:
        raise ValueError('The embroidery font generated no stitches.')
    xs, ys = zip(*points)
    bounds = [min(xs), min(ys), max(xs), max(ys)]
    return dict(stitches=len(points), trims=pattern.count_stitch_commands(emb.TRIM),
                short=sum(v < MIN_STITCH_MM-1e-8 for v in lengths),
                long=sum(v > MAX_STITCH_MM+1e-8 for v in lengths),
                minimum_mm=round(min(lengths,default=0),3),
                maximum_mm=round(max(lengths,default=0),3),
                width_mm=round(bounds[2]-bounds[0],2),
                height_mm=round(bounds[3]-bounds[1],2)), bounds, spans


def trial(body):
    generated = generate(body)
    with TemporaryDirectory(prefix='lettering-trial-') as tmp:
        folder = Path(tmp)
        (folder/'plan.json').write_text(json.dumps(generated['plan']))
        pattern = emb.EmbPattern(str(folder/'plan.json'))
        write_pair(pattern,folder/'design.pes',folder/'design.dst',{'version':6})
        reports = {}
        for fmt in ('pes','dst'):
            reports[fmt], bounds, spans = measure(read_pattern(folder/('design.'+fmt)))
    # Numeric geometry only; never interpolate customer text/markup into SVG.
    x,y,x1,y1 = bounds
    paths = ' '.join(f'M {a[0]} {a[1]} L {b[0]} {b[1]}' for a,b in spans)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x-1} {y-1} {x1-x+2} {y1-y+2}">'
           f'<rect x="{x-1}" y="{y-1}" width="{x1-x+2}" height="{y1-y+2}" fill="white"/>'
           f'<path d="{paths}" fill="none" stroke="#202020" stroke-width="0.12"/></svg>')
    return dict(reports=reports, fit=width_fit(reports['dst']['width_mm'],body.get('available_width_mm',50)),
                image='data:image/svg+xml;base64,'+base64.b64encode(svg.encode()).decode(),
                nominal_height_mm=generated['nominal_height_mm'], release_approved=False,
                pending=['Letter-hole containment','Density and repeated penetrations',
                         'Every letter and punctuation mark retained','Machine fit and physical sew-out'])


def register(app):
    @app.post('/lettering/small-trial')
    def small_trial():
        body=request.get_json(silent=True)
        try:
            validate(body)
            width_fit(0,body.get('available_width_mm',50))
        except (ValueError,TypeError,OverflowError):
            return jsonify(error='Choose a supported font and its available characters, nominal height 4–6 mm, and available width 5–400 mm.'),400
        if not BUSY.acquire(blocking=False):
            return jsonify(error='A small-lettering trial is still running. Please retry shortly.'),409
        try:
            return jsonify(trial(body))
        except (ValueError,TypeError,KeyError,OverflowError,subprocess.SubprocessError,OSError):
            return jsonify(error='The lettering trial could not finish. Your design is unchanged; retry or choose another font.'),422
        finally:
            BUSY.release()
