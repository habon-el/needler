import json
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import pyembroidery as emb
import pytest
from flask import Flask

from embroiderly import lettering_native as native
from embroiderly.lettering_geometry import outline, source_frame, SVG, INK
from embroiderly.lettering_source import route_font


FONT_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" xmlns:i="http://inkstitch.org/namespace"
 xmlns:k="http://www.inkscape.org/namespaces/inkscape">
 <g i:letter-group="glyph" k:label="A"><path id="stroke" i:satin_column="true" d="M0 0L0 10M3 0L3 10"/>
 <path id="dot" i:satin_column="true" d="M0 15L0 18M3 15L3 18"/></g></svg>'''


def test_disconnected_font_pieces_cut_without_changing_rails():
    updated, cuts = route_font(FONT_SVG)
    before = ET.fromstring(FONT_SVG).findall('.//'+SVG+'path')
    after = ET.fromstring(updated).findall('.//'+SVG+'path')
    assert [p.get('d') for p in before] == [p.get('d') for p in after]
    assert cuts == 1 and after[0].get(INK+'trim_after') == 'true'
    assert [p.get(INK+'random_seed') for p in after] == ['1', '2']
    assert route_font(updated)[0] == updated


def test_closed_rails_keep_letter_hole():
    svg = FONT_SVG.replace('M0 0L0 10M3 0L3 10',
                          'M0 0L20 0L20 20L0 20L0 0 M5 5L15 5L15 15L5 15L5 5')
    shapes = outline(svg, with_paths=True)
    assert len(shapes['stroke'].interiors) == 1
    from shapely.geometry import Point
    assert not shapes['stroke'].covers(Point(10*25.4/96, 10*25.4/96))


def test_source_mask_does_not_authorize_dot_connector():
    _, mask, origin, _ = source_frame(FONT_SVG)
    from embroiderly.knockout_routing import RemovedPixels
    # Source spans 0..18 px; origin is its centre; gap midpoint y=12.5 px.
    y = (12.5-9)*25.4/96
    assert RemovedPixels(mask, .04, origin).crosses([0,y*10], [0,y*10])


def test_glyph_check_rejects_missing_marks_without_substitution():
    assert native.glyph_check(FONT_SVG, 'A') == 1
    with pytest.raises(ValueError, match='every letter'):
        native.glyph_check(FONT_SVG, 'A.')


@pytest.fixture
def client(tmp_path, monkeypatch):
    count = []
    def generate(body, **kwargs):
        assert kwargs in ({'native': True}, {'native': True, 'wedges': False})  # without wedges: build's retry
        count.append(body)
        thread=dict(color='#000000',description='Black',catalog_number=None,details=None,brand=None,chart=None,weight=None)
        source = FONT_SVG.replace('<path id="dot" i:satin_column="true" d="M0 15L0 18M3 15L3 18"/>','')
        return dict(svg=source, plan={'extras':{},'threadlist':[thread],
                    'stitches':[[-3,-10,'JUMP'],[-3,-10,'STITCH'],[-3,10,'STITCH'],[3,10,'STITCH'],[3,-10,'STITCH'],[3,-10,'END']]},
                    nominal_height_mm=5, rebuild_report=dict(mask=np.ones((150,150),dtype=bool),
                    origin=[2,2],columns=1,added_cuts=0))
    monkeypatch.setattr(native.small_lettering, 'generate', generate)
    app = Flask(__name__)
    native.register(app, tmp_path)
    return app.test_client(), tmp_path/'work/lettering-native', count


BODY = dict(text='A', font='small_font', height_mm=5, available_width_mm=50, align='center', colour='#123456')


def test_real_download_requires_approval_and_reuses_exact_checked_pair(client):
    c, store, calls = client
    result = c.post('/lettering/native/check', json=BODY)
    assert result.status_code == 200, result.json
    data=result.json;key=data['id']
    assert data['checks_passed'] and not data['approved']
    assert c.get(f'/lettering/native/{key}/download/dst').status_code == 422
    assert c.post(f'/lettering/native/{key}/approve', json={'approve':True}).status_code == 200
    for fmt in ('pes','dst'):
        download = c.get(f'/lettering/native/{key}/download/{fmt}')
        assert download.status_code == 200
        assert download.data == (store/key/('design.'+fmt)).read_bytes()
    again = c.post('/lettering/native/check', json=BODY)
    assert again.json['id'] == key and again.json['cached'] and again.json['approved']
    assert len(calls) == 1
    width_only = c.post('/lettering/native/check',json={**BODY, 'available_width_mm':30})
    assert width_only.json['cached'] and width_only.json['id'] != key
    assert not width_only.json['approved'] and len(calls) == 1
    # Both formats share the gate, even if only one was requested.
    (store/key/'design.pes').write_bytes(b'corrupt')
    assert c.get(f'/lettering/native/{key}/download/dst').status_code == 422
    assert c.post('/lettering/native/check', json=BODY).status_code == 422


@pytest.mark.parametrize('change', [{'text':'A.'},{'height_mm':4},{'available_width_mm':30},{'colour':'#223344'}])
def test_cache_key_tracks_every_recipe_change(change):
    assert native.identity(BODY) != native.identity({**BODY, **change})


def test_invalid_glyph_size_and_colour_never_fall_back(client):
    c, _, calls = client
    for delta in ({'text':'🦉'}, {'height_mm':3}, {'colour':'javascript:bad'}, {'available_width_mm':0}):
        result = c.post('/lettering/native/check',json={**BODY, **delta})
        assert result.status_code == 400 and result.json['error']
    assert not calls


def test_unsafe_native_file_is_not_approved(client, monkeypatch):
    c, _, _ = client
    generator = native.small_lettering.generate
    def broken(*args, **kwargs):
        result = generator(*args, **kwargs)
        result['plan']['stitches'][2] = [-3,-8,'STITCH']
        return result
    monkeypatch.setattr(native.small_lettering,'generate',broken)
    r=c.post('/lettering/native/check',json=BODY)
    assert r.status_code==200 and not r.json['checks_passed']
    assert r.json['reports']['dst']['short'] > 0
    assert c.post('/lettering/native/'+r.json['id']+'/approve',json={'approve':True}).status_code==422


def test_busy_and_failure_release_lock(client, monkeypatch):
    c, _, _ = client
    native.BUSY.acquire()
    try:
        assert c.post('/lettering/native/check',json=BODY).status_code==409
    finally:
        native.BUSY.release()
    def fail(*args, **kwargs):
        raise OSError('internal path should not reach user')
    monkeypatch.setattr(native.small_lettering,'generate',fail)
    r=c.post('/lettering/native/check',json=BODY)
    assert r.status_code==422 and 'internal path' not in r.json['error']
    assert not native.BUSY.locked()
