import json
import numpy as np
import pyembroidery as emb
from embroiderly.web import create_app
from embroiderly.machine_files import write_pair


def test_download_rejects_unverified_files(tmp_path):
    client=create_app(tmp_path).test_client()
    folder=tmp_path/'work/inkstitch-preview/unsafe';folder.mkdir(parents=True)
    (folder/'playback.json').write_text('{}')
    (folder/'design.pes').write_bytes(b'not a machine file')
    response=client.get('/studio-export/unsafe.png/pes')
    assert response.status_code==422
    assert 'blocked' in response.json['error'].lower()
