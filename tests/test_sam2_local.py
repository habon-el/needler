import base64

import numpy as np

from embroiderly import sam2_local as local, subject_model


def test_local_runtime_detection_and_explicit_disable(tmp_path, monkeypatch):
    monkeypatch.setattr(local, 'RUNTIME', tmp_path)
    monkeypatch.setenv('EMBROIDERLY_SAM2_LOCAL', '1')
    assert not local.available()
    (tmp_path/'venv/bin').mkdir(parents=True)
    (tmp_path/'venv/bin/python').touch()
    (tmp_path/'sam2.1_hiera_tiny.pt').touch()
    assert local.available()
    monkeypatch.setenv('EMBROIDERLY_SAM2_LOCAL', '0')
    assert not local.available()


def test_predictor_uses_isolated_runtime_without_importing_torch(monkeypatch):
    monkeypatch.delenv('EMBROIDERLY_SAM2_CHECKPOINT', raising=False)
    monkeypatch.delenv('EMBROIDERLY_SAM2_CONFIG', raising=False)
    monkeypatch.setattr(local, 'available', lambda: True)
    assert isinstance(subject_model._predictor(), local.Predictor)


def test_proxy_round_trip_and_reencode_after_worker_restart(monkeypatch):
    calls = []
    expected = np.array([[[True, False], [False, True]]])
    def request(data):
        calls.append(data)
        if data['op']=='encode': return {'ready':True}
        return dict(shape=list(expected.shape), scores=[.9],
                    masks=base64.b64encode(np.packbits(expected).tobytes()).decode())
    monkeypatch.setattr(local, 'request', request)
    proxy = local.Predictor()
    proxy.set_image(np.zeros((2,2,3), np.uint8))
    mask, score, _ = proxy.predict(point_coords=np.array([[1,1]]), point_labels=np.array([1]), box=None)
    assert np.array_equal(mask,expected) and score.tolist()==[.9]
    assert [c['op'] for c in calls]==['encode','encode','predict']
    assert calls[0]['key']==calls[1]['key']==calls[2]['key']
    assert calls[2]['args']['point_coords']==[[1,1]]


def test_worker_receives_no_key_or_app_pythonpath(monkeypatch):
    local.close()  # Test launch even if an earlier integration check warmed a worker.
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-secret-never-forward')
    monkeypatch.setenv('PYTHONPATH', 'synthetic-app-library-path')
    monkeypatch.setattr(local, 'available', lambda: True)
    class Stop(Exception): pass
    def launch(args, **kwargs):
        assert '-I' in args
        assert set(kwargs['env'])=={'PATH','LANG','OMP_NUM_THREADS'}
        assert 'synthetic' not in str(kwargs)
        raise Stop()
    monkeypatch.setattr(local.subprocess, 'Popen', launch)
    import pytest
    with pytest.raises(Stop): local.request({'op':'encode'})


def test_worker_timeout_closes_process_without_waiting(monkeypatch):
    from unittest.mock import MagicMock
    import pytest
    local.close()
    process = MagicMock()
    process.poll.return_value = None
    process.stdin.fileno.return_value = 123
    monkeypatch.setattr(local, '_process', process)
    monkeypatch.setattr(local.os, 'set_blocking', lambda *args: None)
    monkeypatch.setattr(local.select, 'select', lambda *args: ([],[],[]))
    with pytest.raises(TimeoutError, match='too long'):
        local.request({'op':'encode', 'key':'test', 'image':''})
    process.terminate.assert_called_once()
    assert local._process is None
