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
    # Open-licence (SIL OFL) fonts. Alfa Slab One and Bowlby One stop lower: their
    # round letters (D, O, 0, q) trace badly larger; Bowlby One's ? never traces cleanly.
    # Size range from stroke widths, as for the two
    # above: the thinnest 10% of strokes at least 0.34 mm, the widest at most
    # 4.2 mm (6 mm for puff). Scripts keep no extra spacing so letters join.
    'graduate': dict(name='Graduate', label='Graduate · varsity',
                      file='graduate/Graduate-Regular.ttf', package='google-fonts-graduate',
                      size=4.0, min_scale=1.1, max_scale=3.8, puff_max_scale=10, tracking=0.06,
                      zigzag_mm=.38, pull_mm=.1),
    'bebas_neue': dict(name='Bebas Neue', label='Bebas Neue · tall sports',
                        file='bebasneue/BebasNeue-Regular.ttf', package='google-fonts-bebasneue',
                        size=4.0, min_scale=1.4, max_scale=3.8, puff_max_scale=9.2, tracking=0.06,
                        zigzag_mm=.38, pull_mm=.1),
    'anton': dict(name='Anton', label='Anton · bold condensed',
                   file='anton/Anton-Regular.ttf', package='google-fonts-anton',
                   size=4.0, min_scale=0.9, max_scale=3.8, puff_max_scale=6.9, tracking=0.06,
                   zigzag_mm=.38, pull_mm=.1),
    'staatliches': dict(name='Staatliches', label='Staatliches · block',
                         file='staatliches/Staatliches-Regular.ttf', package='google-fonts-staatliches',
                         size=4.0, min_scale=0.9, max_scale=3.8, puff_max_scale=7.7, tracking=0.06,
                         zigzag_mm=.38, pull_mm=.1),
    'pacifico': dict(name='Pacifico', label='Pacifico · script',
                      file='pacifico/Pacifico-Regular.ttf', package='google-fonts-pacifico',
                      size=4.0, min_scale=0.9, max_scale=3.8, puff_max_scale=7.1, tracking=0,
                      zigzag_mm=.38, pull_mm=.1),
    'lobster': dict(name='Lobster', label='Lobster · script',
                     file='lobster/Lobster-Regular.ttf', package='google-fonts-lobster',
                     size=4.0, min_scale=1.3, max_scale=3.8, puff_max_scale=7, tracking=0,
                     zigzag_mm=.38, pull_mm=.1),
    'kaushan_script': dict(name='Kaushan Script', label='Kaushan Script · brush',
                            file='kaushanscript/KaushanScript-Regular.ttf', package='google-fonts-kaushanscript',
                            size=4.0, min_scale=1.6, max_scale=3.8, puff_max_scale=8.7, tracking=0,
                            zigzag_mm=.38, pull_mm=.1),
    'alfa_slab_one': dict(name='Alfa Slab One', label='Alfa Slab One · slab',
                           file='alfaslabone/AlfaSlabOne-Regular.ttf', package='google-fonts-alfaslabone',
                           size=4.0, min_scale=0.9, max_scale=2.4, puff_max_scale=4, tracking=0.06,
                           zigzag_mm=.38, pull_mm=.1),
    'righteous': dict(name='Righteous', label='Righteous · retro',
                       file='righteous/Righteous-Regular.ttf', package='google-fonts-righteous',
                       size=4.0, min_scale=1, max_scale=3.8, puff_max_scale=6.1, tracking=0.06,
                       zigzag_mm=.38, pull_mm=.1),
    'russo_one': dict(name='Russo One', label='Russo One · tech',
                       file='russoone/RussoOne-Regular.ttf', package='google-fonts-russoone',
                       size=4.0, min_scale=0.9, max_scale=3.8, puff_max_scale=5.6, tracking=0.06,
                       zigzag_mm=.38, pull_mm=.1),
    'archivo_black': dict(name='Archivo Black', label='Archivo Black · heavy',
                           file='archivoblack/ArchivoBlack-Regular.ttf', package='google-fonts-archivoblack',
                           size=4.0, min_scale=0.9, max_scale=3.2, puff_max_scale=4.6, tracking=0.06,
                           zigzag_mm=.38, pull_mm=.1),
    'bowlby_one': dict(name='Bowlby One', label='Bowlby One · chunky',
                        file='bowlbyone/BowlbyOne-Regular.ttf', package='google-fonts-bowlbyone',
                        size=4.0, min_scale=0.9, max_scale=1.65, puff_max_scale=3.4, tracking=0.06,
                        exclude='?', zigzag_mm=.38, pull_mm=.1),
    'bungee': dict(name='Bungee', label='Bungee · signage',
                    file='bungee/Bungee-Regular.ttf', package='google-fonts-bungee',
                    size=4.0, min_scale=0.9, max_scale=2.7, puff_max_scale=3.9, tracking=0.06,
                    zigzag_mm=.38, pull_mm=.1),
    'passion_one': dict(name='Passion One', label='Passion One · rounded',
                         file='passionone/PassionOne-Bold.ttf', package='google-fonts-passionone',
                         size=4.0, min_scale=0.9, max_scale=2.7, puff_max_scale=3.9, tracking=0.06,
                         zigzag_mm=.38, pull_mm=.1),
    'dejavu_serif': dict(name='Needler Serif', label='Needler Serif · classic',
                          file='dejavu/DejaVuSerif-Bold.ttf', package='fonts-dejavu-core',
                          size=4.0, min_scale=1, max_scale=3.8, puff_max_scale=5.5, tracking=0.06,
                          zigzag_mm=.38, pull_mm=.1),
    'dejavu_condensed': dict(name='Needler Condensed', label='Needler Condensed · narrow',
                              file='dejavu/DejaVuSansCondensed-Bold.ttf', package='fonts-dejavu-core',
                              size=4.0, min_scale=1, max_scale=3.8, puff_max_scale=6.1, tracking=0.06,
                              zigzag_mm=.38, pull_mm=.1),
    'lato_italic': dict(name='Needler Italic', label='Needler Italic · slanted',
                         file='lato/Lato-BoldItalic.ttf', package='fonts-lato',
                         size=4.0, min_scale=1.1, max_scale=3.8, puff_max_scale=7.1, tracking=0.06,
                         zigzag_mm=.38, pull_mm=.1),
}


