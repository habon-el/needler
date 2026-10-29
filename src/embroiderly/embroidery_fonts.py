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
    # round letters (D, O, 0, q) trace badly larger, so they get no split satin above
    # it either (split_satin=False: fill); Bowlby One's ? never traces cleanly.
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
                           zigzag_mm=.38, pull_mm=.1, split_satin=False),
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
                        exclude='?', zigzag_mm=.38, pull_mm=.1, split_satin=False),
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
    # Open-licence (SIL OFL) fonts added 2026-10-28; size ranges from stroke widths as above,
    # narrowed where a sweep of every character at the smallest, middle and largest size failed
    # a file check. Those fonts are fill above their range, not split satin.
    'bangers': dict(name='Bangers', label='Bangers · comic',
                file='bangers/Bangers-Regular.ttf', package='google-fonts-bangers',
                size=4.0, min_scale=1.1, max_scale=2.9, puff_max_scale=5.9, tracking=0.06,
                zigzag_mm=.38, pull_mm=.1, split_satin=False),
    'damion': dict(name='Damion', label='Damion · retro script',
                file='damion/Damion-Regular.ttf', package='google-fonts-damion',
                size=4.0, min_scale=1.1, max_scale=3.8, puff_max_scale=9, tracking=0,
                zigzag_mm=.38, pull_mm=.1),
    'fjalla_one': dict(name='Fjalla One', label='Fjalla One · narrow headline',
                file='fjallaone/FjallaOne-Regular.ttf', package='google-fonts-fjallaone',
                size=4.0, min_scale=1.3, max_scale=3.8, puff_max_scale=8, tracking=0.06,
                zigzag_mm=.38, pull_mm=.1),
    'francois_one': dict(name='Francois One', label='Francois One · condensed bold',
                file='francoisone/FrancoisOne-Regular.ttf', package='google-fonts-francoisone',
                size=4.0, min_scale=1.1, max_scale=3.8, puff_max_scale=7.1, tracking=0.06,
                zigzag_mm=.38, pull_mm=.1),
    'grand_hotel': dict(name='Grand Hotel', label='Grand Hotel · classic script',
                file='grandhotel/GrandHotel-Regular.ttf', package='google-fonts-grandhotel',
                size=4.0, min_scale=1.2, max_scale=3.8, puff_max_scale=11, tracking=0,
                zigzag_mm=.38, pull_mm=.1),
    'leckerli_one': dict(name='Leckerli One', label='Leckerli One · chunky script',
                file='leckerlione/LeckerliOne-Regular.ttf', package='google-fonts-leckerlione',
                size=4.0, min_scale=1.1, max_scale=2.4, puff_max_scale=7.6, tracking=0,
                exclude='~', zigzag_mm=.38, pull_mm=.1, split_satin=False),
    'lilita_one': dict(name='Lilita One', label='Lilita One · rounded bold',
                file='lilitaone/LilitaOne-Regular.ttf', package='google-fonts-lilitaone',
                size=4.0, min_scale=0.9, max_scale=3.36, puff_max_scale=4.8, tracking=0.06,
                zigzag_mm=.38, pull_mm=.1),
    'patua_one': dict(name='Patua One', label='Patua One · soft slab',
                file='patuaone/PatuaOne-Regular.ttf', package='google-fonts-patuaone',
                size=4.0, min_scale=0.9, max_scale=2.4, puff_max_scale=6.7, tracking=0.06,
                zigzag_mm=.38, pull_mm=.1, split_satin=False),
    'paytone_one': dict(name='Paytone One', label='Paytone One · round sans',
                file='paytoneone/PaytoneOne-Regular.ttf', package='google-fonts-paytoneone',
                size=4.0, min_scale=0.9, max_scale=2.1, puff_max_scale=4.4, tracking=0.06,
                zigzag_mm=.38, pull_mm=.1, split_satin=False),
    'sniglet': dict(name='Sniglet', label='Sniglet · playful round',
                file='sniglet/Sniglet-ExtraBold.ttf', package='google-fonts-sniglet',
                size=4.0, min_scale=0.9, max_scale=1.77, puff_max_scale=2.5, tracking=0.06,
                zigzag_mm=.38, pull_mm=.1),
    'titan_one': dict(name='Titan One', label='Titan One · heavy rounded',
                file='titanone/TitanOne-Regular.ttf', package='google-fonts-titanone',
                size=4.0, min_scale=0.9, max_scale=2.1, puff_max_scale=3.7, tracking=0.06,
                zigzag_mm=.38, pull_mm=.1, split_satin=False),
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
    for name in ('satin_font.py', 'embroidery_fonts.py', 'monogram_ornaments.py'):
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
        # Split satin on wide strokes (big letters) gets the criss-cross base of wide columns.
        'zigzag_underlay': ('double' if width_mm >= 8.0 else 'true') if edge and width_mm > 3.5 else 'false',
    }


