"""Local design index. Hiding a recent item is not deleting its saved work.

Soft deletion changes metadata only. Permanent cleanup is deliberately separate
because older generated caches can be shared by multiple originals.
"""
from __future__ import annotations

import io
import json
import math
import re
import shutil
import time
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps


class LibraryConflict(ValueError):
    pass


class DesignLibrary:
    def __init__(self, root, settings):
        self.root = Path(root)
        self.settings = settings
        self.uploads = self.root / 'work' / 'uploads'
        self.decisions = self.root / 'work' / 'decisions'
        with settings.connection() as db:
            columns = {row['name'] for row in db.execute('PRAGMA table_info(designs)')}
            if 'revision' not in columns:
                db.execute('ALTER TABLE designs ADD COLUMN revision INTEGER NOT NULL DEFAULT 0')

    def adopt(self):
        """Index originals in place; never rename, modify or adopt derived caches."""
        with self.settings.connection() as db:
            for path in self.uploads.iterdir():
                if not path.is_file() or path.is_symlink() or path.suffix.lower() not in {'.png','.jpg','.jpeg','.webp','.bmp'}:
                    continue
                if path.name.startswith('prepared_') or path.with_suffix('.prep.json').exists():
                    continue
                title = 'Untitled design' if re.fullmatch(r'[a-f0-9]{32}', path.stem) else path.stem.replace('_', ' ').replace('-', ' ')
                changed = path.stat().st_mtime
                for sidecar in self.decisions.glob(path.name + '.*'):
                    changed = max(changed, sidecar.stat().st_mtime)
                db.execute('INSERT OR IGNORE INTO designs(id,name,source,changed_at) VALUES(?,?,?,?)',
                           (path.name, title[:120], path.name, changed))
                db.execute('UPDATE designs SET changed_at=MAX(changed_at,?) WHERE id=?', (changed,path.name))

    def get(self, ident):
        with self.settings.connection() as db:
            row = db.execute('SELECT * FROM designs WHERE id=?', (ident,)).fetchone()
            if row is None:
                raise KeyError(ident)
            return dict(row)

    def list(self, view='recent'):
        self.adopt()
        clauses = {'recent':'deleted_at IS NULL AND removed_recent=0',
                   'all':'deleted_at IS NULL', 'trash':'deleted_at IS NOT NULL'}
        if view not in clauses:
            raise ValueError('Choose Recent, All designs or Trash.')
        with self.settings.connection() as db:
            rows = [dict(row) for row in db.execute('SELECT * FROM designs WHERE ' + clauses[view])]
        for row in rows:
            row['days_remaining'] = None if row['deleted_at'] is None else max(0, math.ceil(30-(time.time()-row['deleted_at'])/86400))
        return rows

    def change(self, action, items, title=None):
        if action not in {'rename','remove_recent','delete','restore','opened'}:
            raise ValueError('Unknown design action.')
        if not isinstance(items, list) or not 1 <= len(items) <= 500:
            raise ValueError('Select between 1 and 500 designs.')
        if any(not isinstance(x,dict) or set(x) != {'id','revision'} or not isinstance(x['id'],str) or type(x['revision']) is not int for x in items):
            raise ValueError('Each design needs its id and current revision.')
        if len({x['id'] for x in items}) != len(items):
            raise ValueError('Select each design only once.')
        if action == 'rename' and (len(items) != 1 or not isinstance(title,str) or not 1 <= len(title.strip()) <= 120):
            raise ValueError('Enter a design name between 1 and 120 characters.')
        now = time.time()
        with self.settings.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            rows = []
            for item in items:
                row = db.execute('SELECT * FROM designs WHERE id=?', (item['id'],)).fetchone()
                if row is None:
                    raise KeyError(item['id'])
                if row['revision'] != item['revision']:
                    raise LibraryConflict('A selected design changed in another window. Reload the library and try again.')
                if action != 'restore' and row['deleted_at'] is not None:
                    raise LibraryConflict('This design is in Trash. Restore it first.')
                rows.append(dict(row))
            for row in rows:
                if action == 'rename':
                    db.execute('UPDATE designs SET name=?,changed_at=?,revision=revision+1 WHERE id=?', (title.strip(),now,row['id']))
                elif action == 'remove_recent':
                    db.execute('UPDATE designs SET removed_recent=1,revision=revision+1 WHERE id=?', (row['id'],))
                elif action == 'delete':
                    db.execute('UPDATE designs SET deleted_at=?,revision=revision+1 WHERE id=?', (now,row['id']))
                elif action == 'restore':
                    # Preserve remove-from-recent independently of deletion.
                    db.execute('UPDATE designs SET deleted_at=NULL,revision=revision+1 WHERE id=?', (row['id'],))
                else:
                    db.execute('UPDATE designs SET opened_at=?,removed_recent=0,revision=revision+1 WHERE id=?', (now,row['id']))
            return [dict(db.execute('SELECT * FROM designs WHERE id=?',(r['id'],)).fetchone()) for r in rows]

    def duplicate(self, ident, revision):
        row = self.get(ident)
        if row['revision'] != revision or row['deleted_at'] is not None:
            raise LibraryConflict('The design changed. Reload the library before making a copy.')
        source = self.uploads / row['source']
        target = self.uploads / (uuid4().hex + source.suffix)
        created = []
        try:
            shutil.copy2(source, target)
            created.append(target)
            # Copy only this design's exact sidecars, not other designs or shared caches.
            for old in self.decisions.glob(source.name + '.*'):
                if old.is_symlink():
                    raise ValueError('Cannot copy a linked design attachment.')
                new = self.decisions / (target.name + old.name[len(source.name):])
                if old.is_dir():
                    shutil.copytree(old, new, symlinks=True)
                else:
                    shutil.copy2(old, new)
                created.append(new)
            with self.settings.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                current = db.execute('SELECT revision,deleted_at FROM designs WHERE id=?',(ident,)).fetchone()
                if current['revision'] != revision or current['deleted_at'] is not None:
                    raise LibraryConflict('The original changed while copying. Reload and try again.')
                db.execute('INSERT INTO designs(id,owner_id,name,source,changed_at) VALUES(?,?,?,?,?)',
                           (target.name,row['owner_id'],(row['name'][:113]+' (copy)'),target.name,time.time()))
            return self.get(target.name)
        except Exception:
            # Exact paths allocated by this operation only, never user originals.
            for path in reversed(created):
                if path.is_dir(): shutil.rmtree(path)
                else: path.unlink(missing_ok=True)
            raise

    def facts(self, ident):
        from .saved_plans import matching_plan
        row = self.get(ident)
        path = self.uploads / row['source']
        options_path = self.decisions / (path.name + '.preparation.json')
        options = json.loads(options_path.read_text()) if options_path.exists() else {}
        height = float(options.get('height_mm', 100))
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image)
            width = height * image.width / image.height
        plan = matching_plan(self.root, path, options).get('playback')
        return {'width_mm':width,'height_mm':height,
                'thread_count':len(set(plan['colors'])) if plan else None,
                'stitch_count':plan['stitch_count'] if plan else None,
                'status':'Ready' if plan else 'Not generated'}


