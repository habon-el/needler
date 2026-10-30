"""Photo lines: one-colour and multi-colour photo stitch, closed or open.

A photo is drawn with one thread in parallel rows. Each row is a zigzag whose
width follows the darkness of the photo under it: nearly touching its
neighbours in the shadows, a thin running line in the highlights. Rows are
joined at their ends, so a rectangular photo sews as one continuous thread.
The tone comes from the original upload (prepared colours would posterize it);
the prepared picture only supplies the subject mask and any painted edits.

Several colours: a few threads are picked from the photo; each pixel is a mix of
its two nearest threads, and each thread is sewn as its own rows, at its own
angle, with the zigzag as wide as its share. Where rows of two threads cross,
the colours mix. Open: light areas get no stitches, so the fabric shows, and
zigzags stay narrow enough to leave fabric between the rows.
"""
import json
import math
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pyembroidery as emb

from .portrait import MIN_STITCH_MM, MAX_STITCH_MM, THREAD_WIDTH_MM


def verify_file(path):
    """Every needle move within 0.3-7 mm. A zero-length stitch (PES repeats the first
    needle position) moves nothing and is ignored, as in export_findings."""
    pattern = emb.EmbPattern(str(path)); prior = (0, 0); lengths = []; bad = 0
    for x, y, flag in pattern.stitches:
        if flag & emb.COMMAND_MASK == emb.STITCH:
            length = math.dist(prior, (x, y)) / 10
            if length > 1e-8:
                lengths.append(length)
                bad += not MIN_STITCH_MM - 1e-8 <= length <= MAX_STITCH_MM + 1e-8
        prior = (x, y)
    if not lengths:
        raise ValueError('No sewable photo stitches remain.')
    if bad:
        raise ValueError(f'Photo lines export blocked: {bad} stitch-length violations in {Path(path).name}.')
    return dict(stitch_count=len(lengths), shortest_stitch_mm=min(lengths), longest_stitch_mm=max(lengths), violations=0)

ROW_MM = 1.0          # distance between rows
STEP_MM = .45         # needle spacing along a zigzag
RUN_MM = 2.0          # running stitch length in the highlights
THIN_MM = .3          # narrower than this, a row is a plain running line
LOCK_MM = .6
COLOURS = (2, 6)      # threads in a multi-colour photo
SHARE = .15           # a thread is sewn only where it makes at least this share of the colour
OPEN_LIGHT = .18      # open photo stitch: lighter than this, the fabric shows
OPEN_WIDTH = .6       # open: a zigzag fills at most this share of its row


def tone(original, prepared_rgb, alpha, edited, invert=False):
    """Darkness 0..1 to stitch, contrast-stretched inside the subject, local contrast lifted."""
    rgb = np.where(edited[..., None], prepared_rgb, original)
    lum = cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_RGB2GRAY)
    lum = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lum).astype(np.float32)
    inside = lum[alpha] if alpha.any() else lum.ravel()
    lo, hi = np.percentile(inside, 2), np.percentile(inside, 98)
    value = np.clip((lum - lo) / max(1.0, hi - lo), 0, 1)
    return value if invert else 1 - value


def _sample(field, x, y):
    h, w = field.shape
    return float(cv2.getRectSubPix(field, (1, 1), (min(max(x, 0), w - 1), min(max(y, 0), h - 1)))[0, 0])