BASELINES = ('straight', 'arc_over', 'arc_under', 'circle', 'wave')
FRAMES = ('none', 'circle', 'oval', 'square', 'diamond', 'hexagon', 'shield', 'heart')
MONOGRAM_MIDDLE = 1.35   # classic monogram: the middle initial is this much bigger


def _frame_ring(kind, bounds, margin, radius):
    """A closed frame line around the letters' bounds (px), at least `margin` clear of them,
    with points about every 0.6 mm so the satin follows curves smoothly."""
    import numpy as np
    from shapely.geometry import Polygon, box
    from shapely import segmentize
    left, top, right, bottom = bounds
    cx, cy = (left+right)/2, (top+bottom)/2
    w, h = (right-left)/2+margin, (bottom-top)/2+margin   # half sizes of the clear box
    t = np.linspace(0, 2*math.pi, 240, endpoint=False)
    if kind == 'circle':
        r = math.hypot(w, h)
        shape = Polygon(np.c_[cx+r*np.cos(t), cy+r*np.sin(t)])
    elif kind == 'oval':
        shape = Polygon(np.c_[cx+w*math.sqrt(2)*np.cos(t), cy+h*math.sqrt(2)*np.sin(t)])
    elif kind == 'square':
        shape = box(cx-w, cy-h, cx+w, cy+h).buffer(min(w, h)*.25, join_style='round').buffer(-min(w, h)*.12)
    elif kind == 'diamond':
        shape = Polygon([(cx, cy-2*h), (cx+2*w, cy), (cx, cy+2*h), (cx-2*w, cy)])
    elif kind == 'hexagon':
        tall = h*1.3
        reach = w/(1-h/(2*tall))
        shape = Polygon([(cx-reach, cy), (cx-reach/2, cy-tall), (cx+reach/2, cy-tall),
                         (cx+reach, cy), (cx+reach/2, cy+tall), (cx-reach/2, cy+tall)])
    elif kind == 'shield':
        width, top_y, side_y, point_y = w*1.15, cy-h*1.2, cy+h*.35, cy+h*2.1
        # Sides curve in to a point at the bottom (the control point sits halfway down the side).
        curve = [((1-u)**2*width+2*(1-u)*u*width, (1-u)**2*side_y+2*(1-u)*u*(side_y+point_y)/2+u*u*point_y)
                 for u in np.linspace(0, 1, 40)]
        shape = Polygon([(cx-width, top_y), (cx+width, top_y)]+[(cx+x, y) for x, y in curve]
                        + [(cx-x, y) for x, y in curve[::-1]])
    elif kind == 'heart':
        x, y = 16*np.sin(t)**3, -(13*np.cos(t)-5*np.cos(2*t)-2*np.cos(3*t)-np.cos(4*t))
        k = max(w/10.5, h/7.5)
        shape = Polygon(np.c_[cx+k*x, cy+k*(y+1.5)])
        # Round the dip at the top: a satin cannot turn inside a cusp.
        shape = shape.buffer(4*radius).buffer(-4*radius)
    else:
        raise ValueError('Choose a listed frame.')
    # Round the corners a little: satin turns a rounded corner cleanly, a sharp one folds over.
    shape = shape.buffer(-2.5*radius).buffer(2.5*radius)
    shape = segmentize(shape.simplify(.1/PX_MM), .6/PX_MM)
    ring = [tuple(p) for p in shape.exterior.coords][:-1]
    return [p for i, p in enumerate(ring) if i == 0 or math.dist(p, ring[i-1]) > 1e-6]
SEQUENCES = ('left', 'centre')
# Joins: closest (each letter starts where its first stroke begins) or bottom (each letter starts
# at its baseline on the left, the thread running there under the letter's own stitches).
JOINS = ('closest', 'bottom')
# Envelopes: the words stretched to fill a shape, letters bending with it (elastic lettering).
ENVELOPES = ('none', 'arch_top', 'arch_bottom', 'bulge', 'pinch', 'bend_up', 'grow', 'shrink')


