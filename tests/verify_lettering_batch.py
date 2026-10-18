"""Actual-word background-removal checks; isolated app, no user designs changed.

Run: PYTHONPATH=src:work/deps python3 tests/verify_lettering_batch.py
This is a diagnostic batch: failures are recorded rather than hidden by assertions.
"""
import base64
import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from embroiderly.web import create_app

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/lettering-batch-20260930'
FONT_DIR = Path('/usr/share/fonts/truetype/dejavu')
if not FONT_DIR.is_dir():
    # Bundled DejaVu fonts (a subset) on systems without the Linux package.
    FONT_DIR = Path(__file__).resolve().parents[1]/'src'/'embroiderly'/'fonts'/'dejavu'
CASES = [
    ('Hello World!', 'DejaVuSans-Bold.ttf', 72, 'PNG', False, 60),
    ('Happy Birthday', 'DejaVuSerif-Bold.ttf', 70, 'PNG', False, 60),
    ('Baby', 'DejaVuSans-BoldOblique.ttf', 100, 'PNG', False, 60),
    ('Good vibes', 'DejaVuSans-Oblique.ttf', 86, 'PNG', False, 60),
    ('Love', 'DejaVuSerif.ttf', 110, 'PNG', False, 60),
    ('Thank you!', 'DejaVuSans-ExtraLight.ttf', 88, 'PNG', False, 60),
    ('MOM & DAD', 'DejaVuSans-Bold.ttf', 85, 'PNG', False, 60),
    ('ABO 0689', 'DejaVuSansMono.ttf', 85, 'PNG', False, 60),
    ('Big thanks', 'DejaVuSerif-Italic.ttf', 92, 'PNG', False, 60),
    ('coffee & cake', 'DejaVuSans.ttf', 82, 'JPEG', False, 60),
    ('GO! 2026', 'DejaVuSans-Bold.ttf', 100, 'PNG', True, 60),
    ('a b g k o e', 'DejaVuSerif.ttf', 80, 'PNG', False, 60),
    ('Baby 0689', 'DejaVuSans.ttf', 40, 'PNG', False, 10),
]


