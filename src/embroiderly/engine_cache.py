"""Exact-input cache. Never reuse partial or modified machine outputs."""
import threading
import weakref
from functools import wraps
import hashlib
import json
from pathlib import Path
from importlib.metadata import version
from uuid import uuid4
from .saved_plans import read_plan

_locks=weakref.WeakValueDictionary()
_guard=threading.Lock()

def serialize_output(function):
    @wraps(function)
    def wrapped(source,directory,*args,**kwargs):
        key=str(Path(directory).resolve())
        with _guard:
            lock=_locks.get(key)
            if lock is None:
                lock=threading.RLock();_locks[key]=lock
        with lock:return function(source,directory,*args,**kwargs)
    return wrapped

FILES = ('design.svg', 'design.pes', 'design.dst', 'engine-plan.json', 'playback.json', 'release-context.json')

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def cache_key(source, svg):
    from .stitch_engine import fingerprint
    return hashlib.sha256(json.dumps(dict(
        schema=2, source=digest(source), svg=digest(svg),
        integration=digest(Path(__file__).with_name('engine.py')),
        engine=fingerprint(),
        exporter=version('pyembroidery'),
    ), sort_keys=True).encode()).hexdigest()

def lookup(directory, key):
    directory = Path(directory)
    try:
        record = json.loads((directory/'verified-cache.json').read_text())
        if not isinstance(record,dict) or record.get('key') != key:return None
        if record.get('files') != {name:digest(directory/name) for name in FILES}:return None
        return read_plan(directory/'playback.json')
    except (OSError, ValueError, TypeError):
        return None

def publish(directory, key, policy=None):
    directory = Path(directory)
    record = dict(key=key, routing_policy=policy, files={name:digest(directory/name) for name in FILES})
    temporary=directory/('verified-cache.'+uuid4().hex+'.tmp')
    temporary.write_text(json.dumps(record,sort_keys=True))
    temporary.replace(directory/'verified-cache.json')