def _envelope_warp(kind, percent, bounds):
    """The bend of an envelope over the straight words' bounds (px): each point keeps its
    place along the line and moves up or down between the shape's new top and bottom edges,
    so letters grow, shrink and lean with it. `percent` is how far the edges move, as a share
    of the words' height. stretch(x) is how much taller the words are there."""
    import numpy as np
    left, top, right, bottom = bounds
    width, height = max(right-left, 1e-6), max(bottom-top, 1e-6)
    move = percent/100*height

    def edges(x):
        u = np.clip((np.asarray(x, float)-left)/width, 0, 1)
        bump = np.sin(np.pi*u)
        up, down = {'arch_top': (-bump, 0), 'arch_bottom': (0, bump), 'bulge': (-bump/2, bump/2),
                    'pinch': (bump/2, -bump/2), 'bend_up': (-bump, -bump),
                    'grow': ((1-u)/2, -(1-u)/2), 'shrink': (u/2, -u/2)}[kind]
        return top+move*up, bottom+move*down

    def warp(x, y):
        x, y = np.asarray(x, float), np.asarray(y, float)
        new_top, new_bottom = edges(x)
        return x, new_top+(y-top)/height*(new_bottom-new_top)

    def stretch(x):
        new_top, new_bottom = edges(x)
        return (new_bottom-new_top)/height
    warp.stretch = stretch
    return warp


def _bend_rails(a, b, warp, step):
    """Satin rails bent by an envelope: points added at most `step` apart first (matched
    pairs stay matched), so a straight stroke follows the curve."""
    import numpy as np

    def pieces(p, q, n):
        return [_lerp(p, q, k/n) for k in range(1, n+1)]
    if len(a) == len(b):
        fine_a, fine_b = [a[0]], [b[0]]
        for i in range(1, len(a)):
            n = max(1, math.ceil(max(math.dist(a[i-1], a[i]), math.dist(b[i-1], b[i]))/step))
            fine_a += pieces(a[i-1], a[i], n)
            fine_b += pieces(b[i-1], b[i], n)
    else:
        def fine(rail):
            return [rail[0]]+[p for i in range(1, len(rail))
                              for p in pieces(rail[i-1], rail[i], max(1, math.ceil(math.dist(rail[i-1], rail[i])/step)))]
        fine_a, fine_b = fine(a), fine(b)

    def bend(rail):
        x, y = warp(*np.array(rail, float).T)
        return [(float(p), float(q)) for p, q in zip(x, y)]
    return bend(fine_a), bend(fine_b)


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


def _circle_matrices(placed, widths, em_px, cap_px, radius_px):
    """Words round a whole circle (centre 0, 0): the first line over the top, reading
    clockwise with the letters standing outward; a second line along the bottom, reading
    left to right with the letters standing inward, its baseline a capital further out so
    both lines share one ring. Letters stay rigid, as on an arc."""
    out, sweeps = {}, []
    for (row, glyphs), width in zip(placed, widths):
        r = radius_px if row == 0 else radius_px+cap_px
        if width > .95*2*math.pi*r:
            raise ValueError('These words do not fit around this circle. Make the circle larger or use fewer letters.')
        sweeps.append(width/r)
        for index, (char, x, columns, advance) in enumerate(glyphs):
            anchor = x+advance*em_px/2
            theta = (anchor-width/2)/r
            if row == 0:
                ax, ay, turn = r*math.sin(theta), -r*math.cos(theta), theta
            else:
                ax, ay, turn = r*math.sin(theta), r*math.cos(theta), -theta
            c, s_ = math.cos(turn), math.sin(turn)
            dx = x-anchor
            out[row, index] = [c*em_px, -s_*em_px, s_*em_px, c*em_px, ax+c*dx, ay+s_*dx]
    # Top words centred on the top, bottom words on the bottom: a capital's gap where they would meet.
    if len(sweeps) == 2 and (sweeps[0]+sweeps[1])/2+cap_px/radius_px > math.pi:
        raise ValueError('The top and bottom words meet around this circle. Make the circle larger or the words shorter.')
    return out


