"""Opt-in real installed-engine checks; generated user-free outputs stay local."""
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from embroiderly.lettering_native import build, recipe


def main():
    output = Path('work/native-lettering-verification')
    output.mkdir(parents=True, exist_ok=True)
    cases = [('jesus', 'jesus is\nkings', 5, 50)]
    cases += [(f'{word.replace(" ", "-")}-{height}', word, height, 50)
              for word in ('Hello World', 'tiny', 'Baby 0689', 'i j . , :') for height in (4, 5, 6)]
    verse = 'rejoice in our confident hope.\nBe patient in trouble,\nand keep on praying.\nromans 12:12 NLT'
    cases += [('verse-100', verse, 4, 100), ('verse-110', verse, 4, 110)]
    results = []
    for name, text, height, width in cases:
        with TemporaryDirectory(prefix='check-', dir=output) as tmp:
            folder = Path(tmp)
            body = recipe(dict(text=text, font='small_font', height_mm=height, align='center', available_width_mm=width))
            try:
                r = build(folder, body)
                entry = dict(case=name, passed=r['checks_passed'], fit=r['fit'], reports=r['reports'],
                             seconds=r['seconds'], issues=r['issues'],
                             hashes={fmt:hashlib.sha256((folder/('design.'+fmt)).read_bytes()).hexdigest() for fmt in ('pes','dst')})
                # Keep test output only, never customer input or application state.
                for fmt in ('pes','dst'):
                    (output/(name+'.'+fmt)).write_bytes((folder/('design.'+fmt)).read_bytes())
                (output/(name+'.svg')).write_text((folder/'source.svg').read_text())
            except Exception as error:
                entry = dict(case=name, passed=False, error=str(error))
            results.append(entry)
            print(json.dumps({k:v for k,v in entry.items() if k not in ('hashes','issues')}), flush=True)
            (output/'results.json').write_text(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
