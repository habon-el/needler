"""Custom fabric settings: a listed fabric with the user's own values, saved for every design,
carried in the design settings, used by the stitch engine, lettering and the worksheet."""
import pytest

from embroiderly import custom_fabrics
from embroiderly.generation_policy import preset_for
from embroiderly.small_lettering import fabric_pull_extra
from embroiderly.worksheet import fabric_info

MINE = dict(name=' Thick hoodie ', base='fleece', row_spacing_mm=.6, satin_spacing_mm=.45, satin_pull_mm=.3,
            fill_underlay=False, max_stitch_length_mm=4.5)


def test_own_fabrics_are_saved_changed_and_deleted(tmp_path):
    fabric, saved = custom_fabrics.save(tmp_path, MINE)
    assert fabric['name'] == 'Thick hoodie' and fabric['id'].startswith('mine-') and saved == [fabric]
    changed, saved = custom_fabrics.save(tmp_path, dict(fabric, name='Hoodie', satin_pull_mm=.25))
    assert changed['id'] == fabric['id'] and len(saved) == 1 and saved[0]['satin_pull_mm'] == .25
    assert custom_fabrics.delete(tmp_path, fabric['id']) == []
    with pytest.raises(ValueError):
        custom_fabrics.delete(tmp_path, fabric['id'])


@pytest.mark.parametrize('change', [dict(name=''), dict(name='x'*41), dict(base='cardboard'), dict(row_spacing_mm=.1),
                                    dict(satin_spacing_mm=2), dict(satin_pull_mm=-.1), dict(max_stitch_length_mm=float('nan')),
                                    dict(max_stitch_length_mm='long'), dict(fill_underlay='yes')])
def test_bad_fabrics_are_refused(tmp_path, change):
    with pytest.raises(ValueError):
        custom_fabrics.save(tmp_path, dict(MINE, **change))
    assert custom_fabrics.saved(tmp_path) == []


def test_at_most_thirty_own_fabrics(tmp_path):
    for _ in range(custom_fabrics.MAX_SAVED):
        custom_fabrics.save(tmp_path, MINE)
    with pytest.raises(ValueError):
        custom_fabrics.save(tmp_path, MINE)


def test_custom_values_replace_the_base_fabric_values():
    fabric = custom_fabrics.check(MINE)
    row = preset_for(dict(fabric_preset='twill', fabric_custom=fabric))
    fleece = preset_for(dict(fabric_preset='fleece'))
    assert row['row_spacing_mm'] == .6 and row['satin_pull_mm'] == .3 and row['fill_underlay'] is False
    assert row['label'] == 'Thick hoodie' and row['fabric'] == 'fleece' and row['backing'] == fleece['backing']
    info = fabric_info('fleece', fabric)
    assert info['label'] == 'Thick hoodie' and info['backing'] == fleece['backing']
    # Lettering: the extra pull follows the custom value (capped as for listed fabrics).
    assert fabric_pull_extra(dict(fabric_custom=fabric)) == pytest.approx(.1)
    with pytest.raises(ValueError):
        preset_for(dict(fabric_custom=dict(fabric, satin_pull_mm=5)))


def test_custom_fabric_changes_the_stitches_and_worksheet(tmp_path):
    from PIL import Image, ImageDraw
    from embroiderly.web import create_app
    client = create_app(tmp_path).test_client()
    listed = client.get('/api/fabrics').get_json()
    twill = next(f for f in listed['fabrics'] if f['id'] == 'twill')
    assert listed['saved'] == [] and twill['row_spacing_mm'] == .4
    body = dict(name='Open twill', base='twill', row_spacing_mm=.7, satin_spacing_mm=.4, satin_pull_mm=.1,
                fill_underlay=True, max_stitch_length_mm=3)
    mine = client.post('/api/fabrics', json=body).get_json()['fabric']
    assert client.get('/api/fabrics').get_json()['saved'] == [mine]
    assert client.post('/api/fabrics', json=dict(body, row_spacing_mm=3)).status_code == 400
    image = Image.new('RGB', (300, 200), 'white')
    ImageDraw.Draw(image).rectangle((40, 40, 260, 160), fill='#1d4f91')
    image.save(tmp_path / 'work/uploads/block.png')
    counts = {}
    for name, extra in (('twill', {}), ('open', dict(fabric_custom=mine))):
        options = dict(artwork_type='logo', count=2, height_mm=40, fabric_preset='twill', **extra)
        result = client.post('/artwork/block.png', json=dict(options=options, digitize=True, subject_confirmed=True)).get_json()
        counts[name] = result['playback']['stitch_count']
    assert counts['open'] < counts['twill']
    assert 'Open twill' in client.get('/worksheet/'+result['prepared_name']).get_data(as_text=True)
    # Deleting the saved fabric leaves the design's own copy untouched.
    assert client.delete('/api/fabrics/'+mine['id']).get_json()['saved'] == []
    assert client.delete('/api/fabrics/'+mine['id']).status_code == 404
