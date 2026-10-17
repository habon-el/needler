"""Explicit, offline build step; never generates stitches on a landing-page request."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from embroiderly.engine import digitize

ROOT = Path(__file__).resolve().parents[1]


def build():
    target = ROOT / 'src/embroiderly/static/landing'
    source = target / 'hello.png'
    image = Image.new('RGBA', (640, 240))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 175)
    draw.text((320, 120), 'hello', font=font, anchor='mm', fill='#126957', stroke_width=0)
    image.save(source)
    source.with_suffix('.prep.json').write_text(json.dumps({'options': {}, 'report': {'height_mm': 40}}))
    plan = digitize(source, ROOT / 'work/landing-sample', 40)
    plan['canvas_px'] = [640, 240]
    plan['sample_note'] = 'Actual PES-readback paths. No physical sew-out claimed.'
    (target / 'hello-plan.json').write_text(json.dumps(plan, separators=(',', ':')))
    print(f"Built landing sample: {plan['stitch_count']} stitches")


if __name__ == '__main__':
    build()