def font_path(key):
    return str(FONT_DIR/FONTS[key]['file'])


@lru_cache(maxsize=None)
def glyph_set(key):
    font = _font(font_path(key))
    cmap = font.getBestCmap()
    # exclude: characters whose outline does not trace into clean satin columns.
    return ''.join(c for c in CHARACTERS if ord(c) in cmap and c not in FONTS[key].get('exclude', ''))


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


def text_metrics(text, key, line_spacing=1.0):
    """The words in this font, measured in capital heights (scale-free): the
    height of the whole block as layout() places it, and the thinnest and
    widest satin stroke. A size in mm times these gives millimetres."""
    path, cap = font_path(key), cap_height(key)
    font = _font(path)
    hhea, em = font['hhea'], font['head'].unitsPerEm
    line_em = (hhea.ascent-hhea.descent+hhea.lineGap)/em*1.05*line_spacing
    tops, bottoms, strokes = [], [], []
    for row, line in enumerate(text.split('\n')):
        for char in line:
            if char == ' ':
                continue
            columns, _, shape = glyph_columns(path, char)
            if shape.is_empty:
                continue
            _, top, _, bottom = shape.bounds
            tops.append(row*line_em+top)
            bottoms.append(row*line_em+bottom)
            strokes += [width*2 for *_, width in columns]
    if not tops or not strokes:
        return None
    return dict(height=(max(bottoms)-min(tops))/cap, thin=min(strokes)/cap, wide=max(strokes)/cap)


def line_widths(text, key):
    """Each line's width in capital heights, as layout() places the letters (without
    extra letter spacing). A capital height in mm times these gives millimetres."""
    data, font = FONTS[key], _font(font_path(key))
    em, cmap = font['head'].unitsPerEm, font.getBestCmap()
    space = font['hmtx'][cmap[32]][0]/em if 32 in cmap else .3
    widths = []
    for line in text.split('\n'):
        x = 0.0
        for i, char in enumerate(line):
            x += (space if char == ' ' else glyph_columns(font_path(key), char)[1])+data['tracking']
            if i+1 < len(line):
                x += kerning(key, char, line[i+1])
        widths.append(max(0.0, x-data['tracking'])/cap_height(key))
    return widths


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


