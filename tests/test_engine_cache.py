import json
from embroiderly.engine_cache import FILES, lookup, publish

def fixture(tmp_path):
    for name in FILES:(tmp_path/name).write_bytes(b'unchanged machine output')
    plan=dict(steps=[dict(t='stitch',x=1,y=1,color='#123456')],colors=['#123456'],stitch_count=1,trim_count=0,origin_mm=[0,0])
    (tmp_path/'playback.json').write_text(json.dumps(plan))
    return plan

def test_exact_cache_preserves_plan_and_bytes(tmp_path):
    plan=fixture(tmp_path)
    before={p.name:p.read_bytes() for p in tmp_path.iterdir()}
    publish(tmp_path,'exact')
    assert lookup(tmp_path,'exact')==plan
    assert all((tmp_path/name).read_bytes()==content for name,content in before.items())
    assert lookup(tmp_path,'different settings') is None

def test_modified_or_missing_exports_never_reused(tmp_path):
    fixture(tmp_path);publish(tmp_path,'exact')
    (tmp_path/'design.pes').write_bytes(b'changed')
    assert lookup(tmp_path,'exact') is None
    (tmp_path/'design.dst').unlink()
    assert lookup(tmp_path,'exact') is None

def test_changed_release_context_invalidates_exact_cache(tmp_path):
    fixture(tmp_path)
    (tmp_path/'release-context.json').write_text('original context')
    publish(tmp_path,'exact')
    (tmp_path/'release-context.json').write_text('changed context')
    assert lookup(tmp_path,'exact') is None


def test_incomplete_or_malformed_cache_ignored(tmp_path):
    fixture(tmp_path)
    assert lookup(tmp_path,'exact') is None
    (tmp_path/'verified-cache.json').write_text('{')
    assert lookup(tmp_path,'exact') is None
