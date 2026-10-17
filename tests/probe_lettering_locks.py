"""Diagnostic experiment only: explicit SVG locks instead of path-following locks.

Does not edit source/fonts or approve downloads. Uses the real app in temporary
storage and its unchanged written-file gates. See Ink/Stitch lock-stitch docs.
"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET
from embroiderly import lettering_source
from embroiderly.lettering_geometry import SVG, INK
from embroiderly.web import create_app


def main():
    route = lettering_source.route_font
    def explicit(svg):
        routed, cuts = route(svg)
        root = ET.fromstring(routed)
        for node in root.iter(SVG+'path'):
            for end in ('start', 'end'):
                node.set(INK+'lock_custom_'+end, 'M 0,0 L 0.6,0 L 0,0 L 0.6,0 L 0,0 L 0.6,0')
                node.set(INK+'lock_'+end+'_scale_percent', '100')
        return ET.tostring(root, encoding='unicode'), cuts
    lettering_source.route_font = explicit
    rows = []
    try:
        with TemporaryDirectory(prefix='.repair-lock-probe-', dir='.') as temporary:
            client = create_app(Path(temporary).resolve()).test_client()
            for words, size in [('tiny i .', 3.8), ('Jesus is King', 3.8), ('Jesus is King', 8)]:
                response = client.post('/lettering/native/check', json=dict(text=words, font='small_font',
                    height_mm=size, available_width_mm=400, align='center', colour='#202020'))
                data = response.json
                row = dict(text=words, size=size, status=response.status_code, reports=data.get('reports'),
                           issues=data.get('issues'), error=data.get('error'), passed=data.get('checks_passed'))
                print(json.dumps(row), flush=True);rows.append(row)
            Path('lettering-lock-probe.json').write_text(json.dumps(rows, indent=2))
    finally:
        lettering_source.route_font = route


if __name__ == '__main__':
    main()