def size_profile(cap_mm, width_mm, zigzag_mm):
    """Satin settings that follow the letter size, as professional lettering does
    (published digitizing guidance: no underlay under about 5 mm, centre run to 10 mm,
    edge run above; tiny letters sewn more open). Cut-offs are our own."""
    walk = 5.0 <= cap_mm <= 10.0 and width_mm >= .9
    edge = cap_mm > 10.0 and width_mm >= 1.5
    return {
        'zigzag_spacing_mm': f"{max(zigzag_mm, .42) if cap_mm < 6.0 else zigzag_mm:g}",
        'center_walk_underlay': 'true' if walk or (cap_mm > 10.0 and .9 <= width_mm < 1.5) else 'false',
        'contour_underlay': 'true' if edge else 'false',
        'zigzag_underlay': 'true' if edge and width_mm > 3.5 else 'false',
    }


BASELINES = ('straight', 'arc_over', 'arc_under')
SEQUENCES = ('left', 'centre')


def _arc_matrices(placed, widths, widest, em_px, baseline_of, align, baseline, radius_px):
    """Letter placements on an arc: each letter stays rigid, its centre on the
    circle and turned to follow it (as professional arc baselines do). arc_over runs
    over the top of a circle, arc_under along the bottom, both read left to right."""
    out = {}
    for (row, glyphs), width in zip(placed, widths):
        shift = (widest-width)*{'left': 0, 'center': .5, 'right': 1}[align]
        middle, line_y = shift+width/2, baseline_of(row)
        if width > .95*2*math.pi*radius_px:
            raise ValueError('These words do not fit around a circle this small. Use a larger radius or fewer letters.')
        for index, (char, x, columns, advance) in enumerate(glyphs):
            anchor = shift+x+advance*em_px/2
            theta = (anchor-middle)/radius_px
            if baseline == 'arc_over':
                ax, ay, turn = middle+radius_px*math.sin(theta), line_y+radius_px*(1-math.cos(theta)), theta
            else:
                ax, ay, turn = middle+radius_px*math.sin(theta), line_y-radius_px*(1-math.cos(theta)), -theta
            c, s_ = math.cos(turn), math.sin(turn)
            dx = shift+x-anchor   # letter origin relative to its centre on the baseline
            out[row, index] = [c*em_px, -s_*em_px, s_*em_px, c*em_px, ax+c*dx, ay+s_*dx]
    return out


