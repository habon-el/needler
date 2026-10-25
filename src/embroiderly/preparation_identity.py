"""A prepared image/preview belongs to its source, options AND pipeline revision.

Only our local source and knowledge data are read. Installed libraries, model
files and generated outputs are not inspected. A change makes an old plan stale;
it never deletes, rewrites or silently regenerates that saved plan.
"""
import hashlib
import json
from pathlib import Path


def revision():
    root = Path(__file__).parent
    digest = hashlib.sha256(b'preparation-source-v3')
    # Conservatively invalidate on backend changes. The previous constant
    # "prep-v2" allowed a fixed preparation algorithm to display old bad stitches.
    paths = sorted(p for p in root.iterdir() if p.suffix == '.py')
    paths += sorted(p for p in (root / 'knowledge').iterdir() if p.suffix == '.json')
    for path in paths:
        digest.update(str(path.relative_to(root)).encode())
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def preparation_key(source_bytes, options):
    from .canvas_guides import without_guides
    digest = hashlib.sha256(source_bytes)
    # Guides on the canvas are drawing aids: they never make a different preparation or stitch plan.
    digest.update(json.dumps(without_guides(options), sort_keys=True).encode())
    digest.update(revision().encode())
    return digest.hexdigest()[:24]