def _wave_matrices(placed, widths, em_px, percent):
    """Words along one S-shaped wave (up, down and back to the line), letters rigid and
    turned to follow it. The wave rises `percent` of the words' length and is as long along
    the curve as the words, so it looks the same for any words."""
    import numpy as np
    (row, glyphs), width = placed[0], widths[0]
    rise, u = width*percent/100, np.linspace(0, 1, 801)
    curve = lambda span: np.concatenate([[0], np.cumsum(np.hypot(np.diff(span*u), np.diff(-rise*np.sin(2*np.pi*u))))])
    span = max(width, 1e-6)
    for _ in range(12):
        # Narrow the wave until its length along the curve is the words' length.
        span *= max(width, 1e-6)/curve(span)[-1]
    along = curve(span)
    out = {}
    for index, (char, x, columns, advance) in enumerate(glyphs):
        anchor = x+advance*em_px/2
        t = float(np.interp(anchor, along, u))
        ax, ay = span*t, -rise*math.sin(2*math.pi*t)
        turn = math.atan2(-rise*2*math.pi*math.cos(2*math.pi*t), span)
        c, s_ = math.cos(turn), math.sin(turn)
        dx = x-anchor
        out[row, index] = [c*em_px, -s_*em_px, s_*em_px, c*em_px, ax+c*dx, ay+s_*dx]
    return out


def _neighbour_gaps(placed, matrices, key):
    """Distance (px) and overlap (px²) of each pair of neighbouring letters in a line."""
    from shapely.affinity import affine_transform
    gaps = []
    for row, glyphs in placed:
        shapes = [affine_transform(glyph_columns(font_path(key), char)[2], matrices[row, index])
                  for index, (char, *_) in enumerate(glyphs) if char != ' ']
        for a, b in zip(shapes, shapes[1:]):
            gaps.append((a.distance(b), a.intersection(b).area))
    return gaps


def _crowded(before, after):
    """Whether squeezing or bending brings letters that were apart within 0.3 mm of each
    other (or closer than they were, if less), or makes letters that touched overlap by half
    as much again."""
    for (d0, area0), (d1, area1) in zip(before, after):
        if d0 > .05/PX_MM:
            if d1 < min(.3/PX_MM, d0)-.05/PX_MM:
                return True
        elif area1 > 1.5*area0+.1/PX_MM**2:
            return True
    return False


class LengthError(ValueError):
    """A fixed length the words cannot have; `nearest` is the closest length they can (mm)."""
    def __init__(self, message, nearest):
        super().__init__(message)
        self.nearest = nearest