def layout(text, key, scale_percent, align='left', colour='#000000', puff=False, foam_mm=3.0, fill=False,
           pull_mm=None, letter_spacing_mm=0.0, line_spacing=1.0, baseline='straight', radius_mm=None,
           sequence='left', arc_degrees=None):
    """SVG of satin-column lettering; user units are CSS px (96 per inch).
    puff: letters over foam (see stitch_satin._puff_satin). Each letter has a
    placement line sewn before the stop for the foam, then a perforation line
    just inside it that tacks the foam down, then its columns. pull_mm replaces
    the font's own pull compensation (fabric preset). letter_spacing_mm is added
    between letters, line_spacing scales the line height; baseline/radius_mm bend
    a single line on an arc (arc_degrees instead of radius_mm: how far round the
    circle the words reach, so the curve looks the same for any length); sequence='centre' sews from the middle letter out
    (centre-out, for caps). Letters that touch are joined by travel
    inside both instead of a cut."""
    if baseline not in BASELINES or sequence not in SEQUENCES:
        raise ValueError('Choose a listed baseline and letter order.')
    from .stitch_engine import PUFF_MAX_MM, puff_min_mm
    puff_columns = (puff_min_mm(foam_mm), PUFF_MAX_MM)
    puff_pull = '.35' if foam_mm < 2.5 else '.45'  # outer edge; sewn 0.05 mm inside
    data = FONTS[key]
    pull_mm = data['pull_mm'] if pull_mm is None else pull_mm
    size_mm = data['size']*scale_percent/100
    em_px = size_mm/cap_height(key)/PX_MM
    font = _font(font_path(key))
    hhea = font['hhea']
    em = font['head'].unitsPerEm
    line_px = (hhea.ascent-hhea.descent+hhea.lineGap)/em*em_px*1.05*line_spacing
    lines = text.split('\n')
    placed, widths = [], []
    for row, line in enumerate(lines):
        x = 0.0
        glyphs = []
        for i, char in enumerate(line):
            columns, advance, _ = glyph_columns(font_path(key), char) if char != ' ' else ((), None, None)
            if char == ' ':
                advance = font['hmtx'][font.getBestCmap()[32]][0]/em if 32 in font.getBestCmap() else .3
            glyphs.append((char, x, columns, advance))
            x += (advance+data['tracking'])*em_px
            if i+1 < len(line):
                x += kerning(key, char, line[i+1])*em_px+letter_spacing_mm/PX_MM
        widths.append(max(0.0, x-data['tracking']*em_px))
        placed.append((row, glyphs))
    widest = max(widths) if widths else 0.0
    baseline_of = lambda row: row*line_px+line_px*.8
    # Each letter's placement from font units (shapely affine order: a, b, d, e, xoff, yoff).
    matrices = {(row, index): [em_px, 0, 0, em_px, (widest-width)*{'left': 0, 'center': .5, 'right': 1}[align]+x,
                               baseline_of(row)]
                for (row, glyphs), width in zip(placed, widths) for index, (_, x, *_) in enumerate(glyphs)}
    size = (widest+em_px, len(lines)*line_px+em_px)
    if baseline != 'straight':
        if len(lines) > 1:
            raise ValueError('Arc lettering takes one line. Remove the line breaks or use a straight baseline.')
        if arc_degrees is not None:
            if not 10 <= float(arc_degrees) <= 300:
                raise ValueError('Choose a curve from 10 to 300 degrees.')
            radius_px = max(widest, em_px)/math.radians(float(arc_degrees))
        elif not radius_mm or not 5 <= float(radius_mm) <= 1000:
            raise ValueError('Enter an arc radius from 5 to 1000 mm.')
        else:
            radius_px = float(radius_mm)/PX_MM
        matrices = _arc_matrices(placed, widths, widest, em_px, baseline_of, align, baseline, radius_px)
        # Keep the bent words on the page: measure them and move them in by half an em.
        from shapely.affinity import affine_transform
        from shapely.ops import unary_union
        outline = unary_union([affine_transform(glyph_columns(font_path(key), char)[2], matrices[row, index])
                               for row, glyphs in placed for index, (char, *_) in enumerate(glyphs) if char != ' '])
        if not outline.is_empty:
            left, top, right, bottom = outline.bounds
            for m in matrices.values():
                m[4] += em_px/2-left
                m[5] += em_px/2-top
            size = (right-left+em_px, bottom-top+em_px)
    ET.register_namespace('', SVG_NS); ET.register_namespace('inkstitch', INK_NS)
    ET.register_namespace('inkscape', LABEL_NS)
    root = ET.Element(f'{{{SVG_NS}}}svg', width=f'{size[0]:.3f}', height=f'{size[1]:.3f}')
    metadata = ET.SubElement(root, f'{{{SVG_NS}}}metadata')
    ET.SubElement(metadata, f'{{{INK_NS}}}inkstitch_svg_version').text = '3'
    count = 0
    for row, glyphs in placed:
        line_group = ET.SubElement(root, f'{{{SVG_NS}}}g', {f'{{{INK_NS}}}letter-group': 'line'})
        order = [i for i, g in enumerate(glyphs) if g[0] != ' ']
        if sequence == 'centre' and len(order) > 2:
            # Centre-out: middle letter to the right end, then left of the middle to the left
            # end, so a cap's front panel is sewn from the centre seam outward.
            middle = len(order)//2
            order = order[middle:]+order[:middle][::-1]
        sewn_letters = []
        for index in order:
            char, x, columns, _ = glyphs[index]
            m = matrices[row, index]
            group = ET.SubElement(line_group, f'{{{SVG_NS}}}g', {f'{{{INK_NS}}}letter-group': 'glyph',
                                                             f'{{{LABEL_NS}}}label': char})
            place = lambda p, m=m: (m[0]*p[0]+m[1]*p[1]+m[4], m[2]*p[0]+m[3]*p[1]+m[5])
            if fill:
                # Big letters: strokes too wide for satin are sewn as one tatami fill
                # per letter (holes kept), as professional lettering does.
                from shapely.affinity import affine_transform
                outline = affine_transform(glyph_columns(font_path(key), char)[2], m)
                rings = [ring for poly in getattr(outline, 'geoms', [outline]) if not poly.is_empty
                         for ring in (poly.exterior, *poly.interiors)]
                if rings:
                    count += 1
                    ET.SubElement(group, f'{{{SVG_NS}}}path', {
                        'id': f'fill{count}', 'd': ' '.join(_path(list(r.coords))+' Z' for r in rings),
                        'style': f'fill:{colour};fill-rule:evenodd;stroke:none',
                        f'{{{INK_NS}}}letter_fill': 'true', f'{{{INK_NS}}}fill_method': 'auto_fill',
                        f'{{{INK_NS}}}angle': '45', f'{{{INK_NS}}}row_spacing_mm': '.4',
                        f'{{{INK_NS}}}max_stitch_length_mm': '3.5', f'{{{INK_NS}}}fill_underlay': 'true',
                        f'{{{INK_NS}}}trim_after': 'true'})
                continue
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
                        # Inside the sewn columns, not the font outline: where two
                        # columns meet the outline has an unsewn wedge, and a travel
                        # across it is a thread over bare fabric.
                        from shapely.geometry import Polygon
                        from shapely.ops import unary_union
                        shape = unary_union([Polygon(list(ca) + list(cb)[::-1]).buffer(0) for ca, cb, *_ in columns])
                        travel = Travel(affine_transform(shape, m), inset=.15/PX_MM, slack=.05/PX_MM)
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
                    f'{{{INK_NS}}}pull_compensation_mm': f"{pull_mm:g}",
                    **{f'{{{INK_NS}}}{name}': value
                       for name, value in size_profile(size_mm, width_mm, data['zigzag_mm']).items()},
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
                        # Separate pieces (the dot of i and j): cut between them,
                        # never one stitch across the fabric gap.
                        **({f'{{{INK_NS}}}trim_after': 'true'} if len(rings) > 1 else {}),
                        f'{{{INK_NS}}}running_stitch_tolerance_mm': '0'}))
            if nodes:
                nodes[-1].set(f'{{{INK_NS}}}trim_after', 'true')
                if not puff and sewn_columns:
                    first = sewn_columns[0]
                    sewn_letters.append(dict(group=group, last=nodes[-1], end=previous_end,
                                             start=_lerp(first[0][0], first[1][0], .5), columns=sewn_columns))
        _join_touching(sewn_letters, colour)
    return ET.tostring(root, encoding='unicode')


