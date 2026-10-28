import io
import numpy as np
import pytest
from PIL import Image
from embroiderly.product_mockup import PRODUCTS, products, render_product
from embroiderly.web import create_app
from test_thread_surface import write_fixture


def square(path, side):
    # A filled red square, side mm, centred on the origin.
    write_fixture(path, [((-side/2, y), (side/2, y)) for y in np.linspace(-side/2, side/2, int(side*2))], '#d01010')
    return path


def red_width(image):
    pixels = np.asarray(image.convert('RGB')).astype(int)
    red = (pixels[..., 0] > 150) & (pixels[..., 1] < 90) & (pixels[..., 2] < 90)
    columns = np.flatnonzero(red.any(0))
    return columns[-1] - columns[0] + 1, red


def test_design_is_shown_at_real_size_in_the_chosen_spot(tmp_path):
    path = square(tmp_path/'square.pes', 80)
    item = PRODUCTS['tshirt']
    image, note = render_product(path, 'tshirt', 'left_chest', '#1f3a5f', width=840, height=760)
    assert note is None and image.size == (840, 760)
    ppm = min(840/item['size'][0], 760/item['size'][1]) * .94
    width, red = red_width(image)
    assert abs(width - 80*ppm) <= 3
    # Centred on the left chest (the viewer's right half), not the middle.
    ys, xs = np.nonzero(red)
    origin_x = (840 - item['size'][0]*ppm) / 2
    assert abs(xs.mean() - (origin_x + 530*ppm)) <= 3
    # Product colour fills the shirt around the design.
    assert tuple(np.asarray(image)[int(ys.mean()) + 60, int(xs.mean())]) == (31, 58, 95)


def test_too_big_for_the_spot_gives_a_note_and_bad_choices_are_refused(tmp_path):
    path = square(tmp_path/'square.pes', 80)
    assert '80 × 80 mm' in render_product(path, 'cap', 'front', '#d9d4c7', width=320, height=220)[1]
    with pytest.raises(ValueError, match='product'):
        render_product(path, 'boat', 'front', '#ffffff')
    with pytest.raises(ValueError, match='placement'):
        render_product(path, 'cap', 'left_chest', '#ffffff')
    with pytest.raises(ValueError):
        render_product(path, 'cap', 'front', 'navy')


def test_every_product_renders_and_the_menu_lists_its_placements(tmp_path):
    path = square(tmp_path/'square.pes', 30)
    menu = products()
    assert [p['id'] for p in menu] == list(PRODUCTS)
    for product in menu:
        for placement in product['placements']:
            image, note = render_product(path, product['id'], placement['id'], '#ffffff', width=200, height=200)
            assert note is None and red_width(image)[0] > 0


def test_mockup_route_puts_the_design_on_a_product(tmp_path):
    app = create_app(tmp_path); client = app.test_client()
    target = tmp_path/'work/inkstitch-preview/example'; target.mkdir(parents=True)
    square(target/'design.pes', 120); (target/'playback.json').write_text('{}')
    assert {p['id'] for p in client.get('/api/products').get_json()['products']} == set(PRODUCTS)
    out = client.get('/thread-mockup/example.png?width=300&height=240&product=tshirt&placement=left_chest&fabric=%23ffffff')
    assert out.status_code == 200 and '120 × 120 mm' in out.headers['X-Mockup-Note']
    assert Image.open(io.BytesIO(out.data)).size == (300, 240)
    assert client.get('/thread-mockup/example.png?product=tshirt&placement=front').status_code == 400
    assert 'X-Mockup-Note' not in client.get('/thread-mockup/example.png?width=120&height=100').headers
