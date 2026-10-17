import hashlib
import json
import numpy as np
import pyembroidery as emb
import pytest
from embroiderly.thread_surface import read_stream, buffers, shade, render_file, rgb, rgb_lab, fit_view
from embroiderly.web import create_app


def write_fixture(path, lines, colour='#527aa4'):
    pattern=emb.EmbPattern();pattern.add_thread(colour)
    for a,b in lines:
        pattern.add_stitch_absolute(emb.JUMP,a[0]*10,a[1]*10)
        pattern.add_stitch_absolute(emb.STITCH,a[0]*10,a[1]*10)
        pattern.add_stitch_absolute(emb.STITCH,b[0]*10,b[1]*10)
    pattern.add_command(emb.END)
    emb.write_pes(pattern,str(path),{'version':6})
    return read_stream(path)


def test_surface_rejects_internal_plan_and_colourless_dst(tmp_path):
    with pytest.raises(ValueError,match='written PES'):
        read_stream(tmp_path/'engine-plan.json')
    with pytest.raises(ValueError,match='explicit palette'):
        read_stream(tmp_path/'design.dst')


def test_export_readback_heights_and_holes(tmp_path):
    plan=write_fixture(tmp_path/'single.pes',[((1,2),(10,2))])
    h,_,_,_=buffers(plan,240,100,20,[0,0])
    assert h[40,110]>.17
    assert h[40,21]<h[40,110]  # needle-point taper
    assert not h[10].any()  # jump from origin is not sewn
    twice=write_fixture(tmp_path/'twice.pes',[((1,2),(10,2)),((1,2),(10,2))])
    h2,_,_,_=buffers(twice,240,100,20,[0,0])
    assert np.isclose(h2[40,110],2*h[40,110],atol=.001)
    assert [s for s in plan['steps'] if s['t']=='stitch'][-1]['x']==10


def test_angle_brightness_reverses(tmp_path):
    lines=[((1,y),(11,y)) for y in np.arange(1,11,.4)]+[((x,1),(x,11)) for x in np.arange(14,24,.4)]
    plan=write_fixture(tmp_path/'angles.pes',lines)
    h,d,c,_=buffers(plan,520,260,20,[0,0])
    a=shade(h,d,c,20,[0,0],angle=0);b=shade(h,d,c,20,[0,0],angle=90)
    left=(h[:,0:240]>0);right=(h[:,270:]>0)
    al=a[:,:240][left].mean();ar=a[:,270:][right].mean()
    bl=b[:,:240][left].mean();br=b[:,270:][right].mean()
    assert al<ar and bl>br
    assert abs(al-ar)>.015 and abs(bl-br)>.015


@pytest.mark.parametrize('colour',['#126957','#527aa4','#ffffff','#000000','#ff0000','#ffec00','#9b3e58'])
def test_neutral_mean_catalogue_delta_e_below_three(tmp_path,colour):
    plan=write_fixture(tmp_path/'colour.pes',[((1,y),(9,y)) for y in np.arange(1,9,.4)],colour)
    h,d,c,_=buffers(plan,220,220,20,[0,0])
    out=shade(h,d,c,20,[0,0],neutral=True)
    average=out[h>0].mean(axis=0)
    # CIE76 is explicit, not mislabeled CIEDE2000. Includes clamped RGB colours.
    delta=float(np.linalg.norm(rgb_lab(average)-rgb_lab(rgb(colour))))
    assert delta<3,delta


def test_gap_long_stitch_and_determinism(tmp_path):
    path=tmp_path/'defects.pes'
    plan=write_fixture(path,[((1,2),(10,2)),((1,4),(4,4)),((6,4),(10,4))])
    h,d,c,_=buffers(plan,240,120,20,[0,0])
    assert not h[78:82,95:105].any()  # deliberate 2 mm gap
    assert (h[40,28:195]>0).all()  # complete 9 mm stitch, not split for display
    a=np.asarray(render_file(path,240,120));b=np.asarray(render_file(path,240,120))
    assert np.array_equal(a,b)
    assert np.array_equal(shade(h,d,c,20,[0,0]),shade(h,d,c,20,[0,0]))


def test_density_increases_height(tmp_path):
    normal=write_fixture(tmp_path/'normal.pes',[((1,y),(10,y)) for y in np.linspace(1,9,21)])
    dense=write_fixture(tmp_path/'dense.pes',[((1,y),(10,y)) for y in np.linspace(1,9,31)])
    a,ad,ac,_=buffers(normal,480,420,40,[0,0]);b,bd,bc,_=buffers(dense,480,420,40,[0,0])
    assert b.mean()>a.mean()*1.35
    assert b.max()>a.max()*1.2
    # Same outer extent and lighting: the denser left edge is darker.
    assert shade(b,bd,bc,40,[0,0])[60:300,41:45].mean()<shade(a,ad,ac,40,[0,0])[60:300,41:45].mean()


def test_mockup_endpoint_reads_export_and_preserves_bytes(tmp_path):
    app=create_app(tmp_path);target=tmp_path/'work/inkstitch-preview/example';target.mkdir(parents=True)
    path=target/'design.pes';write_fixture(path,[((1,1),(9,1)),((2,2),(9,3))])
    (target/'playback.json').write_text('{}') # intentionally no internal plan to render
    before=path.read_bytes();client=app.test_client()
    out=client.get('/thread-mockup/example.png?width=120&height=100&neutral=true')
    assert out.status_code==200 and out.mimetype=='image/png'
    assert out.headers['X-Export-SHA256']==hashlib.sha256(before).hexdigest()
    assert path.read_bytes()==before
    for query in ('strand=nan','angle=inf','width=9999','texture=foam','fabric=oops','neutral=maybe'):
        assert client.get('/thread-mockup/example.png?'+query).status_code==400
    assert client.get('/thread-mockup/missing.png').status_code==404


def test_finished_routes_use_written_files_and_dst_bound_palette(tmp_path):
    app=create_app(tmp_path);client=app.test_client()
    target=tmp_path/'work/machine-preview/legacy';target.mkdir(parents=True)
    pes=target/'fixture.pes';write_fixture(pes,[((1,1),(9,1))])
    dst=target/'experimental.dst';emb.write_dst(emb.EmbPattern(str(pes)),str(dst))
    metadata={'source_sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),'colors':['#527aa4'],'steps':[]}
    (target/'playback.json').write_text(json.dumps(metadata))
    out=client.get('/finished/legacy.png')
    assert out.status_code==302 and 'legacy=true' in out.location
    mock=client.get(out.location+'&width=120&height=100')
    assert mock.status_code==200 and mock.mimetype=='image/png'
    assert mock.headers['Content-Disposition'].startswith('inline')
    assert mock.headers['X-Export-SHA256']==metadata['source_sha256']
    metadata['source_sha256']='stale'
    (target/'playback.json').write_text(json.dumps(metadata))
    assert client.get(out.location+'&width=120&height=100').status_code==400
    alternate=client.get('/finished/legacy.png?engine=inkstitch')
    assert alternate.status_code==302 and 'legacy=false' in alternate.location

