"""Device-local preferences. Design options deliberately do not belong here.

Storage is replaceable through read/write; ownership migration is internal only.
No authentication or identity-claim HTTP endpoint is exposed.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


DEFAULTS = {
    "theme": "system", "detail": "standard", "motion": "system",
    "density": "comfortable", "units": "mm",
}
CHOICES = {
    "theme": {"dark", "light", "system"},
    "detail": {"simple", "standard", "expert"},
    "motion": {"on", "off", "system"},
    "density": {"comfortable", "compact"},
    "units": {"mm", "in"},
}


class SettingsService:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY CHECK(id=1), owner_id TEXT,
                    value TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS designs (
                    id TEXT PRIMARY KEY, owner_id TEXT, name TEXT NOT NULL,
                    source TEXT NOT NULL, removed_recent INTEGER NOT NULL DEFAULT 0,
                    deleted_at REAL, opened_at REAL, changed_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS machine_profiles (
                    id TEXT PRIMARY KEY, owner_id TEXT, value TEXT NOT NULL
                );
            ''')
            db.execute('INSERT OR IGNORE INTO settings(id,value) VALUES(1,?)',
                       (json.dumps(DEFAULTS),))

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def read(self):
        with self.connection() as db:
            row = db.execute('SELECT value,revision FROM settings WHERE id=1').fetchone()
            return {"values": {**DEFAULTS, **json.loads(row['value'])},
                    "revision": row['revision']}

    def write(self, patch, revision):
        if not isinstance(patch, dict) or not patch or set(patch) - set(CHOICES):
            raise ValueError('Unknown or empty settings change.')
        if type(revision) is not int or revision < 0:
            raise ValueError('A valid settings revision is required.')
        for key, value in patch.items():
            if not isinstance(value, str) or value not in CHOICES[key]:
                raise ValueError(f'Invalid {key} preference.')
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT value,revision FROM settings WHERE id=1').fetchone()
            if row['revision'] != revision:
                raise SettingsConflict('Settings changed in another window. Reload settings and try again.')
            values = {**DEFAULTS, **json.loads(row['value']), **patch}
            db.execute('UPDATE settings SET value=?,revision=revision+1 WHERE id=1',
                       (json.dumps(values),))
            return {"values": values, "revision": revision + 1}

    def claim_local_rows(self, authenticated_owner_id):
        """Future auth adapter calls this AFTER verifying the provider's identity.

        One transaction claims device rows. Never accept a browser-supplied identity.
        """
        if not isinstance(authenticated_owner_id, str) or not authenticated_owner_id.strip():
            raise ValueError('Verified owner id required.')
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            for table in ('designs', 'settings', 'machine_profiles'):
                db.execute(f'UPDATE {table} SET owner_id=? WHERE owner_id IS NULL',
                           (authenticated_owner_id,))


class SettingsConflict(ValueError):
    pass


def register_preferences(app, root):
    from flask import jsonify, request
    service = SettingsService(root / 'work' / 'library.sqlite3')
    app.extensions['settings_service'] = service

    @app.route('/api/settings', methods=['GET', 'PATCH'])
    def preferences():
        if request.method == 'GET':
            response = jsonify(service.read())
            response.headers['Cache-Control'] = 'no-store'
            return response
        # JSON-only plus same-origin protects this local mutation from web forms.
        origin = request.headers.get('Origin')
        if origin and origin.rstrip('/') != request.host_url.rstrip('/'):
            return jsonify(error='Use the settings panel on this app.'), 403
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or set(data) != {'values', 'revision'}:
            return jsonify(error='Expected settings values and revision.'), 400
        try:
            return jsonify(service.write(data['values'], data['revision']))
        except SettingsConflict as error:
            return jsonify(error=str(error)), 409
        except ValueError as error:
            return jsonify(error=str(error)), 400
