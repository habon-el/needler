"""Real app/export smoke test on a disposable flat logo with an open hole."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time

from PIL import Image, ImageDraw
from embroiderly.web import create_app
from embroiderly.machine_files import read_pattern
from embroiderly.lettering_trial import measure


def main():
    with TemporaryDirectory(prefix='.repair-image-', dir='.') as temporary:
        root = Path(temporary).resolve()
        client = create_app(root).test_client()
        image = Image.new('RGBA', (240, 180))
        draw = ImageDraw.Draw(image)
        draw.ellipse((20, 30, 120, 130), fill='#202020')
        draw.ellipse((48, 58, 92, 102), fill=(0, 0, 0, 0))
        draw.rectangle((155, 40, 210, 120), fill='#bf3333')
        image.save(root/'work/uploads/logo.png')
        started = time.monotonic()
        r = client.post('/artwork/logo.png', json=dict(options=dict(count=2, smooth=0,
            floor_mm2=0, height_mm=60), digitize=True, subject_confirmed=True))
        evidence = dict(status=r.status_code, passed=r.status_code == 200,
                        error=r.json.get('error'), physical_sew_out='pending')
        if r.status_code == 200:
            name = r.json['prepared_name']
            evidence['files'] = {}
            for fmt in ('dst', 'pes'):
                files = [client.get(f'/studio-export/{name}/{fmt}') for _ in range(3)]
                assert all(f.status_code == 200 for f in files), [f.json for f in files]
                assert files[0].data == files[1].data == files[2].data
                path = root/('download.'+fmt)
                path.write_bytes(files[0].data)
                report, _, _ = measure(read_pattern(path))
                evidence['files'][fmt] = dict(readback=report,
                    sha256=hashlib.sha256(files[0].data).hexdigest(), repeated_downloads_identical=True)
                assert report['short'] == report['long'] == 0
            assert evidence['files']['dst']['readback']['trims'] == evidence['files']['pes']['readback']['trims']
        evidence['seconds'] = round(time.monotonic()-started, 2)
        Path('image-repair-verification.json').write_text(json.dumps(evidence, indent=2))
        print(json.dumps(evidence), flush=True)
        return evidence['passed']


if __name__ == '__main__':
    raise SystemExit(0 if main() else 1)
