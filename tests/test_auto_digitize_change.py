"""Session 26: change a made design by typing or speaking. Needler says what it understood and
shows it before anything is made; then only that change is made, the rest stays."""
import time

from PIL import Image, ImageDraw

from embroiderly.auto_digitize import merge_change, named_removal, parse_request, removal_preview, understood, wish_for
from embroiderly.web import create_app


def fireball(size=(300, 300)):
    """A ball on fire on white, with a white highlight inside the ball (the subject's own white)."""
    image = Image.new('RGB', size, 'white')
    draw = ImageDraw.Draw(image)
    draw.polygon([(150, 20), (200, 120), (100, 120)], fill='#e8401c')
    draw.ellipse((70, 90, 230, 250), fill='#f08a24', outline='black', width=6)
    draw.ellipse((110, 120, 140, 150), fill='white')
    return image


def test_keep_only_the_subject_means_leave_out_the_background():
    wish = parse_request('Remove the white background, keep only the basketball on fire')
    assert wish['remove_background'] is True and wish['remove_colour'] == 'white'
    assert parse_request('keep only the ball')['remove_background'] is True
    assert 'remove_colour' not in parse_request('no background please')
    # "Keep the background" still means keep it; the two never come together.
    assert 'remove_background' not in parse_request('keep the background')


def test_a_later_change_wins_and_the_rest_stays():
    first = wish_for('6 cm wide, 3 colours, keep the background', {'fabric': 'cap'})
    changed = wish_for('6 cm wide, 3 colours, keep the background', {'fabric': 'cap'},
                       ['remove the white background', '5 colours'])
    assert first['keep_background'] and 'keep_background' not in changed
    assert changed['remove_colour'] == 'white' and changed['colours'] == 5
    assert changed['width_mm'] == 60 and changed['fabric'] == 'cap'
    # "Bigger" grows the last result's sewn width by a quarter.
    assert merge_change({'height_mm': 50}, parse_request('make it bigger'), 80)['width_mm'] == 100
    assert 'height_mm' not in merge_change({'height_mm': 50}, parse_request('make it bigger'), 80)


def test_what_it_understood_is_said_in_plain_words():
    old = wish_for('', {'fabric': 'stretch_knit'})
    new = merge_change(old, parse_request('remove the white background, add an outline, 4 colours'))
    assert understood(old, new) == ['Leave out the white background and keep only the subject.',
                                    'Use 4 thread colours.', 'Add a dark outline around each colour.']
    assert understood(old, merge_change(old, parse_request('make it look nicer'))) == []


def test_the_preview_shows_only_the_outside_white_left_out():
    image = fireball()
    operation = named_removal(image, 'white')
    assert operation['colour'] == '#ffffff'
    url, share = removal_preview(image, operation)
    assert url.startswith('data:image/png;base64,')
    # The white around the ball goes; the highlight inside the ball (about 1 %) stays.
    assert .55 < share < .8


def test_change_endpoints_explain_then_make_only_that_change(tmp_path):
    app = create_app(tmp_path)
    client = app.test_client()
    fireball().save(tmp_path / 'work/uploads/fire.png')
    assert client.post('/api/auto-digitize/fire.png/change', json=dict(text='remove the white')).status_code == 409
    assert client.post('/api/auto-digitize/fire.png', json=dict(goes_on='cap', request='3 colours')).status_code == 202
    for _ in range(600):
        job = client.get('/api/auto-digitize/fire.png').get_json()
        if job['state'] != 'running':
            break
        time.sleep(.5)
    assert job['result'].get('stitches'), job
    said = client.post('/api/auto-digitize/fire.png/change',
                       json=dict(text='Remove the white background, keep only the ball on fire')).get_json()
    assert said['understood'][0].startswith('Leave out the white background (') and said['preview']
    assert client.post('/api/auto-digitize/fire.png/change/apply', json=dict(text='')).status_code == 400
    reply = client.post('/api/auto-digitize/fire.png/change/apply', json=dict(text='remove the white background'))
    assert reply.status_code == 202
    for _ in range(600):
        job = client.get('/api/auto-digitize/fire.png').get_json()
        if job['state'] != 'running':
            break
        time.sleep(.5)
    # The first request and the taps are kept; the change comes after them.
    assert job['changes'] == ['remove the white background'] and job['choices'] == {'fabric': 'cap'}
    assert job['request'] == '3 colours\nThen: remove the white background'
    assert any('Leaving out the white background' in s['text'] for s in job['steps'])
    assert job['result'].get('stitches')
