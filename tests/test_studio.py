from pathlib import Path
from PIL import Image
from embroiderly.web import create_app

def test_studio_has_integrated_controls(tmp_path):
    client=create_app(tmp_path).test_client()
    Image.new("RGB",(20,20),"red").save(tmp_path/"work/uploads/studio.png")
    page=client.get("/artwork/studio.png")
    assert page.status_code==200
    for control in (b'id="run"',b'id="timeline"',b'data-view="stitched"',b'id="exportPes"',b'id="confirmed"'):
        assert control in page.data
    assert b'/artwork/studio.png' in client.get('/designs').data

def test_export_is_limited_to_generated_formats(tmp_path):
    client=create_app(tmp_path).test_client()
    folder=tmp_path/"work/inkstitch-preview/studio";folder.mkdir(parents=True)
    (folder/"design.pes").write_bytes(b"test-pes")
    assert client.get("/studio-export/studio.png/pes").status_code==404
    (folder/"playback.json").write_text("{}")
    response=client.get("/studio-export/studio.png/pes")
    assert response.status_code==422  # A preview is not permission to release bytes.
    assert 'blocked' in response.json['error'].lower()
    assert client.get("/studio-export/studio.png/json").status_code==404
    assert client.get("/studio-export/missing.png/dst").status_code==404