def rows(dark, mask, scale, row_mm=ROW_MM, angle=0.0, width_mm=None):
    """Zigzag runs [(x_mm, y_mm), ...] in sewing order (serpentine), each inside the mask."""
    width_mm = width_mm or row_mm * .95
    h, w = mask.shape
    # Keep the zigzag inside the subject: erode by half the widest zigzag.
    keep = max(1, int(math.ceil(width_mm / 2 / scale)))
    # The picture edge is a boundary too (cv2 would otherwise treat outside as inside).
    inner = cv2.erode(mask.astype(np.uint8), np.ones((2 * keep + 1, 2 * keep + 1), np.uint8),
                      borderType=cv2.BORDER_CONSTANT, borderValue=0).astype(bool)
    blur = cv2.GaussianBlur(dark.astype(np.float32), (0, 0), max(.5, row_mm / 2 / scale))
    a = math.radians(angle)
    u, n = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
    corners = [(0, 0), (w * scale, 0), (0, h * scale), (w * scale, h * scale)]
    along = [c[0] * u[0] + c[1] * u[1] for c in corners]
    across = [c[0] * n[0] + c[1] * n[1] for c in corners]
    runs, flip = [], False
    t = min(across) + row_mm / 2
    while t < max(across):
        points, segments = [], []
        s = min(along)
        while s <= max(along):
            x, y = s * u[0] + t * n[0], s * u[1] + t * n[1]
            px, py = x / scale, y / scale
            if 0 <= px < w and 0 <= py < h and inner[int(py), int(px)]:
                points.append((s, x, y))
            elif points:
                segments.append(points); points = []
            s += STEP_MM
        if points:
            segments.append(points)
        row_runs = []
        for seg in segments:
            if (seg[-1][0] - seg[0][0]) < 1.0:
                continue
            run, side, last = [], 1, None
            for i, (s, x, y) in enumerate(seg):
                width = _sample(blur, x / scale, y / scale) * width_mm
                end = i == len(seg) - 1
                if width < THIN_MM and not end and last is not None and math.dist(last, (x, y)) < RUN_MM:
                    continue  # highlights: long running stitches along the row centre
                offset = side * width / 2 if width >= THIN_MM else 0.0
                p = (x + n[0] * offset, y + n[1] * offset)
                if last is None or math.dist(last, p) >= MIN_STITCH_MM + .05:
                    run.append(p); last = p
                side = -side
            if len(run) >= 2:
                row_runs.append(run)
        if flip:
            row_runs = [r[::-1] for r in row_runs[::-1]]
        runs.extend(row_runs)
        flip = not flip
        t += row_mm
    return runs


def _inside(mask, scale, a, b):
    count = max(2, int(math.dist(a, b) / (scale / 2)) + 1)
    h, w = mask.shape
    for k in range(count):
        x = (a[0] + (b[0] - a[0]) * k / (count - 1)) / scale
        y = (a[1] + (b[1] - a[1]) * k / (count - 1)) / scale
        if not (0 <= x < w and 0 <= y < h and mask[int(y), int(x)]):
            return False
    return True


def _lock(run, at_end):
    """Three short stitches back and forth along the run: the thread cannot pull out."""
    seq = run[::-1] if at_end else run
    p = seq[0]
    for q in seq[1:]:
        d = math.dist(p, q)
        if d >= LOCK_MM * .8:
            mid = (p[0] + (q[0] - p[0]) * LOCK_MM / d, p[1] + (q[1] - p[1]) * LOCK_MM / d)
            return [mid, p] if at_end else [p, mid, p]
    return []


