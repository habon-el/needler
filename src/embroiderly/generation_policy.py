"""Explicit generation limits; rendering fabric textures are not sewing presets.

Fabric presets (fabric_preset): density, satin spacing and pull compensation, fill
underlay, fill stitch length, tie-off size and backing/topping advice per fabric, from knowledge/generation.json.
Values are starting points from published digitizing guidance, not sew-out
verified (each row says so)."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

NS = '{http://inkstitch.org/namespace}'
DEFAULT = 'twill'


def presets():
    return json.loads(Path(__file__).with_name('knowledge').joinpath('generation.json').read_text(encoding='utf-8'))['rows']


def preset_for(settings):
    """The fabric row for these settings; a custom fabric (fabric_custom) is its base
    fabric with the user's own values and name (custom_fabrics.py)."""
    if (settings or {}).get('fabric_custom'):
        from .custom_fabrics import check, LIMITS
        custom = check(settings['fabric_custom'])
        base = next(r for r in presets() if r['fabric'] == custom['base'])
        return dict(base, **{k: custom[k] for k in (*LIMITS, 'fill_underlay')}, label=custom['name'], custom=custom)
    fabric = (settings or {}).get('fabric_preset', DEFAULT)
    preset = next((r for r in presets() if r['fabric'] == fabric), None)
    if preset is None:
        raise ValueError('No verified generation preset for this fabric. Select a supported sewing preset.')
    return preset


# Adjust stitch spacing: one design-wide choice scales row and satin spacing.
DENSITY = {'lighter': 1.12, 'normal': 1.0, 'denser': .9}


def apply(document, settings):
    preset = preset_for(settings)
    density = settings.get('density', 'normal')
    if density not in DENSITY:
        raise ValueError('Choose lighter, normal or denser stitching.')
    factor = DENSITY[density]
    fabric = preset['fabric']
    # Never regenerate a locked object with different source settings.
    if any(p.get('locked') for p in settings.get('piece_edits', {}).values()):
        raise ValueError('Unlock the locked pieces before applying generation repairs.')
    metadata = next(n for n in document if n.tag.split('}')[-1] == 'metadata')
    ET.SubElement(metadata, NS+'min_stitch_len_mm').text = '0.45'
    ET.SubElement(metadata, NS+'collapse_len_mm').text = '0'
    # Branching: travel inside sewn areas between same-colour parts instead of cutting.
    ET.SubElement(metadata, NS+'branching').text = 'true' if settings.get('branching', True) else 'false'
    lock = str(preset.get('lock_scale_mm', .6))
    count = 0
    for node in document.iter():
        if node.tag.split('}')[-1] != 'path':
            continue
        node.set(NS+'min_stitch_length_mm', '0.45')
        if 'fill:' in node.get('style', '') and 'fill:none' not in node.get('style', ''):
            # Preserve explicitly authored decorative spacing.
            if NS+'row_spacing_mm' not in node.attrib:
                node.set(NS+'row_spacing_mm', str(preset['row_spacing_mm']))
            if NS+'fill_method' not in node.attrib:
                # Plain tatami: underlay and stitch length follow the fabric.
                if NS+'fill_underlay' not in node.attrib:
                    node.set(NS+'fill_underlay', 'true' if preset.get('fill_underlay', True) else 'false')
                if preset.get('underlay_row_spacing_mm'):
                    node.set(NS+'fill_underlay_row_spacing_mm', str(preset['underlay_row_spacing_mm']))
                node.set(NS+'max_stitch_length_mm', str(preset.get('max_stitch_length_mm', 3.0)))
        if factor != 1 and NS+'puff_foam_mm' not in node.attrib and node.get(NS+'fill_method') != 'puff_satin'                 and node.get(NS+'puff') != 'true':
            # Density: fill rows and satin stitches closer together or further apart (foam keeps its own).
            if NS+'row_spacing_mm' in node.attrib:
                node.set(NS+'row_spacing_mm', f"{float(node.get(NS+'row_spacing_mm'))*factor:.3f}")
            if node.get(NS+'satin_column') == 'true' or node.get(NS+'fill_method') == 'auto_satin':
                node.set(NS+'zigzag_spacing_mm', f"{float(node.get(NS+'zigzag_spacing_mm', .4))*factor:.3f}")
        # Components already have separate SVG paths. Cut conservatively; hidden
        # future-coverage travel is not yet certified by the release gate.
        node.set(NS+'trim_after', 'true')
        node.set(NS+'lock_start', 'custom')
        node.set(NS+'lock_end', 'custom')
        node.set(NS+'lock_custom_start', '1 -1 1 -1')
        node.set(NS+'lock_custom_end', '1 -1 1 -1')
        node.set(NS+'lock_start_scale_mm', lock)
        node.set(NS+'lock_end_scale_mm', lock)
        count += 1
    return {'fabric_preset': fabric, 'density': density, 'row_spacing_mm': preset['row_spacing_mm'],
            'satin_pull_mm': preset.get('satin_pull_mm'), 'satin_spacing_mm': preset.get('satin_spacing_mm'),
            'stabilizer': preset.get('stabilizer'), 'backing': preset.get('backing'), 'topping': preset.get('topping'),
            'fabric_custom': preset.get('custom'),
            'min_stitch_length_mm': 0.45, 'collapse_len_mm': 0,
            'elements': count, 'trim_policy': 'conservative component cuts',
            'lock_style': 'custom: 1 -1 1 -1', 'lock_scale_mm': float(lock)}
