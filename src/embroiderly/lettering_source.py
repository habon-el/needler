"""Route separate native-font pieces without connecting dots across bare cloth."""
import xml.etree.ElementTree as ET
import re
from shapely.ops import unary_union
from .lettering_geometry import outline, SVG, INK


def route_font(svg):
    columns = outline(svg, with_paths=True)
    union = unary_union(list(columns.values()))
    components = list(union.geoms) if union.geom_type == 'MultiPolygon' else [union]
    root = ET.fromstring(svg)
    previous, previous_part, cuts = None, None, 0
    for index, node in enumerate(root.iter(SVG+'path')):
        # Auto-satin generates random element IDs. An explicit stable seed
        # avoids letting those IDs change the regenerated stitch geometry.
        node.set(INK+'random_seed', str(index+1))
        # Use the app's existing 0.6 mm retracing lock convention, not the
        # font engine's half-stitch locks that become 0.2 mm on small columns.
        for end in ('start', 'end'):
            node.set(INK+'lock_'+end, 'custom')
            node.set(INK+'lock_custom_'+end, '1 -1 1 -1')
            node.set(INK+'lock_'+end+'_scale_mm', '0.6')
        # Lock geometry still passes the ordinary written-file checker.

        shape = columns.get(node.get('id'))
        if shape is None:
            continue
        part = max(range(len(components)), key=lambda i: components[i].intersection(shape).area)
        if previous is not None and part != previous_part:
            if previous.get(INK+'trim_after') != 'true':
                cuts += 1
            previous.set(INK+'trim_after', 'true')
        previous, previous_part = node, part
    # Some engine routing/tie choices use element IDs as well as random_seed.
    # The batch extension assigns random IDs, so normalise identities and their
    # references before generating stitches (no paths/rails are rewritten).
    ids = {node.get('id'): f'native-source-{index}' for index, node in enumerate(root.iter()) if node.get('id')}
    for node in root.iter():
        for attr, value in list(node.attrib.items()):
            if attr == 'id':
                node.set(attr, ids[value])
            else:
                node.set(attr, re.sub(r'#([\w:.-]+)', lambda m: '#'+ids.get(m[1], m[1]), value))
    return ET.tostring(root, encoding='unicode'), cuts

