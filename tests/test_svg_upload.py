"""SVG logos are rendered by our own geometry reader; unsafe XML is refused."""
import io
import numpy as np
from PIL import Image
from embroiderly.vector_raster import render
from embroiderly.web import create_app

LOGO = b'''<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="50mm" viewBox="0 0 200 100">
<rect x="10" y="10" width="80" height="80" fill="#cc2233"/>
<circle cx="150" cy="50" r="35" fill="none" stroke="#2244aa" stroke-width="8"/></svg>'''


def test_fill_and_stroke_render_with_transparent_background():
    image = render(LOGO, width=400)
    assert image.size == (400, 200)
    pixels = np.asarray(image)
    assert pixels[0, 0, 3] == 0
    assert tuple(pixels[100, 100, :3]) == (0xcc, 0x22, 0x33)
    assert tuple(pixels[100, 300-70, :3]) == (0x22, 0x44, 0xaa)   # ring stroke
    assert pixels[100, 300, 3] == 0                              # ring centre is empty


def test_upload_converts_svg_and_rejects_entities(tmp_path):
    client = create_app(tmp_path).test_client()
    response = client.post('/upload', data={'image': (io.BytesIO(LOGO), 'logo.svg')})
    assert response.status_code == 302
    name = response.location.rstrip('/').split('/')[-1]
    assert name.endswith('.png') and (tmp_path/'work/uploads'/name).is_file()
    bomb = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><svg xmlns="http://www.w3.org/2000/svg"/>'
    assert client.post('/upload', data={'image': (io.BytesIO(bomb), 'bad.svg')}).status_code == 400
    empty = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><text>Hi</text></svg>'
    assert client.post('/upload', data={'image': (io.BytesIO(empty), 'text.svg')}).status_code == 400
