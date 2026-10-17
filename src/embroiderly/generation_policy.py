"""Explicit generation limits; rendering fabric textures are not sewing presets."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

NS = '{http://inkstitch.org/namespace}'


def apply(document, settings):
    rows = json.loads(Path(__file__).with_name('knowledge').joinpath('generation.json').read_text())['rows']
    fabric = settings.get('fabric_preset', 'twill')
    preset = next((r for r in rows if r['fabric'] == fabric), None)
    if preset is None:
        raise ValueError('No verified generation preset for this fabric. Select a supported sewing preset.')
    # Never regenerate a locked object with different source settings.
    if any(p.get('locked') for p in settings.get('piece_edits', {}).values()):
        raise ValueError('Unlock the locked pieces before applying generation repairs.')
    metadata = next(n for n in document if n.tag.split('}')[-1] == 'metadata')
    ET.SubElement(metadata, NS+'min_stitch_len_mm').text = '0.45'
    ET.SubElement(metadata, NS+'collapse_len_mm').text = '0'
    count = 0
    for node in document.iter():
        if node.tag.split('}')[-1] != 'path':
            continue
        node.set(NS+'min_stitch_length_mm', '0.45')
        if 'fill:' in node.get('style', '') and 'fill:none' not in node.get('style', ''):
            # Preserve explicitly authored decorative spacing.
            if NS+'row_spacing_mm' not in node.attrib:
                node.set(NS+'row_spacing_mm', str(preset['row_spacing_mm']))
        # Components already have separate SVG paths. Cut conservatively; hidden
        # future-coverage travel is not yet certified by the release gate.
        node.set(NS+'trim_after', 'true')
        node.set(NS+'lock_start', 'custom')
        node.set(NS+'lock_end', 'custom')
        node.set(NS+'lock_custom_start', '1 -1 1 -1')
        node.set(NS+'lock_custom_end', '1 -1 1 -1')
        node.set(NS+'lock_start_scale_mm', '0.6')
        node.set(NS+'lock_end_scale_mm', '0.6')
        count += 1
    return {'fabric_preset': fabric, 'row_spacing_mm': preset['row_spacing_mm'],
            'min_stitch_length_mm': 0.45, 'collapse_len_mm': 0,
            'elements': count, 'trim_policy': 'conservative component cuts',
            'lock_style': 'custom: 1 -1 1 -1', 'lock_scale_mm': 0.6}