def register_library(app, root):
    from flask import abort, jsonify, request, send_file, render_template
    library = DesignLibrary(root, app.extensions['settings_service'])
    app.extensions['design_library'] = library

    @app.before_request
    def protect_trashed_design():
        if request.endpoint and request.endpoint.startswith('library_'):
            return
        name = (request.view_args or {}).get('name')
        if not name: return
        # Follow prepared-source metadata for old deep links as well as originals.
        seen = set()
        for _ in range(8):
            if name in seen or Path(name).name != name: break
            seen.add(name)
            try:
                row = library.get(name)
            except KeyError:
                meta = (library.uploads / name).with_suffix('.prep.json')
                try: name = json.loads(meta.read_text()).get('source')
                except (OSError,ValueError): break
                if not isinstance(name,str): break
                continue
            if row['deleted_at'] is not None:
                if len(seen) > 1:
                    # Content-addressed generation caches can belong to a live copy.
                    # Never disable that copy's playback because its original is trashed.
                    original = library.uploads / row['source']
                    with library.settings.connection() as db:
                        active = db.execute('SELECT source FROM designs WHERE deleted_at IS NULL').fetchall()
                    try:
                        source_bytes = original.read_bytes()
                        if any((library.uploads / candidate['source']).is_file() and
                               (library.uploads / candidate['source']).read_bytes() == source_bytes for candidate in active):
                            break
                    except OSError:
                        pass
                if request.method != 'GET':
                    return jsonify(error='Design is in Trash. Restore it before editing.'), 410
                return render_template('trashed.html', design_name=row['name']), 410
            break

    @app.get('/api/library')
    def library_list():
        try: result = library.list(request.args.get('view','recent'))
        except ValueError as error: return jsonify(error=str(error)),400
        response = jsonify(designs=result, permanent_cleanup_available=False)
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/api/library/<ident>/facts')
    def library_facts(ident):
        try: return jsonify(library.facts(ident))
        except KeyError: abort(404)
        except (OSError, ValueError, TypeError): return jsonify(error='Design details could not load.'),422

    @app.get('/api/library/<ident>/preview')
    def library_preview(ident):
        try: row = library.get(ident)
        except KeyError: abort(404)
        try:
            with Image.open(library.uploads / row['source']) as source:
                image = ImageOps.exif_transpose(source).convert('RGBA')
                image.thumbnail((600,450),Image.Resampling.LANCZOS)
                buffer = io.BytesIO(); image.save(buffer,format='PNG'); buffer.seek(0)
            response = send_file(buffer,mimetype='image/png')
            response.headers['Cache-Control'] = 'no-store'
            return response
        except (OSError,ValueError): return jsonify(error='Preview did not load.'),422

    @app.post('/api/library/action')
    def library_action():
        origin = request.headers.get('Origin')
        if origin and origin.rstrip('/') != request.host_url.rstrip('/'):
            return jsonify(error='Use the library on this app.'),403
        data = request.get_json(silent=True)
        if not isinstance(data,dict): return jsonify(error='Expected a design action.'),400
        try:
            if data.get('action') == 'duplicate':
                items = data.get('items')
                if not isinstance(items,list) or len(items) != 1 or not isinstance(items[0],dict):
                    raise ValueError('Choose one design to duplicate.')
                result = [library.duplicate(items[0]['id'],items[0]['revision'])]
            else:
                result = library.change(data.get('action'),data.get('items'),data.get('name'))
            return jsonify(designs=result)
        except LibraryConflict as error: return jsonify(error=str(error)),409
        except KeyError: return jsonify(error='Design not found. Reload the library.'),404
        except (TypeError,ValueError) as error: return jsonify(error=str(error)),400
        except OSError: return jsonify(error='Could not save the library change. Reload to check its status.'),500
