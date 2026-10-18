"""Extra machine formats are converted from the checked PES and re-checked."""
import pyembroidery as emb
import pytest
from PIL import Image, ImageDraw
from embroiderly.engine import digitize
from embroiderly.release_gate import FORMATS, ReleaseError, converted_bytes
from embroiderly.web import create_app


@pytest.fixture(scope='module')
def design(tmp_path_factory):
    folder = tmp_path_factory.mktemp('formats')
    path = folder/'art.png'
    image = Image.new('RGB', (240, 160), 'white')
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 100, 140), fill=(200, 30, 40)); draw.ellipse((130, 30, 220, 130), fill=(20, 60, 160))
    image.save(path)
    digitize(path, folder/'out', 30)
    return folder/'out'


@pytest.mark.parametrize('fmt', sorted(FORMATS))
def test_every_offered_format_passes_its_own_readback(design, fmt, tmp_path):
    data = converted_bytes(design, fmt)
    target = tmp_path/('design.'+fmt); target.write_bytes(data)
    pattern = emb.EmbPattern(str(target), settings={'trims': True} if fmt == 'jef' else None)
    assert pattern.count_stitch_commands(emb.STITCH) > 100


def test_unknown_format_is_refused(design):
    with pytest.raises(ReleaseError):
        converted_bytes(design, 'vp3')


def test_studio_route_offers_converted_formats(tmp_path):
    client = create_app(tmp_path).test_client()
    assert client.get('/studio-export/x.png/jef').status_code == 404   # no stitches yet
    assert client.get('/studio-export/x.png/zip').status_code == 404
