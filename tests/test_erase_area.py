"""Outlined erasure must remove only the explicitly bounded image pixels."""
import base64
import io
import cv2
import numpy as np
import pytest
from PIL import Image
from embroiderly.preparation import prepare
from embroiderly.web import create_app


@pytest.mark.parametrize('outline', [
    [[10, 10], [30, 10], [30, 30], [10, 30]],
    [[5, 5], [45, 5], [45, 15], [15, 15], [15, 45], [5, 45]],
])
def test_polygon_erasure_is_exact_and_does_not_change_other_pixels(tmp_path, outline):
    path = tmp_path / 'source.png'
    Image.new('RGBA', (60, 60), '#f0c080').save(path)
    settings = {'count': 2, 'smooth': 0, 'floor_mm2': 0, 'mask_holes_mm2': 25}
    original = path.read_bytes()
    before, _, _ = prepare(path, settings)
    after, _, _ = prepare(path, {**settings, 'edits': [
        {'kind': 'erase', 'shape': 'polygon', 'points': outline, 'radius': 1}
    ]})
    expected = np.zeros((60, 60), dtype=np.uint8)
    cv2.fillPoly(expected, [np.array(outline, dtype=np.int32)], 1)
    before_pixels, after_pixels = np.asarray(before), np.asarray(after)
    assert np.array_equal(after_pixels[:, :, 3] == 0, expected > 0)
    assert np.array_equal(after_pixels[expected == 0], before_pixels[expected == 0])
    assert path.read_bytes() == original
    restored, _, _ = prepare(path, settings)
    assert restored.tobytes() == before.tobytes()


@pytest.mark.parametrize('shape,pts', [('polygon', [[10,10],[30,10],[30,30],[10,30]]), ('brush', [[20,20],[25,25]])])
def test_subject_and_plan_previews_share_erase_boundary(tmp_path, shape, pts):
    client=create_app(tmp_path).test_client()
    source=tmp_path/'work/uploads/subject.png'
    Image.new('RGBA', (60,60), '#f0c080').save(source)
    response=client.post('/artwork/subject.png',json={'options': {
        'count':2,'smooth':0,'floor_mm2':0,'edits':[
            {'kind':'erase','shape':shape,'points':pts,'radius':3}
        ]
    }})
    assert response.status_code==200
    def alpha(key):
        payload=response.json[key].split(',',1)[1]
        return np.array(Image.open(io.BytesIO(base64.b64decode(payload))).getchannel('A'))
    assert np.array_equal(alpha('image'), alpha('isolated'))
    assert alpha('isolated')[20,20]==0
    assert alpha('isolated')[40,40]==255


@pytest.mark.parametrize('outline', [[], [[10, 10]], [[10, 10], [20, 20]], [[-1, 0], [2, 0], [2, 2]]])
def test_invalid_erase_polygon_rejected(tmp_path, outline):
    path = tmp_path / 'source.png'
    Image.new('RGB', (60, 60), 'red').save(path)
    with pytest.raises(ValueError):
        prepare(path, {'edits': [{'kind': 'erase', 'shape': 'polygon', 'points': outline}]})