def _join_touching(letters, colour):
    """Closest join where it is safe: consecutive letters that touch (script fonts,
    tight pairs) are joined by travel inside both letters' sewn columns instead of
    a cut. Letters with fabric between them keep their cut: an uncut thread over
    bare fabric fails the machine-file checks."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from .stitch_paths import Travel
    def area(letter):
        return unary_union([Polygon(list(a)+list(b)[::-1]).buffer(0) for a, b in letter['columns']])
    for here, there in zip(letters, letters[1:]):
        a, b = area(here), area(there)
        if a.distance(b) > .02/PX_MM or here['end'] is None:
            continue
        route = Travel(unary_union([a, b]), inset=.15/PX_MM, slack=.05/PX_MM).route(
            here['end'], there['start'], direct_mm=math.inf)
        if route is None:
            continue
        here['last'].attrib.pop(f'{{{INK_NS}}}trim_after', None)
        there['group'].insert(0, ET.Element(f'{{{SVG_NS}}}path', {
            'id': f"join-{here['last'].get('id')}", 'd': _path(route),
            'style': f'fill:none;stroke:{colour};stroke-width:{.2/PX_MM:.3f}',
            f'{{{INK_NS}}}stroke_method': 'running_stitch',
            f'{{{INK_NS}}}running_stitch_length_mm': '1.2',
            f'{{{INK_NS}}}running_stitch_tolerance_mm': '0'}))