def threads(rgb, alpha, count, fabric=None):
    """count threads for the photo, the one nearest the fabric first, each one's share (0..1) of
    every pixel, and their names. The colours picked from the photo become real threads of one chart
    (thread_matching, the closest chart overall); a pixel is a mix of its two nearest threads, in the
    threads' own colours. With a fabric colour (open photo stitch) the fabric is one of the colours,
    but never sewn."""
    from skimage.color import lab2rgb, rgb2lab
    from .thread_matching import matched_threads
    lab = rgb2lab(rgb / 255.).astype(np.float32)
    inside = lab[alpha]
    paper = None if fabric is None else rgb2lab(np.array([[fabric]], float) / 255.)[0, 0].astype(np.float32)
    if paper is not None:
        # Do not spend a thread on the fabric's own colour.
        far = np.linalg.norm(inside - paper, axis=1) > 12
        inside = inside[far] if far.sum() >= count * 20 else inside
    sample = np.ascontiguousarray(inside[::max(1, len(inside) // 20000)])
    count = max(1, min(count, len(np.unique(np.round(sample), axis=0))))
    cv2.setRNGSeed(0)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, .5)
    _, _, centres = cv2.kmeans(sample, count, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
    picked = np.clip(lab2rgb(centres[None].astype(float))[0] * 255, 0, 255).round()
    brand, real = matched_threads([tuple(c) for c in picked])
    centres = rgb2lab(np.array([[e[0] for e in real]], float) / 255.)[0].astype(np.float32)
    reference = paper if paper is not None else np.array([100, 0, 0], np.float32)
    order = np.argsort(np.linalg.norm(centres - reference, axis=1), kind='stable')
    centres, real = centres[order], [real[i] for i in order]
    palette = np.vstack([centres, paper[None]]) if paper is not None else centres
    if len(palette) == 1:
        share = np.ones(alpha.shape + (1,), np.float32)
    else:
        # Nearest two colours per pixel; the pixel's place on the line between them is the mix.
        distance = np.linalg.norm(lab[:, :, None, :] - palette[None, None], axis=3)
        near = np.argsort(distance, axis=2)[:, :, :2]
        a, b = palette[near[..., 0]], palette[near[..., 1]]
        span = b - a
        t = np.clip(((lab - a) * span).sum(2) / np.maximum((span * span).sum(2), 1e-6), 0, 1)
        share = np.zeros(alpha.shape + (len(palette),), np.float32)
        ys, xs = np.indices(alpha.shape)
        share[ys, xs, near[..., 0]] = 1 - t
        share[ys, xs, near[..., 1]] += t
    share[~alpha] = 0
    hexes = ['#%02x%02x%02x' % rgb for rgb, _, _ in real]
    names = [' '.join(v for v in (brand, code, name) if v) for _, name, code in real]
    return hexes, [share[:, :, i] for i in range(len(centres))], names


def _sew(plan, runs, mask, scale, to_file, row_mm):
    """One thread's runs: rows joined along the inside where they can, otherwise tied off and cut."""
    previous = last_run = None
    for run in runs:
        joined = previous is not None and math.dist(previous, run[0]) <= max(3 * row_mm, 3.0) \
            and _inside(mask, scale, previous, run[0])
        if joined:
            # Step down to the next row along the picture edge: one continuous thread.
            gap = math.dist(previous, run[0]); parts = max(1, int(math.ceil(gap / 3.0)))
            for k in range(1, parts + 1):
                q = (previous[0] + (run[0][0] - previous[0]) * k / parts, previous[1] + (run[0][1] - previous[1]) * k / parts)
                if math.dist(previous, q) >= MIN_STITCH_MM:
                    plan.add_stitch_absolute(emb.STITCH, *to_file(q))
        else:
            if previous is not None:
                for p in _lock(last_run, True):
                    plan.add_stitch_absolute(emb.STITCH, *to_file(p))
                plan.add_stitch_absolute(emb.TRIM, *to_file(previous))
            plan.add_stitch_absolute(emb.JUMP, *to_file(run[0]))
            for p in _lock(run, False)[1:]:
                plan.add_stitch_absolute(emb.STITCH, *to_file(p))
        for p in run[1:]:
            plan.add_stitch_absolute(emb.STITCH, *to_file(p))
        previous, last_run = run[-1], run
    for p in _lock(last_run, True):
        plan.add_stitch_absolute(emb.STITCH, *to_file(p))
    plan.add_stitch_absolute(emb.TRIM, *to_file(previous))
    return previous


def generate(source, directory, height_mm, options, metadata=None):
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    from PIL import Image
    with Image.open(source) as image:
        array = np.array(image.convert('RGBA'))
    h, w = array.shape[:2]; scale = height_mm / h
    alpha = array[:, :, 3] > 127
    if not alpha.any():
        raise ValueError('No selected photo pixels.')
    prepared_rgb = array[:, :, :3]
    from .detail_lines import source_pixels
    original = source_pixels(Path(source), metadata, (h, w))
    edited = np.zeros((h, w), bool)
    if original is None:
        original = prepared_rgb
    else:
        from .preparation import edit_brush
        for edit in options.get('edits', []):
            if edit.get('kind') != 'erase':
                edited |= edit_brush(edit, w, h)
    invert = options.get('photo_light_thread') is True
    several = options.get('photo_style') == 'multi_colour'
    opened = options.get('photo_open') is True
    row_mm = float(min(2.0, max(.6, float(options.get('photo_row_mm', ROW_MM)))))
    angle = float(min(180, max(-180, float(options.get('photo_angle', 0)))))
    width_mm = row_mm * (OPEN_WIDTH if opened else .95)
    blur = lambda field: cv2.GaussianBlur(field.astype(np.float32), (0, 0), max(.5, row_mm / 2 / scale))
    layers = []
    if several:
        count = options.get('photo_colours', 4)
        if type(count) is not int or not COLOURS[0] <= count <= COLOURS[1]:
            raise ValueError(f'Choose {COLOURS[0]} to {COLOURS[1]} thread colours for the photo.')
        rgb = np.where(edited[..., None], prepared_rgb, original).astype(np.float64)
        fabric = ((20, 20, 20) if invert else (255, 255, 255)) if opened else None
        colours, shares, names = threads(rgb, alpha, count, fabric)
        named = dict(zip(colours, names))
        for index, (thread, share) in enumerate(zip(colours, shares)):
            mask = alpha & (blur(share) > SHARE)
            # Each thread at its own angle, so crossing rows mix the colours.
            runs = rows(share, mask, scale, row_mm, angle + index * 180 / len(colours), width_mm)
            if runs:
                layers.append((thread, runs, mask))
    else:
        thread = str(options.get('photo_thread', '#f2f2f2' if invert else '#1b1b1b')).lower()
        dark = tone(original, prepared_rgb, alpha, edited, invert)
        mask = alpha & (blur(dark) > OPEN_LIGHT) if opened else alpha
        runs = rows(dark, mask, scale, row_mm, angle, width_mm)
        if runs:
            layers.append((thread, runs, mask))
    if not layers:
        raise ValueError('The photo is too small for photo lines; make it larger.')
    plan = emb.EmbPattern(); plan.extras['name'] = 'Photo lines'
    to_file = lambda p: ((p[0] - w * scale / 2) * 10, (p[1] - h * scale / 2) * 10)
    previous = None
    for thread, runs, mask in layers:
        if previous is not None:
            plan.add_stitch_absolute(emb.COLOR_CHANGE, *to_file(previous))
        plan.add_thread(thread)
        previous = _sew(plan, runs, mask, scale, to_file, row_mm)
    plan.add_stitch_absolute(emb.END, *to_file(previous))
    used = [thread for thread, _, _ in layers]
    # Stitches are rounded to the 0.1 mm grid when written: drop any that collapse below the minimum.
    tidy, prior = [], None
    for x, y, flag in plan.stitches:
        point = (round(x), round(y))
        if flag == emb.STITCH and prior is not None and math.dist(prior, point) / 10 < MIN_STITCH_MM:
            continue
        tidy.append([point[0], point[1], flag]); prior = point if flag in (emb.STITCH, emb.JUMP) else prior
    plan.stitches = tidy
    with tempfile.TemporaryDirectory(prefix='photo-lines-', dir=directory) as temporary:
        temp = Path(temporary)
        from .machine_files import write_pair
        write_pair(plan, temp / 'design.pes', temp / 'design.dst', {'version': 6, 'tie_on': False, 'tie_off': False, 'full_jump': False})
        audits = {fmt: verify_file(temp / ('design.' + fmt)) for fmt in ('pes', 'dst')}
        for fmt in ('pes', 'dst'):
            (temp / ('design.' + fmt)).replace(directory / ('design.' + fmt))
    written = emb.EmbPattern(str(directory / 'design.pes'))
    types = {emb.STITCH: 'stitch', emb.JUMP: 'jump', emb.TRIM: 'trim', emb.COLOR_CHANGE: 'color_change',
             emb.STOP: 'color_change', emb.END: 'end'}
    steps, index = [], 0
    for x, y, f in written.stitches:
        kind = types.get(f & emb.COMMAND_MASK, 'unknown')
        index += kind == 'color_change'
        steps.append(dict(x=x / 10, y=y / 10, t=kind, color=used[min(index, len(used) - 1)]))
    payload = dict(steps=steps, colors=used, stitch_count=audits['pes']['stitch_count'],
                   trim_count=sum(s['t'] == 'trim' for s in steps), origin_mm=[w * scale / 2, h * scale / 2],
                   height_mm=height_mm, thread_width_mm=THREAD_WIDTH_MM,
                   engine='Multi-colour photo stitch' if several else 'One-colour photo lines',
                   objects=sum(len(runs) for _, runs, _ in layers), palette_format='PES v6 custom RGB',
                   generation_mode='photo colours' if several else 'photo lines',
                   photo_lines=dict(row_mm=row_mm, angle=angle, thread=used[0], threads=used, light_thread=invert,
                                    open=opened))
    if several:
        from .thread_matching import CHARTS
        # The chart the threads came from: the longest chart name every thread name starts with.
        brand = max((b for b in CHARTS if all(n.startswith(b + ' ') for n in names)), key=len)
        payload['photo_lines'].update(chart=brand, thread_names=[named[t] for t in used])
    # The written files read back from disk: PES and DST sizes, stitches over empty fabric (export_proof.py).
    from .export_proof import proof
    try:
        payload['export_proof'] = proof(directory, alpha, scale, payload['origin_mm'], canvas_mm=(w * scale, height_mm), svg=None)
    except Exception as error:  # A report: it never blocks the files it describes.
        payload['export_proof'] = dict(error=str(error)[:200], notes=[])
    (directory / 'playback.json').write_text(json.dumps(payload))
    from .release_gate import record_context
    record_context(directory, alpha, scale, payload['origin_mm'])
    return payload