def render(case):
    text, font, size, fmt, reverse, height = case
    canvas = Image.new('L', (768*3, 240*3))
    draw = ImageDraw.Draw(canvas)
    face = ImageFont.truetype(str(FONT_DIR/font), size*3)
    box = draw.textbbox((0, 0), text, font=face)
    draw.text(((2304-box[2]+box[0])/2-box[0], (720-box[3]+box[1])/2-box[1]),
              text, font=face, fill=255)
    coverage = np.asarray(canvas.resize((768, 240), Image.Resampling.LANCZOS))
    bg = np.array([248, 246, 240] if fmt == 'JPEG' else ([0]*3 if reverse else [255]*3))
    ink = np.array([255]*3 if reverse else [0]*3)
    a = coverage[..., None]/255
    image = Image.fromarray(np.uint8(np.round(bg*(1-a)+ink*a)))
    stream = io.BytesIO(); image.save(stream, format=fmt, quality=88)
    return stream.getvalue(), coverage, bg


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    results = []; tiles = []
    with tempfile.TemporaryDirectory(prefix='embroiderly-word-tests-') as tmp, patch('embroiderly.subject_model.warm_image'):
        root = Path(tmp); client = create_app(root).test_client()
        for index, case in enumerate(CASES, 1):
            text, font, size, fmt, reverse, height = case
            source, coverage, background = render(case)
            prefix = f'{index:02d}'
            (OUT/f'{prefix}-source.{fmt.lower()}').write_bytes(source)
            upload = client.post('/upload', data={'image': (io.BytesIO(source), f'word.{fmt.lower()}')})
            assert upload.status_code == 302, upload.data[:300]
            name = upload.location.split('/')[-1]; options = {'height_mm': height}
            initial = client.post('/artwork/'+name, json={'options': options}).get_json()
            operation = initial['report']['background_proposal']
            assert operation, (text, initial)
            request = {'action': 'remove_colour', 'operation': operation, 'options': options}
            response = client.post('/assist/'+name, json=request)
            assert response.status_code == 200, response.data[:500]
            proposal = response.get_json()
            not_saved = not (root/'work/decisions'/(name+'.preparation.json')).exists()
            response = client.post('/artwork/'+name, json={'options': {**options, **proposal['patch']}, 'save': True})
            assert response.status_code == 200, response.data[:500]
            applied = response.get_json()
            assert applied['report']['height_mm'] == height
            data = base64.b64decode(applied['image'].split(',')[1])
            (OUT/f'{prefix}-removed.png').write_bytes(data)
            output = np.asarray(Image.open(io.BytesIO(data)).convert('RGBA'))
            visible = output[:,:,3] > 127
            # Ground truth from rendered glyphs, not the operation's own report.
            n, labels, stats, _ = cv2.connectedComponentsWithStats(np.uint8(coverage < 128), 8)
            outside_ids = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:,0], labels[:,-1]])))
            holes = []
            for label in range(1, n):
                if label in outside_ids:
                    continue
                core = (labels == label) & (coverage <= 5)
                if not np.any(core):
                    continue
                holes.append({'area_mm2': round(float(stats[label, cv2.CC_STAT_AREA])*(height/240)**2, 4),
                              'core_pixels': int(core.sum()),
                              'core_pixels_filled': int((core & visible).sum())})
            ink_core = coverage >= 250
            outer_core = np.isin(labels, list(outside_ids)) & (coverage <= 5)
            target_remaining = visible & (np.max(np.abs(output[:,:,:3].astype(float)-background), axis=2) <= 12)
            repeated = client.post('/artwork/'+name, json={'options': {**options, **proposal['patch']}}).get_json()
            record = {'word': text, 'font': font, 'format': fmt, 'image_height_mm': height,
                      'reverse': reverse, 'remaining_background_mm2_independent': round(float(target_remaining.sum())*(height/240)**2, 6),
                      'outside_core_pixels_retained': int((outer_core & visible).sum()),
                      'ink_core_pixels_lost': int((ink_core & ~visible).sum()),
                      'holes': holes, 'filled_specks_reported': proposal['knockout']['filled_specks'],
                      'recoverable_parts': len(proposal['knockout']['parts']),
                      'proposal_did_not_save': not_saved,
                      'source_unchanged': (root/'work/uploads'/name).read_bytes() == source,
                      'repeat_identical': repeated['image'] == applied['image']}
            record['pass'] = (not target_remaining.any() and not (outer_core & visible).any()
                              and not (ink_core & ~visible).any()
                              and not any(h['core_pixels_filled'] for h in holes)
                              and all(record[k] for k in ['proposal_did_not_save','source_unchanged','repeat_identical']))
            if not record['pass']:
                # Diagnose using the existing cleanup toggle; do not change production code.
                raw_options = {**options, **proposal['patch']}
                raw_options['colour_knockouts'] = [{**op, 'cleanup': False} for op in raw_options['colour_knockouts']]
                raw = client.post('/artwork/'+name, json={'options': raw_options}).get_json()
                raw_data = base64.b64decode(raw['image'].split(',')[1])
                (OUT/f'{prefix}-cleanup-off.png').write_bytes(raw_data)
                raw_pixels = np.asarray(Image.open(io.BytesIO(raw_data)).convert('RGBA'))
                raw_visible = raw_pixels[:,:,3] > 127
                hole_core = ~np.isin(labels, [0, *outside_ids]) & (coverage <= 5)
                record['cleanup_off'] = {
                    'hole_core_pixels_filled': int((hole_core & raw_visible).sum()),
                    'outside_core_pixels_retained': int((outer_core & raw_visible).sum()),
                    'ink_core_pixels_lost': int((ink_core & ~raw_visible).sum()),
                    'remaining_background_mm2': round(float((raw_visible & (np.max(np.abs(raw_pixels[:,:,:3].astype(float)-background), axis=2) <= 12)).sum())*(height/240)**2, 6)}
            results.append(record)
            print(json.dumps(record), flush=True)
            tile = Image.new('RGB', (850, 300), '#e9edf0'); d = ImageDraw.Draw(tile)
            d.text((12, 8), f'{index}. {text} | {height} mm canvas | '+('PASS' if record['pass'] else 'CHECK'), fill='black')
            # Actual transparent output on a coloured substrate makes leftovers visible.
            tile.paste(Image.fromarray(output).convert('RGB'), (25, 40), Image.fromarray(output[:,:,3]))
            tiles.append(tile)
    report = {'scope': 'Isolated upload, automatic proposal, explicit apply/save, repeat; no machine sew-out or browser click test.',
              'passed': sum(r['pass'] for r in results), 'total': len(results), 'cases': results}
    (OUT/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    sheet = Image.new('RGB', (1700, 300*((len(tiles)+1)//2)), 'white')
    for i, tile in enumerate(tiles): sheet.paste(tile, ((i%2)*850, (i//2)*300))
    sheet.save(OUT/'results-contact-sheet.png')
    print(f"RESULT: {report['passed']}/{report['total']} strict checks passed. {OUT}")


if __name__ == '__main__':
    main()
