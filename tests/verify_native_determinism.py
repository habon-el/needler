"""Cold-generation diagnostic; a cached download is not a determinism proof."""
import hashlib
import json
from pathlib import Path
from embroiderly.small_lettering import generate


def main():
    recipe = dict(text='Hello World', font='small_font', height_mm=5, align='center')
    runs = [generate(recipe, native=True) for _ in range(2)]
    rows = []
    for run in runs:
        commands = run['plan']['stitches']
        rows.append(dict(source_sha256=hashlib.sha256(run['svg'].encode()).hexdigest(),
                         commands_sha256=hashlib.sha256(json.dumps(commands).encode()).hexdigest(),
                         command_count=len(commands)))
    evidence = dict(recipe=recipe, runs=rows,
                    source_identical=runs[0]['svg']==runs[1]['svg'],
                    commands_identical=runs[0]['plan']['stitches']==runs[1]['plan']['stitches'])
    Path('native-cold-generation-verification.json').write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence), flush=True)
    return evidence['commands_identical']


if __name__ == '__main__':
    raise SystemExit(0 if main() else 1)
