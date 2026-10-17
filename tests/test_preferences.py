import json
import pytest
from embroiderly.preferences import SettingsService, SettingsConflict
from embroiderly.web import create_app


def test_preferences_persist_and_reject_conflicting_write(tmp_path):
    service = SettingsService(tmp_path / 'settings.sqlite3')
    assert service.read()['values']['theme'] == 'system'
    service.write({'theme': 'dark'}, 0)
    assert SettingsService(service.path).read()['values']['theme'] == 'dark'
    with pytest.raises(SettingsConflict):
        service.write({'theme': 'light'}, 0)
    assert service.read()['revision'] == 1


@pytest.mark.parametrize('patch', [{}, {'height_mm': 80}, {'theme': 'purple'}, {'theme': []}, {'owner_id': 'spoof'}])
def test_only_personal_appearance_settings_allowed(tmp_path, patch):
    service = SettingsService(tmp_path / 'settings.sqlite3')
    with pytest.raises(ValueError):
        service.write(patch, 0)
    assert service.read()['revision'] == 0


def test_future_claim_preserves_already_owned_records(tmp_path):
    service = SettingsService(tmp_path / 'settings.sqlite3')
    with service.connection() as db:
        db.execute("INSERT INTO designs(id,name,source,changed_at) VALUES('local','Local','local.png',0)")
        db.execute("INSERT INTO designs(id,owner_id,name,source,changed_at) VALUES('other','other-user','Other','other.png',0)")
        db.execute("INSERT INTO machine_profiles(id,value) VALUES('machine','{}')")
    service.claim_local_rows('verified-user')
    with service.connection() as db:
        assert db.execute("SELECT owner_id FROM designs WHERE id='local'").fetchone()[0] == 'verified-user'
        assert db.execute("SELECT owner_id FROM designs WHERE id='other'").fetchone()[0] == 'other-user'
        assert db.execute('SELECT owner_id FROM settings').fetchone()[0] == 'verified-user'
        assert db.execute('SELECT owner_id FROM machine_profiles').fetchone()[0] == 'verified-user'


def test_api_validation_conflict_and_no_claim_endpoint(tmp_path):
    client = create_app(tmp_path).test_client()
    response = client.get('/api/settings')
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    payload = {'values': {'theme': 'dark'}, 'revision': 0}
    assert client.patch('/api/settings', json=payload, headers={'Origin':'https://untrusted.example'}).status_code == 403
    assert client.patch('/api/settings', json=payload).status_code == 200
    assert client.patch('/api/settings', json=payload).status_code == 409
    assert client.patch('/api/settings', json=[]).status_code == 400
    assert client.post('/api/settings/claim', json={'owner_id':'spoof'}).status_code == 404
    assert not list((tmp_path / 'work' / 'decisions').glob('*'))
