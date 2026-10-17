"""The retry must recheck written files and never approve a rejected candidate."""
from copy import deepcopy
import pytest
from test_lettering_native import client, BODY
from embroiderly import lettering_native as native, lettering_rebuild
from embroiderly.lettering_source import route_font


@pytest.mark.parametrize('candidate_safe', [True, False])
def test_native_retry_uses_same_release_gate_and_never_saves_unsafe_candidate(client, monkeypatch, candidate_safe):
    c, store, _ = client
    generate = native.small_lettering.generate
    rebuilt = []
    safe = {}
    def short(*args, **kwargs):
        original = generate(*args, **kwargs)
        safe['plan'] = deepcopy(original['plan'])
        original['svg'], _ = route_font(original['svg'])
        original['plan']['stitches'][2] = [-3, -8, 'STITCH']
        return original
    def rebuild(svg, engine):
        rebuilt.append(svg)
        assert 'M 0,0 L 0.6,0' in svg
        plan = deepcopy(safe['plan'])
        if not candidate_safe:
            plan['stitches'][2] = [-3, -8, 'STITCH']
        return svg, plan, {}
    monkeypatch.setattr(native.small_lettering, 'generate', short)
    monkeypatch.setattr(lettering_rebuild, 'rebuild', rebuild)
    response = c.post('/lettering/native/check', json=BODY)
    assert response.status_code == 200, response.json
    data = response.json
    assert len(rebuilt) == 1
    assert data['recipe'] == BODY and not data['approved']
    assert data['checks_passed'] is candidate_safe
    if candidate_safe:
        assert data['lock_adjustment']['before_short'] == 1
        assert data['lock_adjustment']['after_short'] == 0
        assert data['reports']['dst']['short'] == data['reports']['pes']['short'] == 0
    else:
        assert data['lock_adjustment'] is None
        assert data['reports']['dst']['short'] == 1
        assert 'M 0,0 L 0.6,0' not in (store/data['id']/'source.svg').read_text()
    approval = c.post('/lettering/native/'+data['id']+'/approve', json={'approve': True})
    assert approval.status_code == (200 if candidate_safe else 422)
