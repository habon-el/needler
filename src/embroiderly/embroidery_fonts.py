"""Needler embroidery fonts: bundled TrueType outlines converted to satin columns.

Each font lists its source file, nominal letter height (capital H) and the
scale range we allow. Layout applies the font's own advance widths and pair
kerning, then writes one SVG group per glyph whose paths are satin columns
(two rails plus rungs) for the native stitch engine.
"""
from functools import lru_cache
import hashlib
import math
from pathlib import Path
import xml.etree.ElementTree as ET
from .satin_font import _font, glyph_columns

FONT_DIR = Path(__file__).with_name('fonts')
SVG_NS = 'http://www.w3.org/2000/svg'
INK_NS = 'http://inkstitch.org/namespace'
LABEL_NS = 'http://www.inkscape.org/namespaces/inkscape'
PX_MM = 25.4/96
CHARACTERS = ''.join(chr(c) for c in range(33, 127))+'ÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜÝàáâãäåçèéêëìíîïñòóôõöùúûüýÿ£€©®°'

FONTS = {
    'small_font': dict(name='Needler Sans', label='Needler Sans (DejaVu Sans Bold)',
                       file='dejavu/DejaVuSans-Bold.ttf', package='fonts-dejavu-core',
                       size=4.0, min_scale=.9, max_scale=3.8, puff_max_scale=5.5, tracking=.06,
                       zigzag_mm=.38, pull_mm=.1),
    'lato_black': dict(name='Needler Lato', label='Needler Lato (Lato Black)',
                       file='lato/Lato-Black.ttf', package='fonts-lato',
                       size=4.0, min_scale=1.0, max_scale=3.8, puff_max_scale=6.5, tracking=.07,
                       zigzag_mm=.38, pull_mm=.1),
}


def font_path(key):
    return str(FONT_DIR/FONTS[key]['file'])


@lru_cache(maxsize=None)
def glyph_set(key):
    font = _font(font_path(key))
    cmap = font.getBestCmap()
    return ''.join(c for c in CHARACTERS if ord(c) in cmap)


def catalogue():
    """Installed embroidery fonts in the shape the lettering screens expect."""
    result = {}
    for key, data in FONTS.items():
        path = FONT_DIR/data['file']
        if path.is_file() and (path.parent/'LICENSE').is_file():
            result[key] = dict(data, key=key, glyphs=glyph_set(key))
    return result


def fingerprint(key):
    h = hashlib.sha256(repr(sorted(FONTS[key].items())).encode())
    h.update((FONT_DIR/FONTS[key]['file']).read_bytes())
    for name in ('satin_font.py', 'embroidery_fonts.py'):
        h.update(Path(__file__).with_name(name).read_bytes())
    return h.hexdigest()


@lru_cache(maxsize=None)
def cap_height(key):
    _, _, shape = glyph_columns(font_path(key), 'H')
    left, top, right, bottom = shape.bounds
    return bottom-top


@lru_cache(maxsize=None)
def _kerning(key):
    """Pair kerning from GPOS (format 1 and 2) or the legacy kern table, in em."""
    font = _font(font_path(key))
    em = font['head'].unitsPerEm
    pairs, classes = {}, []
    if 'GPOS' in font:
        table = font['GPOS'].table
        for feature in table.FeatureList.FeatureRecord if table.FeatureList else []:
            if feature.FeatureTag != 'kern':
                continue
            for index in feature.Feature.LookupListIndex:
                lookup = table.LookupList.Lookup[index]
                subtables = lookup.SubTable
                if lookup.LookupType == 9:
                    subtables = [s.ExtSubTable for s in subtables if s.ExtensionLookupType == 2]
                elif lookup.LookupType != 2:
                    continue
                for sub in subtables:
                    if sub.Format == 1:
                        for first, pairset in zip(sub.Coverage.glyphs, sub.PairSet):
                            for record in pairset.PairValueRecord:
                                value = getattr(record.Value1, 'XAdvance', 0) or 0
                                if value:
                                    pairs.setdefault((first, record.SecondGlyph), value/em)
                    elif sub.Format == 2:
                        classes.append((set(sub.Coverage.glyphs), sub.ClassDef1.classDefs,
                                        sub.ClassDef2.classDefs, sub.Class1Record))
    elif 'kern' in font:
        for table in font['kern'].kernTables:
            for (first, second), value in table.kernTable.items():
                pairs.setdefault((first, second), value/em)
    return pairs, classes


