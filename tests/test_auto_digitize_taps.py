"""Session 25: easy Digitize for me. Taps stand in for a written request, and the brief says
what will be made before Start, so a first-timer gets what an expert would have typed."""
import pytest

from embroiderly.auto_digitize import GOES_ON, SIZES, brief, classify, plan, taps, wish_for
from embroiderly.web import create_app
from test_auto_digitize import badge


def test_taps_set_the_fabric_size_and_look():
    wish = taps(dict(goes_on='cap', size='small', look='detailed', outlines=True, puff=True))
    assert wish == dict(fabric='cap', width_mm=70.0, detail='more', outlines=True, puff=True)
    # "Not sure" and Balanced leave the picture's own choices alone; unknown values are ignored.
    assert taps(dict(goes_on='', size='huge', look='balanced')) == {}
    assert set(GOES_ON) >= {'t_shirt', 'polo', 'hoodie', 'cap', 'jacket', 'bag', 'towel'}
    assert SIZES == {'small': 70, 'medium': 100, 'large': 200}


def test_typed_words_win_over_a_tap():
    wish = wish_for('6 cm wide, on a hoodie, simple', taps(dict(goes_on='t_shirt', size='large', look='detailed')))
    assert wish['width_mm'] == 60 and wish['fabric'] == 'fleece' and wish['detail'] == 'less'
    # A tap still counts where the words say nothing about it.
    assert wish_for('3 colours', taps(dict(size='large')))['width_mm'] == 200


def test_the_taps_reach_the_settings():
    kind, facts = classify(badge())
    options = plan(kind, facts, wish_for('', taps(dict(goes_on='t_shirt', size='small', puff=True))), (400, 300), {})
    assert options['fabric_preset'] == 'stretch_knit' and options['puff'] is True
    assert options['height_mm'] == pytest.approx(70 * 300 / 400, abs=.1)


def test_the_brief_says_what_will_be_made_in_plain_words():
    kind, facts = classify(badge())
    text = brief(kind, facts, wish_for('', taps(dict(goes_on='t_shirt', size='small', look='simple', outlines=True))),
                 (400, 300), {})
    assert text.startswith('Flat-colour artwork, 2 thread colours, plain background left out, about 70 × 52 mm')
    assert 'dark outline' in text and 'simplified' in text and text.endswith('stitches set for a T-shirt.')
    # Nothing tapped: the picture's own choices and the saved size.
    plain = brief(kind, facts, {}, (400, 300), {'height_mm': 60})
    assert plain == 'Flat-colour artwork, 3 thread colours, plain background left out, about 80 × 60 mm.'


def test_the_brief_endpoint_follows_the_taps_and_the_words(tmp_path):
    client = create_app(tmp_path).test_client()
    badge().save(tmp_path/'work/uploads/badge.png')
    reply = client.post('/api/auto-digitize/badge.png/brief', json=dict(goes_on='cap', size='small'))
    assert reply.status_code == 200 and 'about 70 × 52 mm' in reply.get_json()['brief']
    assert 'a cap' in reply.get_json()['brief']
    worded = client.post('/api/auto-digitize/badge.png/brief', json=dict(size='small', request='black lines only'))
    assert worded.get_json()['brief'].startswith('Black ink drawing')
    assert client.post('/api/auto-digitize/missing.png/brief', json={}).status_code == 404
