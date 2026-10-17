"""Regenerate pre-digitized lettering vectors, never scale machine stitches.

The 0.45 mm source minimum uses the application's existing generation margin
above its 0.3 mm readback constraint. It is not a needle-safety certification.
Font-authored rails, rungs, underlay, density, compensation and trims remain
unchanged. Locks may still violate readback limits and must not be exempted.
"""
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET

NS = '{http://inkstitch.org/namespace}'
SVG = '{http://www.w3.org/2000/svg}'
MIN_GENERATED_MM = 0.45


def prepare(svg):
    root = ET.fromstring(svg)
    metadata = root.find(SVG+'metadata')
    if metadata is None:
        metadata = ET.SubElement(root, SVG+'metadata')
    # Replace, rather than duplicate, existing document minimum settings.
    for node in list(metadata):
        if node.tag == NS+'min_stitch_len_mm':
            metadata.remove(node)
    ET.SubElement(metadata, NS+'min_stitch_len_mm').text = str(MIN_GENERATED_MM)
    count = 0
    for node in root.iter(SVG+'path'):
        node.set(NS+'min_stitch_length_mm', str(MIN_GENERATED_MM))
        count += 1
    if not count:
        raise ValueError('The embroidery font produced no letter paths.')
    return ET.tostring(root, encoding='unicode'), count


def rebuild(svg, engine):
    prepared, count = prepare(svg)
    with TemporaryDirectory(prefix='lettering-rebuild-') as temporary:
        source = Path(temporary)/'letters.svg'
        source.write_text(prepared)
        run = subprocess.run([str(engine), '--extension=output', '--format=json', str(source)],
                             capture_output=True, timeout=120, check=True, env={**os.environ, 'PYTHONHASHSEED':'0'})
        plan = json.loads(run.stdout)
    return prepared, plan, dict(method='regenerated font vectors', paths=count,
                                min_stitch_length_mm=MIN_GENERATED_MM,
                                release_approved=False, physical_sew_out='pending')
