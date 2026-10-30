"""Export proof: the written DST and PES read back from disk and measured against the design.

Found testing a flaming basketball (Oct 2026): the file check refused 5 stitches over
empty fabric. A faithful copy (orange ball with black seams, three flames with black
outlines, white background left out) failed the same way, earlier, in the colour-removal
routing: the black outline round the flames is one long thin satin area, and the column
tracer works on a raster of a fixed size, so on that 70 mm outline one raster pixel is
0.2 mm and a column ended that far outside the outline in a flame's V-shaped valley.
"""
import math
from pathlib import Path

import numpy as np
import pyembroidery as emb
from PIL import Image, ImageChops, ImageDraw, ImageFilter
from shapely.geometry import LineString, Point

from embroiderly.auto_digitize import size_differs
from embroiderly.export_proof import proof
from embroiderly.machine_files import write_pair
from embroiderly.satin_font import area_columns
from embroiderly.stitch_engine import _satin_area


def saw_outline(width=70, teeth=5, depth=15, line=.8):
    """The black outline round flames: a band `line` mm wide along a saw-toothed top."""
    points = [(0, 0)]
    for i in range(teeth):
        points += [((i+.5)*width/teeth, -depth), ((i+1)*width/teeth, 0)]
    points += [(width, 20), (0, 20), (0, 0)]
    return LineString(points).buffer(line/2, join_style='mitre', mitre_limit=10)


def test_satin_on_a_long_thin_outline_stays_inside_it():
    shape = saw_outline()
    # The tracer's columns reach past the outline in the valleys (one coarse raster pixel)...
    assert max(shape.distance(Point(p)) for a, b, *_ in area_columns(shape) for p in list(a)+list(b)) > .15
    # ...the stitches no longer do: within the 0.1 mm the file grid and the check allow.
    runs = _satin_area(shape, .4, 0, .45)
    assert runs and max(shape.distance(Point(p)) for run in runs for p in run) <= .1


SVG = ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
       'xmlns:inkstitch="http://inkstitch.org/namespace" width="20mm" height="20mm" viewBox="0 0 20 20">'
       '<path id="area0" d="M 0,0 L 10,0 L 10,10 L 0,10 Z" style="fill:#ff0000;fill-rule:evenodd;stroke:none" '
       'inkstitch:fill_method="auto_fill" inkstitch:row_spacing_mm="0.4" />'
       '<defs><symbol id="inkstitch_origin" /></defs><use xlink:href="#inkstitch_origin" x="5" y="5" /></svg>')


def write(folder, skip=()):
    """A 10 mm red square sewn as rows 0.4 mm apart (tenths of a millimetre), some left out."""
    pattern = emb.EmbPattern()
    pattern.add_thread('#ff0000')
    stitches = [[-50, -48, emb.JUMP]]
    for k, y in enumerate(range(-48, 49, 4)):
        if k in skip:
            continue
        xs = range(-50, 51, 25) if k % 2 == 0 else range(50, -51, -25)
        stitches += [[x, y, emb.STITCH] for x in xs]
    pattern.stitches = stitches+[[stitches[-1][0], stitches[-1][1], emb.END]]
    (folder/'design.svg').write_text(SVG, encoding='utf-8')
    write_pair(pattern, folder/'design.pes', folder/'design.dst', {'version': 6})
    return folder


def test_rows_sewn_as_asked_read_back_from_both_files(tmp_path):
    result = proof(write(tmp_path), np.ones((200, 200), bool), .1, [10, 10], canvas_mm=(10, 10))
    assert {f: (r['width_mm'], r['height_mm'], r['crossings']) for f, r in result['files'].items()} == \
        {'pes': (10.0, 9.6, 0), 'dst': (10.0, 9.6, 0)}
    assert result['drawn_mm'] == [10.0, 10.0]
    rows = result['rows']
    assert len(rows) == 1 and rows[0]['asked_mm'] == rows[0]['measured_mm'] == .4 and rows[0]['gaps'] == 0
    assert result['coverage']['bare_count'] == 0
    assert result['notes'] == []


def test_missing_rows_show_as_a_space_and_bare_fabric(tmp_path):
    result = proof(write(tmp_path, skip=(12, 13)), canvas_mm=(10, 10))
    row = result['rows'][0]
    # Rows at y 0 and 0.4 left out: the rows beside them are 1.2 mm apart, about y 0.2.
    assert row['gaps'] == 1 and row['widest_mm'] == 1.2 and abs(row['y_mm']-.2) < .05
    assert result['coverage']['bare_count'] == 1 and abs(result['coverage']['bare'][0]['y_mm']-.2) < .15
    assert any('bare part' in n for n in result['notes']) and any('Fill rows with spaces' in n for n in result['notes'])


