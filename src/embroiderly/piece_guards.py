"""Local, design-scoped mutation serialization and shared saved-lock enforcement."""
import json
import threading
import weakref
from pathlib import Path
from .piece_layout import guard, edits

_locks=weakref.WeakValueDictionary()
_mutex=threading.Lock()


def register(app,root):
    from flask import request,g,jsonify

    @app.before_request
    def guard_saved_pieces():
        # Read-only review cannot apply options. A network call must not hold
        # the mutation lock or stop the customer inspecting locked artwork.
        # AI draft endpoints only propose; they independently check saved/draft locks.
        # Keep every existing mutation endpoint under the original guard.
        if request.endpoint in ('design_review', 'ai_draft', 'ai_draft_job'):
            return
        if request.method not in ('POST','PATCH','DELETE') or not request.view_args or 'name' not in request.view_args:
            return
        name=Path(request.view_args['name']).name
        metadata=root/'work/uploads'/Path(name).with_suffix('.prep.json')
        if metadata.is_file():
            source=json.loads(metadata.read_text()).get('source')
            if source:name=Path(source).name
        saved=root/'work/decisions'/(name+'.preparation.json')
        with _mutex:
            lock=_locks.get(str(saved))
            if lock is None:lock=threading.RLock();_locks[str(saved)]=lock
        lock.acquire();g.piece_mutation_lock=lock
        previous=json.loads(saved.read_text()) if saved.is_file() else {}
        if not any(p.get('locked') for p in edits(previous).values()):return
        body=request.get_json(silent=True)
        try:
            if request.endpoint not in ('artwork_prepare','assist'):
                raise ValueError('A piece is locked. Unlock it before running an automatic or legacy edit.')
            if not isinstance(body,dict) or not isinstance(body.get('options'),dict):
                raise ValueError('A piece is locked. Reload the current design before editing.')
            guard(previous,body['options'])
        except ValueError as error:
            return jsonify(error=str(error)),409

    @app.teardown_request
    def release_piece_mutation_lock(error):
        lock=g.pop('piece_mutation_lock',None)
        if lock is not None:lock.release()
