"""Real app generation at editable font sizes, with temporary designs only."""
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from embroiderly.web import create_app
from embroiderly.machine_files import read_pattern
from embroiderly.lettering_trial import measure


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sizes', nargs='+', type=float, default=[3.6, 4, 6, 8, 12, 15.2])
    parser.add_argument('--report', default='size-range-verification.json')
    args = parser.parse_args()
    rows = []
    with TemporaryDirectory(prefix='.repair-size-', dir='.') as temporary:
        root = Path(temporary).resolve()
        client = create_app(root).test_client()
        for text in ['tiny i .', 'Jesus is King']:
            for size in args.sizes:
                result = client.post('/lettering/native/check', json=dict(
                    text=text, font='small_font', height_mm=size,
                    available_width_mm=400, align='center', colour='#202020'))
                data = result.json
                row = dict(text=text, font_size=size, status=result.status_code,
                           passed=data.get('checks_passed', False), error=data.get('error'),
                           reports=data.get('reports'), issues=data.get('issues'), seconds=data.get('seconds'),
                           lock_adjustment=data.get('lock_adjustment'))
                if row['passed']:
                    key = data['id']
                    assert client.post('/lettering/native/'+key+'/approve', json={'approve': True}).status_code == 200
                    row['downloads'] = {}
                    for fmt in ['dst', 'pes']:
                        r = client.get('/lettering/native/'+key+'/download/'+fmt)
                        assert r.status_code == 200
                        file = root/('checked.'+fmt); file.write_bytes(r.data)
                        row['downloads'][fmt] = measure(read_pattern(file))[0]
                        assert row['downloads'][fmt]['short'] == row['downloads'][fmt]['long'] == 0
                    assert row['downloads']['dst']['trims'] == row['downloads']['pes']['trims']
                rows.append(row)
                Path(args.report).write_text(json.dumps(rows, indent=2))
                print(json.dumps(row), flush=True)
    return all(r['passed'] for r in rows)


if __name__ == '__main__':
    raise SystemExit(0 if main() else 1)