def layout(text, key, scale_percent, align='left', colour='#000000', puff=False, foam_mm=3.0, fill=False,
           pull_mm=None, letter_spacing_mm=0.0, line_spacing=1.0, baseline='straight', radius_mm=None,
           sequence='left', arc_degrees=None, frame='none', frame_mm=2.5, classic=False, ornament='none',
           circle_mm=None, wave_percent=6.0, fit_length_mm=None, envelope='none', envelope_percent=30.0,
           join='closest'):
    """SVG of satin-column lettering; user units are CSS px (96 per inch).
    puff: letters over foam (see stitch_satin._puff_satin). Each letter has a
    placement line sewn before the stop for the foam, then a perforation line
    just inside it that tacks the foam down, then its columns. pull_mm replaces
    the font's own pull compensation (fabric preset). letter_spacing_mm is added
    between letters, line_spacing scales the line height; baseline/radius_mm bend
    a single line on an arc (arc_degrees instead of radius_mm: how far round the
    circle the words reach, so the curve looks the same for any length); sequence='centre' sews from the middle letter out
    (centre-out, for caps). Letters that touch are joined by travel
    inside both instead of a cut. ornament: a crown, laurel, swirls or divider
    (monogram_ornaments) around the words and frame, sewn last. baseline='circle': the
    words round a whole circle circle_mm across (a second line along the bottom);
    'wave': one S-shaped wave rising wave_percent of the words' length. fit_length_mm:
    one letter spacing chosen so the stitched line is exactly this long along its
    baseline (letter_spacing_mm is then not used). envelope: the words (every line) stretched
    to fill a shape, letters bending with it, its edges moving envelope_percent of the words'
    height (_envelope_warp). join='bottom': satin letters (not puff or fill) are entered at their
    baseline on the left (_bottom_entry); letters with fabric between them still cut."""
    if baseline not in BASELINES or sequence not in SEQUENCES:
        raise ValueError('Choose a listed baseline and letter order.')
    if join not in JOINS:
        raise ValueError('Choose closest or bottom joins.')
    if envelope not in ENVELOPES:
        raise ValueError('Choose a listed envelope.')
    if envelope != 'none':
        if baseline != 'straight':
            raise ValueError('An envelope shapes words on a straight line. Choose a straight line or no envelope.')
        if classic:
            raise ValueError('A classic monogram cannot have an envelope. Choose no envelope.')
        if not 10 <= float(envelope_percent) <= 50:
            raise ValueError('Choose an envelope strength from 10 to 50%.')
    if frame not in FRAMES:
        raise ValueError('Choose a listed frame.')
    if frame != 'none' and puff:
        raise ValueError('A frame cannot be 3D puff yet. Turn off 3D puff or choose no frame.')
    from .monogram_ornaments import ORNAMENTS
    if ornament not in ORNAMENTS:
        raise ValueError('Choose a listed ornament.')
    if ornament != 'none' and puff:
        raise ValueError('An ornament cannot be 3D puff yet. Turn off 3D puff or choose no ornament.')
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

    def set_lines(spacing_mm):
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
                    x += kerning(key, char, line[i+1])*em_px+spacing_mm/PX_MM
            widths.append(max(0.0, x-data['tracking']*em_px))
            placed.append((row, glyphs))
        return placed, widths

    baseline_of = lambda row: row*line_px+line_px*.8

    def straight(placed, widths):
        # Each letter's placement from font units (shapely affine order: a, b, d, e, xoff, yoff).
        widest = max(widths) if widths else 0.0
        return {(row, index): [em_px, 0, 0, em_px, (widest-width)*{'left': 0, 'center': .5, 'right': 1}[align]+x,
                               baseline_of(row)]
                for (row, glyphs), width in zip(placed, widths) for index, (_, x, *_) in enumerate(glyphs)}

    placed, widths = set_lines(letter_spacing_mm)
    if fit_length_mm is not None:
        # Fixed length: one spacing between every two characters, so the stitched line
        # (satin edge included) is exactly this long along its baseline.
        if len(lines) > 1:
            raise ValueError('Fixed length takes one line. Remove the line breaks or turn off fixed length.')
        if classic:
            raise ValueError('A classic monogram cannot have a fixed length. Turn off fixed length.')
        placed, widths = set_lines(0.0)
        letters = [(i, char, x) for i, (char, x, *_) in enumerate(placed[0][1]) if char != ' ']
        if len(letters) < 2:
            raise ValueError('Fixed length needs at least two letters.')
        bounds = lambda char: glyph_columns(font_path(key), char)[2].bounds
        (first, c0, x0), (last, c1, x1) = letters[0], letters[-1]
        edge = 0.0 if fill else float(puff_pull)-.05 if puff else pull_mm
        natural = (x1+bounds(c1)[2]*em_px-x0-bounds(c0)[0]*em_px)*PX_MM+2*edge
        gaps = last-first
        spacing = (float(fit_length_mm)-natural)/gaps
        if spacing > size_mm:
            longest = math.floor((natural+gaps*size_mm)*10)/10
            raise LengthError(f'Spreading these words to {float(fit_length_mm):g} mm leaves more than a letter\'s '
                              f'height between letters. The longest that still reads as words is about {longest:g} mm.',
                              longest)
        if spacing < 0:
            plain = _neighbour_gaps(placed, straight(placed, widths), key)
            fits = lambda s: not _crowded(plain, _neighbour_gaps(placed, straight(*set_lines(s)), key))
            if not fits(spacing):
                low, high = spacing, 0.0
                for _ in range(16):
                    middle = (low+high)/2
                    low, high = (low, middle) if fits(middle) else (middle, high)
                shortest = math.ceil((natural+gaps*high)*10)/10
                raise LengthError(f'Squeezing these words to {float(fit_length_mm):g} mm would make the letters '
                                  f'overlap. The shortest they can be is about {shortest:g} mm.', shortest)
        placed, widths = set_lines(spacing)
    widest = max(widths) if widths else 0.0
    matrices = straight(placed, widths)
    size = (widest+em_px, len(lines)*line_px+em_px)
    if classic:
        # Classic monogram: two or three initials, the middle one bigger, all centred on one line.
        letters = [index for index, g in enumerate(placed[0][1]) if g[0] != ' ']
        if len(lines) > 1 or baseline != 'straight' or not 2 <= len(letters) <= 3:
            raise ValueError('A classic monogram is two or three initials on one straight line.')
        middle = letters[1] if len(letters) == 3 else None
        x = 0.0
        for index in letters:
            char = placed[0][1][index][0]
            l, t, r, b = glyph_columns(font_path(key), char)[2].bounds
            scale_px = em_px*(MONOGRAM_MIDDLE if index == middle else 1)
            matrices[0, index] = [scale_px, 0, 0, scale_px, x-l*scale_px, -(t+b)/2*scale_px]
            x += (r-l)*scale_px+.12*em_px
    frame_columns, ornament_pieces = [], []
    if baseline == 'circle':
        if len(lines) > 2:
            raise ValueError('A full circle takes one line over the top and at most one along the bottom.')
        if not circle_mm or not 10 <= float(circle_mm) <= 500:
            raise ValueError('Enter a circle size from 10 to 500 mm.')
        matrices = _circle_matrices(placed, widths, em_px, size_mm/PX_MM, float(circle_mm)/2/PX_MM)
    elif baseline != 'straight' and len(lines) > 1:
        raise ValueError('Curved lettering takes one line. Remove the line breaks or use a straight baseline.')
    elif baseline == 'wave':
        if not 2 <= float(wave_percent) <= 25:
            raise ValueError('Choose a wave from 2 to 25%.')
        matrices = _wave_matrices(placed, widths, em_px, float(wave_percent))
    elif baseline != 'straight':
        if arc_degrees is not None:
            if not 10 <= float(arc_degrees) <= 300:
                raise ValueError('Choose a curve from 10 to 300 degrees.')
            radius_px = max(widest, em_px)/math.radians(float(arc_degrees))
        elif not radius_mm or not 5 <= float(radius_mm) <= 1000:
            raise ValueError('Enter an arc radius from 5 to 1000 mm.')
        else:
            radius_px = float(radius_mm)/PX_MM
        matrices = _arc_matrices(placed, widths, widest, em_px, baseline_of, align, baseline, radius_px)
    if baseline in ('circle', 'wave') and _crowded(_neighbour_gaps(placed, straight(placed, widths), key),
                                                   _neighbour_gaps(placed, matrices, key)):
        # Rigid letters on the inside of a tight bend come together at their tops (or feet).
        raise ValueError('The letters would touch around a circle this small. Make the circle larger.'
                         if baseline == 'circle' else
                         'The letters would touch on a wave this strong. Choose a gentler wave.')
    from shapely.affinity import affine_transform
    warp = None

    def page(shape, m):
        # A letter's outline as sewn: placed, then bent by the envelope.
        shape = affine_transform(shape, m)
        if warp is None:
            return shape
        import numpy as np
        from shapely import segmentize, transform
        return transform(segmentize(shape, .5/PX_MM), lambda xy: np.column_stack(warp(xy[:, 0], xy[:, 1])))
    if envelope != 'none':
        from shapely.ops import unary_union
        block = unary_union([affine_transform(glyph_columns(font_path(key), char)[2], matrices[row, index])
                             for row, glyphs in placed for index, (char, *_) in enumerate(glyphs) if char != ' '])
        if not block.is_empty:
            warp = _envelope_warp(envelope, float(envelope_percent), block.bounds)
    if baseline != 'straight' or classic or frame != 'none' or ornament != 'none' or warp is not None:
        # Keep the bent words (and the frame and ornament) on the page: measure them and move them in by half an em.
        from shapely.ops import unary_union
        outline = unary_union([page(glyph_columns(font_path(key), char)[2], matrices[row, index])
                               for row, glyphs in placed for index, (char, *_) in enumerate(glyphs) if char != ' '])
        if not outline.is_empty:
            left, top, right, bottom = outline.bounds
            if frame != 'none':
                # A satin frame around the letters, clear of them by about a third of a capital.
                from .borders import satin_rails
                radius = float(frame_mm)/2/PX_MM
                cap_px = cap_height(key)*em_px
                ring = _frame_ring(frame, outline.bounds, max(.35*cap_px, 1.5/PX_MM)+radius, radius)
                try:
                    frame_columns = satin_rails(ring+[ring[0]], radius)
                except ValueError:
                    raise ValueError('This frame does not fit at this size. Choose another frame, '
                                     'a thinner frame or bigger letters.') from None
                xs = [p[0] for a, b in frame_columns for p in (*a, *b)]
                ys = [p[1] for a, b in frame_columns for p in (*a, *b)]
                left, top = min(left, min(xs)), min(top, min(ys))
                right, bottom = max(right, max(xs)), max(bottom, max(ys))
            if ornament != 'none':
                # Around the words and frame, scaled to the capital, clear of both.
                from shapely.geometry import Polygon
                from .monogram_ornaments import ornament as ornament_columns
                avoid = unary_union([outline]+[Polygon(list(a)+list(b)[::-1]).buffer(0) for a, b in frame_columns])
                ornament_pieces = ornament_columns(ornament, (left, top, right, bottom), cap_height(key)*em_px, avoid)
                xs = [p[0] for piece in ornament_pieces for a, b in piece for p in (*a, *b)]
                ys = [p[1] for piece in ornament_pieces for a, b in piece for p in (*a, *b)]
                left, top = min(left, min(xs)), min(top, min(ys))
                right, bottom = max(right, max(xs)), max(bottom, max(ys))
            move = lambda rails: [(x+em_px/2-left, y+em_px/2-top) for x, y in rails]
            frame_columns = [(move(a), move(b)) for a, b in frame_columns]
            ornament_pieces = [[(move(a), move(b)) for a, b in piece] for piece in ornament_pieces]
            for m in matrices.values():
                m[4] += em_px/2-left
                m[5] += em_px/2-top
            if warp is not None:
                # The envelope was measured before the move: undo it, bend, redo it.
                import numpy as np
                bent, dx, dy = warp, em_px/2-left, em_px/2-top

                def warp(x, y, bent=bent):
                    x, y = bent(np.asarray(x, float)-dx, np.asarray(y, float)-dy)
                    return x+dx, y+dy
                warp.stretch = lambda x, bent=bent: bent.stretch(np.asarray(x, float)-dx)
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
                outline = page(glyph_columns(font_path(key), char)[2], m)
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
            rails = [([place(p) for p in a], [place(p) for p in b]) for a, b, *_ in columns]
            if warp is not None:
                rails = [_bend_rails(ra, rb, warp, .6/PX_MM) for ra, rb in rails]
            for (a, b, closed, width_em), (ra, rb) in zip(columns, rails):
                sewn_columns.append((ra, rb))
                width_mm = width_em*2*em_px*PX_MM
                if warp is not None:
                    # Bent strokes are as wide as the envelope makes them.
                    width_mm = (max(math.dist(p, q) for p, q in zip(ra, rb))*PX_MM if len(ra) == len(rb) else
                                width_mm*float(max(warp.stretch([p[0] for p in ra+rb]))))
                walk = width_mm >= .9
                start = _lerp(ra[0], rb[0], .5) if walk else _lerp(ra[0], rb[0], .3)
                if previous_end is not None:
                    # Move between strokes inside the letter, never across fabric.
                    if travel is None:
                        from .stitch_paths import Travel
                        # Inside the sewn columns, not the font outline: where two
                        # columns meet the outline has an unsewn wedge, and a travel
                        # across it is a thread over bare fabric.
                        from shapely.geometry import Polygon
                        from shapely.ops import unary_union
                        if warp is None:
                            shape = affine_transform(unary_union([Polygon(list(ca) + list(cb)[::-1]).buffer(0)
                                                                  for ca, cb, *_ in columns]), m)
                        else:
                            shape = unary_union([Polygon(list(ca) + list(cb)[::-1]).buffer(0) for ca, cb in rails])
                        travel = Travel(shape, inset=.15/PX_MM, slack=.05/PX_MM)
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
                    start = _lerp(first[0][0], first[1][0], .5)
                    if join == 'bottom':
                        # The letter's foot on the left, in its own frame (the letter may be turned or bent).
                        left = glyph_columns(font_path(key), char)[2].bounds[0]
                        foot = place((left, 0.0))
                        if warp is not None:
                            import numpy as np
                            foot = tuple(float(np.ravel(v)[0]) for v in warp(np.array([foot[0]]), np.array([foot[1]])))
                        route = _bottom_entry(sewn_columns, foot, start)
                        if route is not None:
                            count += 1
                            group.insert(0, ET.Element(f'{{{SVG_NS}}}path', {
                                'id': f'entry{count}', 'd': _path(route),
                                'style': f'fill:none;stroke:{colour};stroke-width:{.2/PX_MM:.3f}',
                                f'{{{INK_NS}}}stroke_method': 'running_stitch',
                                f'{{{INK_NS}}}running_stitch_length_mm': '1.2',
                                f'{{{INK_NS}}}running_stitch_tolerance_mm': '0'}))
                            start = route[0]
                    sewn_letters.append(dict(group=group, last=nodes[-1], end=previous_end,
                                             start=start, columns=sewn_columns))
        _join_touching(sewn_letters, colour)
    if frame_columns:
        # The frame is sewn last, around the letters, as satin halves that meet at both ends.
        group = ET.SubElement(root, f'{{{SVG_NS}}}g', {f'{{{INK_NS}}}letter-group': 'line',
                                                       f'{{{LABEL_NS}}}label': 'frame'})
        nodes = []
        for a, b in frame_columns:
            count += 1
            nodes.append(ET.SubElement(group, f'{{{SVG_NS}}}path', {
                'id': f'frame{count}', 'd': ' '.join([_path([tuple(p) for p in a]), _path([tuple(p) for p in b])]),
                'style': f'fill:none;stroke:{colour};stroke-width:{.2/PX_MM:.3f}',
                f'{{{INK_NS}}}satin_column': 'true', f'{{{INK_NS}}}satin_pairs': 'indexed',
                f'{{{INK_NS}}}pull_compensation_mm': f'{pull_mm:g}',
                **{f'{{{INK_NS}}}{name}': value
                   for name, value in size_profile(size_mm, float(frame_mm), data['zigzag_mm']).items()}}))
        nodes[-1].set(f'{{{INK_NS}}}trim_after', 'true')
    if ornament_pieces:
        _ornament_group(root, ornament_pieces, colour, pull_mm, size_mm, data['zigzag_mm'], count)
    return ET.tostring(root, encoding='unicode')