def kerning(key, left, right):
    font = _font(font_path(key))
    cmap = font.getBestCmap()
    a, b = cmap.get(ord(left)), cmap.get(ord(right))
    if a is None or b is None:
        return 0.0
    pairs, classes = _kerning(key)
    if (a, b) in pairs:
        return pairs[(a, b)]
    em = font['head'].unitsPerEm
    for coverage, first, second, records in classes:
        if a in coverage:
            value = getattr(records[first.get(a, 0)].Class2Record[second.get(b, 0)].Value1, 'XAdvance', 0) or 0
            if value:
                return value/em
    return 0.0


def _lerp(p, q, t):
    return (p[0]+(q[0]-p[0])*t, p[1]+(q[1]-p[1])*t)


def _path(points):
    return 'M '+' L '.join(f'{x:.4f},{y:.4f}' for x, y in points)


def _joins(a, b, index, step, others):
    """Whether the column end at `index` runs into another stroke: a point just
    beyond the end lies inside one."""
    from shapely.geometry import Point
    if others.is_empty or len(a) < 2:
        return False
    m = _lerp(a[index], b[index], .5)
    n = _lerp(a[index+step], b[index+step], .5)
    d = math.dist(m, n)
    if d < 1e-9:
        return False
    return others.buffer(1e-6).contains(Point(m[0]+(m[0]-n[0])/d*.6/PX_MM, m[1]+(m[1]-n[1])/d*.6/PX_MM))


