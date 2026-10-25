"""Guides on the design canvas: straight lines the user places to line pieces up (canvas-guides.js).

A guide is {axis: 'x' | 'y', mm: position}: axis 'x' is an up-and-down line at X mm, axis 'y' an
across line at Y mm, both measured from the hoop centre like piece positions (positive Y is down).
Guides live in the preparation options (`canvas_guides`) so they come back after reload, but they
are drawing aids only: they never reach the stitches. The preparation key and the saved-plan match
leave them out, so adding or moving a guide keeps the current stitch plan and machine files, and
they are saved through their own small route instead of a new preview.
"""
import hashlib
import json
import math
from pathlib import Path

KEY = 'canvas_guides'
MAX_GUIDES = 20
LIMIT_MM = 500


def checked(value):
    """The guides as saved: a list of at most MAX_GUIDES {axis, mm}, mm rounded to 0.1. Bad values raise."""
    if not isinstance(value, list) or len(value) > MAX_GUIDES:
        raise ValueError(f'Keep up to {MAX_GUIDES} guides.')
    result = []
    for guide in value:
        if not isinstance(guide, dict) or set(guide) != {'axis', 'mm'} or guide['axis'] not in ('x', 'y') \
                or type(guide['mm']) not in (int, float) or not math.isfinite(guide['mm']) or abs(guide['mm']) > LIMIT_MM:
            raise ValueError(f'A guide is a line across or down, at most {LIMIT_MM} mm from the hoop centre.')
        result.append(dict(axis=guide['axis'], mm=round(float(guide['mm']), 1)))
    return result


def check(options):
    """Refuse saved preparation options whose guides are not valid."""
    if KEY in options:
        checked(options[KEY])


def without_guides(options):
    """The options that make stitches: guides removed."""
    return {k: v for k, v in options.items() if k != KEY} if isinstance(options, dict) else options


def save(saved, guides):
    """Write the guides into the design's saved options file; nothing else in it changes."""
    saved = Path(saved)
    guides = checked(guides)
    options = json.loads(saved.read_text()) if saved.exists() else {}
    if not isinstance(options, dict):
        raise ValueError('The saved design settings cannot be read.')
    if guides:
        options[KEY] = guides
    else:
        options.pop(KEY, None)
    saved.parent.mkdir(parents=True, exist_ok=True)
    temporary = saved.with_suffix('.pending.json')
    temporary.write_text(json.dumps(options, sort_keys=True))
    temporary.replace(saved)
    return guides


def register_guides(app, root):
    from flask import jsonify, request
    uploads, decisions = Path(root)/'work'/'uploads', Path(root)/'work'/'decisions'

    @app.post('/api/guides/<name>')
    def guides_save(name):
        name = Path(name).name
        if not (uploads/name).is_file():
            return jsonify(error='Design not found.'), 404
        body = request.get_json(silent=True)
        try:
            guides = save(decisions/(name+'.preparation.json'), body.get('guides') if isinstance(body, dict) else None)
        except (ValueError, OSError) as error:
            return jsonify(error=str(error)), 400
        # The new file fingerprint lets the next piece edit pass the "changed in another window" check.
        revision = hashlib.sha256((decisions/(name+'.preparation.json')).read_bytes()).hexdigest()
        return jsonify(guides=guides, piece_revision=revision)
