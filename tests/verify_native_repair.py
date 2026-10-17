"""Opt-in real-engine checks through application routes, not mocked generation.

Run with PYTHONPATH=src:work/deps python3 tests/verify_native_repair.py.
Only new synthetic designs in a temporary project are approved/downloaded.
The JSON evidence lives at the project root. Physical sew-out remains pending.
"""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time

from embroiderly.web import create_app
from embroiderly.machine_files import read_pattern
from embroiderly.lettering_trial import measure


VERSE = ('rejoice in our confident hope.\nBe patient in trouble,\n'
         'and keep on praying.\nromans 12:12 NLT')


def main():
    cases = [(word, size, 110) for word in ('Hello World', 'tiny', 'jesus is\nkings', 'Baby 0689', 'i j . , :')
             for size in (4, 5, 6)]
    cases += [(VERSE, 4, 100), (VERSE, 4, 110)]
    alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ\nabcdefghijklmnopqrstuvwxyz\n0123456789\n.,:;"\'()-+/#&@'
    cases += [(alphabet, size, 400) for size in (4, 5, 6)]
    # Keep the failing reverse-line semicolon cases above; this explicitly
    # different layout checks the installed forward variant without substitution.
    cases += [(';\nABCDEFGHIJKLMNOPQRSTUVWXYZ\nabcdefghijklmnopqrstuvwxyz\n0123456789\n.,:"\'()-+/#&@', size, 400) for size in (4, 5, 6)]
    rows = []
    with TemporaryDirectory(prefix='.repair-native-', dir='.') as temporary:
        root = Path(temporary).resolve()
        client = create_app(root).test_client()
        for words, size, width in cases:
            started = time.monotonic()
            recipe = dict(text=words, font='small_font', height_mm=size,
                          available_width_mm=width, align='center', colour='#202020')
            response = client.post('/lettering/native/check', json=recipe)
            data = response.json
            row = dict(text=words, nominal_height_mm=size, available_width_mm=width,
                       status=response.status_code, passed=data.get('checks_passed', False),
                       issues=data.get('issues'), reports=data.get('reports'), error=data.get('error'),
                       fit=data.get('fit'), physical_sew_out='pending')
            if row['passed']:
                key = data['id']
                approved = client.post(f'/lettering/native/{key}/approve', json={'approve': True})
                assert approved.status_code == 200, approved.json
                row['downloads'] = {}
                for fmt in ('dst', 'pes'):
                    files = [client.get(f'/lettering/native/{key}/download/{fmt}') for _ in range(3)]
                    assert all(r.status_code == 200 for r in files)
                    assert files[0].data == files[1].data == files[2].data
                    path = root / ('download.' + fmt)
                    path.write_bytes(files[0].data)
                    report, _, _ = measure(read_pattern(path))
                    assert report['short'] == report['long'] == 0
                    row['downloads'][fmt] = dict(sha256=hashlib.sha256(files[0].data).hexdigest(),
                        readback=report, repeated_downloads_identical=True)
                assert row['downloads']['dst']['readback']['trims'] == row['downloads']['pes']['readback']['trims']
            row['seconds'] = round(time.monotonic() - started, 2)
            rows.append(row)
            Path('native-repair-verification.json').write_text(json.dumps(rows, indent=2))
            print(json.dumps(row), flush=True)
        assert not list((root / 'work/uploads').iterdir()), 'Native text entered raster uploads'
    print(f'{sum(r["passed"] for r in rows)}/{len(rows)} cases passed; no sew-out or density certification.', flush=True)
    return all(row['passed'] for row in rows)


if __name__ == '__main__':
    raise SystemExit(0 if main() else 1)