def test_sewn_size_differs_from_the_canvas(tmp_path):
    notes = proof(write(tmp_path), canvas_mm=(20, 20))['notes']
    assert notes == ['Sewn size 10 × 9.6 mm: the canvas you set is 20 mm high with empty margins. '
                     'For a design 20 mm high, set the canvas to 41.7 mm.']


def test_the_size_asked_for_is_compared_with_the_files():
    result = dict(width_mm=76.2, height_mm=88.0)
    assert size_differs({'width_mm': 80}, result) == ['You asked for 80 mm wide; the files sew 76.2 mm wide.']
    assert size_differs({'height_mm': 88.5}, result) == []
    assert size_differs({}, result) == []


def basketball(path, size=768):
    """Orange ball with black seams under three flames, black outlines, white background."""
    s = size/600

    def flame(cx, base, w, h, tongues, phase=0.0):
        top = [(cx-w/2+w*i/120, base-h*math.sin(math.pi*i/120)**.8*(.55+.45*abs(math.cos(math.pi*tongues*i/120+phase))))
               for i in range(121)]
        return [(x*s, y*s) for x, y in top+[(cx+w/2, base+20), (cx-w/2, base+20)]]
    image = Image.new('RGB', (size, size), 'white')
    draw = ImageDraw.Draw(image)
    draw.polygon(flame(300, 300, 440, 270, 3), fill='#d62718', outline='black', width=int(5*s))
    draw.polygon(flame(300, 305, 330, 200, 2, .6), fill='#f39c12', outline='black', width=int(4*s))
    draw.polygon(flame(300, 310, 190, 130, 1, 1.4), fill='#ffd31a', outline='black', width=int(4*s))
    c, r, line = (300*s, 400*s), 170*s, int(6*s)
    draw.ellipse([c[0]-r, c[1]-r, c[0]+r, c[1]+r], fill='#e8731c', outline='black', width=int(7*s))
    seams = Image.new('L', image.size, 0)
    lines = ImageDraw.Draw(seams)
    lines.line([c[0], c[1]-r, c[0], c[1]+r], fill=255, width=line)
    lines.line([c[0]-r, c[1], c[0]+r, c[1]], fill=255, width=line)
    for side in (-1, 1):
        x, rr = c[0]+side*r*1.3, r*.95
        lines.ellipse([x-rr, c[1]-rr, x+rr, c[1]+rr], outline=255, width=line)
    ball = Image.new('L', image.size, 0)
    ImageDraw.Draw(ball).ellipse([c[0]-r, c[1]-r, c[0]+r, c[1]+r], fill=255)
    image.paste((0, 0, 0), mask=ImageChops.multiply(seams, ball))
    # Drawing leaves single pixels of a colour inside the outlines; a picture would not.
    image.filter(ImageFilter.ModeFilter(3)).save(path)


def test_the_flaming_basketball_with_its_background_left_out_passes_the_file_check(tmp_path):
    from embroiderly.auto_digitize import AutoDigitizer, classify, plan
    from embroiderly.colour_knockout import proposal_patch
    from embroiderly.release_gate import checked_bytes
    from embroiderly.web import create_app
    (tmp_path/'work/uploads').mkdir(parents=True)
    path = tmp_path/'work/uploads/ball.png'
    basketball(path)
    digitizer = AutoDigitizer(create_app(tmp_path), tmp_path)
    with Image.open(path) as image:
        kind, facts = classify(image)
        options = {**plan('logo', facts, {}, image.size, {}), 'count': 5, 'height_mm': 100}
        # The white background is left out by removing its colour (the colour-removal routing).
        options.update(proposal_patch(image, options))
    assert options.get('colour_knockouts')
    result, _ = digitizer._attempt(path, options, keep_playback=True)
    assert not result.get('error'), result.get('error')
    folder = tmp_path/'work/inkstitch-preview'/Path(result['prepared']).stem
    assert checked_bytes(folder, 'dst')
    made = result['playback']['export_proof']
    assert made['files']['dst']['crossings'] == made['files']['pes']['crossings'] == 0
    assert (result['width_mm'], result['height_mm']) == (made['width_mm'], made['height_mm'])
    # The ball and flames fill 86 mm of the 100 mm canvas: said, with the canvas for 100 mm.
    assert 80 < made['height_mm'] < 92 and any('set the canvas to' in n for n in made['notes'])
    assert all(r['gaps'] == 0 for r in made['rows']) and made['rows']