def layout(text, key, scale_percent, align='left', colour='#000000', puff=False, foam_mm=3.0):
    """SVG of satin-column lettering; user units are CSS px (96 per inch).
    puff: letters over foam (see stitch_satin._puff_satin). Each letter has a
    placement line sewn before the stop for the foam, then a perforation line
    just inside it that tacks the foam down, then its columns."""
    from .stitch_engine import PUFF_MAX_MM, puff_min_mm
    puff_columns = (puff_min_mm(foam_mm), PUFF_MAX_MM)
    puff_pull = '.35' if foam_mm < 2.5 else '.45'  # outer edge; sewn 0.05 mm inside
    data = FONTS[key]
    size_mm = data['size']*scale_percent/100
    em_px = size_mm/cap_height(key)/PX_MM
    font = _font(font_path(key))
    hhea = font['hhea']
    em = font['head'].unitsPerEm
    line_px = (hhea.ascent-hhea.descent+hhea.lineGap)/em*em_px*1.05
    lines = text.split('\n')
    placed, widths = [], []
    for row, line in enumerate(lines):
        x = 0.0
        glyphs = []
        for i, char in enumerate(line):
            columns, advance, _ = glyph_columns(font_path(key), char) if char != ' ' else ((), None, None)
            if char == ' ':
                advance = font['hmtx'][font.getBestCmap()[32]][0]/em if 32 in font.getBestCmap() else .3
            glyphs.append((char, x, columns))
            x += (advance+data['tracking'])*em_px
            if i+1 < len(line):
                x += kerning(key, char, line[i+1])*em_px
        widths.append(max(0.0, x-data['tracking']*em_px))
        placed.append((row, glyphs))
    widest = max(widths) if widths else 0.0
    ET.register_namespace('', SVG_NS); ET.register_namespace('inkstitch', INK_NS)
    ET.register_namespace('inkscape', LABEL_NS)
    root = ET.Element(f'{{{SVG_NS}}}svg', width=f'{widest+em_px:.3f}', height=f'{len(lines)*line_px+em_px:.3f}')
    metadata = ET.SubElement(root, f'{{{SVG_NS}}}metadata')
    ET.SubElement(metadata, f'{{{INK_NS}}}inkstitch_svg_version').text = '3'
    count = 0
    for (row, glyphs), width in zip(placed, widths):
        shift = (widest-width)*{'left': 0, 'center': .5, 'right': 1}[align]
        line_group = ET.SubElement(root, f'{{{SVG_NS}}}g', {f'{{{INK_NS}}}letter-group': 'line'})
        baseline = row*line_px+line_px*.8
        for char, x, columns in glyphs:
            if char == ' ':
                continue
            group = ET.SubElement(line_group, f'{{{SVG_NS}}}g', {f'{{{INK_NS}}}letter-group': 'glyph',
                                                             f'{{{LABEL_NS}}}label': char})
            place = lambda p: (shift+x+p[0]*em_px, baseline+p[1]*em_px)
            travel = None
            nodes = []
            sewn_columns, column_nodes = [], []
            previous_end = None
            for a, b, closed, width_em in columns:
                ra, rb = [place(p) for p in a], [place(p) for p in b]
                sewn_columns.append((ra, rb))
                walk = width_em*2*em_px*PX_MM >= .9
                start = _lerp(ra[0], rb[0], .5) if walk else _lerp(ra[0], rb[0], .3)
                if previous_end is not None:
                    # Move between strokes inside the letter, never across fabric.
                    if travel is None:
                        from shapely.affinity import affine_transform
                        from .stitch_paths import Travel
                        shape = glyph_columns(font_path(key), char)[2]
                        placed = affine_transform(shape, [em_px, 0, 0, em_px, shift+x, baseline])
                        travel = Travel(placed, inset=.15/PX_MM, slack=.05/PX_MM)
                    route = travel.route(previous_end, start, direct_mm=math.inf)
                    if route is None:
                        nodes[-1].set(f'{{{INK_NS}}}trim_after', 'true')
                    else:
                        # Explicit even when straight: the satin ends on its
                        # outer edge, so the needle first steps back inside.
                        count += 1
                        nodes.append(ET.SubElement(group, f'{{{SVG_NS}}}path', {
                            **({f'{{{INK_NS}}}puff': 'true'} if puff else {}),
                            'id': f'travel{count}', 'd': _path(route),
                            'style': f'fill:none;stroke:{colour};stroke-width:{.2/PX_MM:.3f}',
                            f'{{{INK_NS}}}stroke_method': 'running_stitch',
                            f'{{{INK_NS}}}running_stitch_length_mm': '1.2',
                            f'{{{INK_NS}}}running_stitch_tolerance_mm': '0'}))
                previous_end = _lerp(rb[-1], ra[-1], .3)
                d = ' '.join([_path(ra), _path(rb)])
                width_mm = width_em*2*em_px*PX_MM
                if puff and not puff_columns[0] <= width_mm <= puff_columns[1]:
                    raise ValueError(f'3D puff on {foam_mm:g} mm foam needs letter strokes {puff_columns[0]:g}–{puff_columns[1]:g} mm wide; '
                                     f'“{char}” has a {width_mm:.1f} mm stroke at this size. '
                                     + (('Use a larger size or a bolder font' + (' or 2 mm foam' if foam_mm > 2 else '')
                                         + ': thinner strokes cannot hold the foam down.')
                                        if width_mm < puff_columns[0] else 'Use a smaller size.'))
                count += 1
                attributes = {
                    'id': f'column{count}', 'd': d,
                    'style': f'fill:none;stroke:{colour};stroke-width:{.2/PX_MM:.3f}',
                    f'{{{INK_NS}}}satin_column': 'true',
                    f'{{{INK_NS}}}zigzag_spacing_mm': f"{data['zigzag_mm']:g}",
                    f'{{{INK_NS}}}pull_compensation_mm': f"{data['pull_mm']:g}",
                    f'{{{INK_NS}}}center_walk_underlay': 'true' if width_mm >= .9 else 'false',
                }
                if len(ra) == len(rb):
                    # Rails are matched cross-sections: stitch vertex i to vertex i.
                    attributes[f'{{{INK_NS}}}satin_pairs'] = 'indexed'
                if puff:
                    attributes.update({f'{{{INK_NS}}}puff': 'true', f'{{{INK_NS}}}zigzag_spacing_mm': '.22',
                                       f'{{{INK_NS}}}pull_compensation_mm': puff_pull})
                node = ET.SubElement(group, f'{{{SVG_NS}}}path', attributes)
                nodes.append(node)
                column_nodes.append(node)
            if puff and nodes:
                # The sewn columns, not the font outline: corners the columns leave
                # open stay unsewn, and the perforation must stay inside the stitches.
                from shapely.geometry import Polygon
                from shapely.ops import unary_union
                shape = unary_union([Polygon(list(a) + list(b)[::-1]).buffer(0) for a, b in sewn_columns])
                # Caps only on open ends: an end that runs into another stroke of the
                # letter is a join, and a cap there only piles thread on it.
                for k, ((a, b), column) in enumerate(zip(sewn_columns, column_nodes)):
                    others = unary_union([Polygon(list(p) + list(q)[::-1]).buffer(0)
                                          for j, (p, q) in enumerate(sewn_columns) if j != k])
                    column.set(f'{{{INK_NS}}}puff_caps', ' '.join(
                        end for end, index, step in (('start', 0, 1), ('end', -1, -1))
                        if not _joins(a, b, index, step, others)) or 'none')
                inner = shape.buffer(-.1/PX_MM)
                rings = [list(p.exterior.coords) + [p.exterior.coords[0]] for p in getattr(inner, 'geoms', [inner]) if not p.is_empty]
                first = _lerp(sewn_columns[0][0][0], sewn_columns[0][1][0], .5)
                placement = shape.buffer(-.3/PX_MM)
                placement = [list(p.exterior.coords) for p in getattr(placement, 'geoms', [placement]) if not p.is_empty] or rings
                for index, ring in enumerate(placement):
                    # Sewn on the fabric before the stop: where to lay the foam.
                    count += 1
                    ET.SubElement(group, f'{{{SVG_NS}}}path', {
                        'id': f'placement{count}', 'd': _path(ring),
                        'style': f'fill:none;stroke:{colour};stroke-width:{.2/PX_MM:.3f}',
                        f'{{{INK_NS}}}stroke_method': 'running_stitch', f'{{{INK_NS}}}puff_placement': 'true',
                        f'{{{INK_NS}}}running_stitch_length_mm': '2.5', f'{{{INK_NS}}}trim_after': 'true',
                        f'{{{INK_NS}}}running_stitch_tolerance_mm': '.1'})
                for index, ring in enumerate(rings):
                    # Tack the foam down first, starting and ending beside the first column.
                    here = min(range(len(ring)-1), key=lambda i: math.dist(ring[i], first))
                    ring = ring[here:-1] + ring[:here+1]
                    count += 1
                    group.insert(index, ET.Element(f'{{{SVG_NS}}}path', {
                        'id': f'perforate{count}', 'd': _path(ring),
                        'style': f'fill:none;stroke:{colour};stroke-width:{.2/PX_MM:.3f}',
                        f'{{{INK_NS}}}stroke_method': 'running_stitch', f'{{{INK_NS}}}puff': 'true',
                        f'{{{INK_NS}}}running_stitch_length_mm': '1.0',
                        f'{{{INK_NS}}}running_stitch_tolerance_mm': '0'}))
            if nodes:
                nodes[-1].set(f'{{{INK_NS}}}trim_after', 'true')
    return ET.tostring(root, encoding='unicode')
