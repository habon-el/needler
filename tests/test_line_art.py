"""Light line art on a dark background becomes continuous running-stitch routes."""
import numpy as np
from PIL import Image, ImageDraw
from embroiderly.engine import digitize
from embroiderly.line_art import Network, colour_layers, digitize_lines, routes
from embroiderly.preparation import prepare
from embroiderly.release_gate import checked_bytes


def drawing(path):
    image = Image.new('RGB', (300, 300), (5, 5, 5))
    d = ImageDraw.Draw(image)
    d.line((40, 40, 260, 40), fill=(235, 235, 230), width=2)
    d.line((150, 40, 150, 260), fill=(235, 235, 230), width=2)     # T shape: one network
    d.ellipse((60, 150, 120, 210), outline=(200, 40, 40), width=2)  # red ring
    d.line((200, 200, 260, 260), fill=(200, 40, 40), width=2)
    image.save(path)


def test_colours_are_split_by_hue_and_background_ignored():
    image = np.zeros((40, 40, 3), np.uint8)
    image[5:7, 5:35] = (230, 230, 225); image[20:22, 5:35] = (190, 40, 40)
    image[21, 5:35] = (90, 25, 25)   # dim antialiased edge of the red stroke
    layers = colour_layers(image)
    assert len(layers) == 2
    red = next(mask for tone, mask in layers if int(tone[1:3], 16) > 2*int(tone[3:5], 16))
    assert red[21, 10] and not red[5, 10]


def test_tree_is_sewn_in_one_route_with_short_retrace():
    net = Network()
    a, b, c, d = (net.node(p) for p in ((0, 0), (10, 0), (20, 0), (10, 10)))
    net.add(a, b, [(0, 0), (10, 0)]); net.add(b, c, [(10, 0), (20, 0)]); net.add(b, d, [(10, 0), (10, 10)])
    paths = routes(net, retrace_limit=15)
    assert len(paths) == 1
    length = sum(np.hypot(*np.subtract(q, p)) for p, q in zip(paths[0], paths[0][1:]))
    assert length == 40   # 30 mm of line, one 10 mm branch sewn twice


def test_long_retrace_becomes_a_cut_instead():
    net = Network()
    a, b, c, d = (net.node(p) for p in ((0, 0), (10, 0), (20, 0), (10, 10)))
    net.add(a, b, [(0, 0), (10, 0)]); net.add(b, c, [(10, 0), (20, 0)]); net.add(b, d, [(10, 0), (10, 10)])
    assert len(routes(net, retrace_limit=5)) == 2


def test_line_art_mode_digitizes_and_passes_release_gate(tmp_path):
    source = tmp_path/'art.png'; drawing(source)
    image, palette, report = prepare(source, {'line_art': True, 'height_mm': 60})
    assert report['line_art'] and not report['generation_blockers'] and len(palette) == 2
    alpha = np.asarray(image)[:, :, 3]
    assert alpha[5, 5] == 0                       # black background not stitched
    prepared = tmp_path/'prepared.png'; image.save(prepared)
    prepared.with_suffix('.prep.json').write_text('{"options": {"line_art": true}, "report": {}}')
    payload = digitize(prepared, tmp_path/'out', 60)
    assert payload['trim_count'] <= 4 and payload['stitch_count'] > 50
    assert checked_bytes(tmp_path/'out', 'dst')
