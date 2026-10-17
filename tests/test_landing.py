import json
from pathlib import Path
from PIL import Image
from embroiderly.web import create_app


def test_landing_is_public_content_not_customer_library(tmp_path):
    app = create_app(tmp_path)
    Image.new('RGB', (20, 20), 'red').save(tmp_path/'work/uploads/private-customer.png')
    with app.test_client() as client:
        page = client.get('/')
        assert page.status_code == 200
        assert b'Your ideas.' in page.data
        assert b'private-customer' not in page.data
        assert b'/designs#newDesign' in page.data
        assert b'AI-generated concept' in page.data
        library = client.get('/designs')
        assert library.status_code == 200 and b'id="newDesign"' in library.data
        assert b'id="designGrid"' in library.data


def test_old_library_bookmarks_keep_query(tmp_path):
    client = create_app(tmp_path).test_client()
    response = client.get('/?view=trash&sort=name&q=bird')
    assert response.status_code == 302
    assert response.location == '/designs?view=trash&sort=name&q=bird'


def test_landing_assets_and_demo_are_bounded_and_local(tmp_path):
    client = create_app(tmp_path).test_client()
    for path in ('landing.css', 'landing.js', 'landing/cap-concept.webp',
                 'landing/machine-concept.webp', 'landing/hello.png', 'landing/hello-plan.json'):
        response = client.get('/static/'+path)
        assert response.status_code == 200
        assert len(response.data) < 200_000
    plan = client.get('/static/landing/hello-plan.json').get_json()
    assert plan['stitch_count'] == sum(s['t']=='stitch' for s in plan['steps'])
    assert len(plan['colors']) == 1
    assert plan['stitch_count'] > 100
    assert plan['canvas_px'] == [640,240]
    script = client.get('/static/landing.js').data
    assert b'/upload' not in script and b'method:' not in script


def test_landing_sample_matches_actual_pes_readback():
    import pyembroidery as emb
    root = Path(__file__).resolve().parents[1]
    path = root/'work/landing-sample/design.pes'
    if not path.exists():
        import pytest
        pytest.skip('Run tests/build_landing_sample.py to verify the local generated export')
    plan = json.loads((root/'src/embroiderly/static/landing/hello-plan.json').read_text())
    pattern = emb.EmbPattern(str(path))
    assert len(pattern.stitches) == len(plan['steps'])
    for command, step in zip(pattern.stitches, plan['steps']):
        assert command[:2] == [step['x']*10, step['y']*10]