def _ornament_group(root, pieces, colour, pull_mm, size_mm, zigzag_mm, count):
    """The ornament, sewn after the words and frame: each piece's columns in order, the
    needle moved between them inside the piece (as inside a letter), a cut after each piece."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from .stitch_paths import Travel
    group = ET.SubElement(root, f'{{{SVG_NS}}}g', {f'{{{INK_NS}}}letter-group': 'line',
                                                   f'{{{LABEL_NS}}}label': 'ornament'})
    style = f'fill:none;stroke:{colour};stroke-width:{.2/PX_MM:.3f}'
    for piece in pieces:
        travel = Travel(unary_union([Polygon(list(a)+list(b)[::-1]).buffer(0) for a, b in piece]),
                        inset=.15/PX_MM, slack=.05/PX_MM)
        nodes, previous_end = [], None
        for a, b in piece:
            width_mm = max(math.dist(p, q) for p, q in zip(a, b))*PX_MM
            start = _lerp(a[0], b[0], .5)
            if previous_end is not None:
                route = travel.route(previous_end, start, direct_mm=math.inf)
                if route is None:
                    nodes[-1].set(f'{{{INK_NS}}}trim_after', 'true')
                else:
                    count += 1
                    nodes.append(ET.SubElement(group, f'{{{SVG_NS}}}path', {
                        'id': f'ornament-travel{count}', 'd': _path(route), 'style': style,
                        f'{{{INK_NS}}}stroke_method': 'running_stitch',
                        f'{{{INK_NS}}}running_stitch_length_mm': '1.2',
                        f'{{{INK_NS}}}running_stitch_tolerance_mm': '0'}))
            profile = size_profile(size_mm, width_mm, zigzag_mm)
            # Zigzag underlay runs to the far end, so the satin then comes back to the start.
            previous_end = _lerp(b[0], a[0], .3) if profile['zigzag_underlay'] != 'false' else _lerp(b[-1], a[-1], .3)
            count += 1
            nodes.append(ET.SubElement(group, f'{{{SVG_NS}}}path', {
                'id': f'ornament{count}', 'd': ' '.join([_path(a), _path(b)]), 'style': style,
                f'{{{INK_NS}}}satin_column': 'true', f'{{{INK_NS}}}satin_pairs': 'indexed',
                f'{{{INK_NS}}}pull_compensation_mm': f'{pull_mm:g}',
                **{f'{{{INK_NS}}}{name}': value for name, value in profile.items()}}))
        nodes[-1].set(f'{{{INK_NS}}}trim_after', 'true')


def _bottom_entry(columns, foot, start):
    """Bottom join: a run from the letter's sewn area nearest its foot (baseline, left edge) to
    where its first stroke starts, inside the letter, sewn before the strokes so they cover it.
    The thread then arrives (and ties in) at the baseline. None when the first stroke already
    starts there. Never over bare fabric: the run stays 0.15 mm inside the sewn columns."""
    from shapely.geometry import Point, Polygon
    from shapely.ops import nearest_points, unary_union
    from .stitch_paths import Travel
    shape = unary_union([Polygon(list(a)+list(b)[::-1]).buffer(0) for a, b in columns])
    inner = shape.buffer(-.2/PX_MM)
    if inner.is_empty:
        return None
    entry = nearest_points(inner, Point(foot))[0]
    entry = (entry.x, entry.y)
    if math.dist(entry, start)*PX_MM < 1.0:
        return None
    route = Travel(shape, inset=.15/PX_MM, slack=.05/PX_MM).route(entry, start, direct_mm=math.inf)
    return [tuple(p) for p in route] if route else None


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
