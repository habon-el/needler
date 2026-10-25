"""Text advice: every problem with the text settings at once, each with a one-click fix."""
import pytest

from embroiderly import small_lettering as sl

PUFF = dict(puff=True, puff_foam_mm=3)


def advice(**body):
    return sl.advice(dict(dict(text='God Great', font='russo_one', height_mm=20, available_width_mm=200), **body))


def fixes(result):
    return [p['fix']['set'] for p in result['problems'] if 'fix' in p]


def test_settings_that_work_have_no_problems():
    assert advice()['problems'] == []
    assert advice(**PUFF)['problems'] == []


def test_a_thin_font_for_puff_gets_a_bold_font_as_the_fix():
    result = advice(font='pacifico', **PUFF)
    assert fixes(result) == [{'font': 'russo_one'}]
    assert 'russo_one' in result['puff_fonts'] and 'pacifico' not in result['puff_fonts']


def test_all_problems_are_listed_together_with_fixes_that_work():
    body = dict(text='God Great', font='russo_one', height_mm=31.2, available_width_mm=50, **PUFF)
    result = sl.advice(body)
    assert len(result['problems']) == 2   # height and width, in one answer
    for values in fixes(result):
        body.update(values)
    assert sl.advice(body)['problems'] == []


def test_curved_text_needs_one_line():
    result = advice(text='God\nGreat', baseline='arc_over', arc_degrees=90)
    assert {'baseline': 'straight'} in fixes(result)


@pytest.mark.parametrize('extra', [{}, dict(baseline='arc_over', arc_degrees=140), dict(baseline='arc_under', arc_degrees=60)])
def test_width_comes_from_the_laid_out_letters(extra):
    body = dict(text='CHAMPIONS', font='graduate', height_mm=10, available_width_mm=300, colour='#202020', **extra)
    from embroiderly import lettering_native as ln
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as folder:
        real = ln.build(Path(folder), ln.recipe(body))['reports']['dst']['width_mm']
    assert sl.laid_out_width(body) == pytest.approx(real, abs=.6)
    too_narrow = sl.advice(dict(body, available_width_mm=real-5))
    assert {'available_width_mm': pytest.approx(real+2, abs=1.5)} == too_narrow['problems'][0]['fix']['set']


def test_thread_names_for_the_text_colour(tmp_path):
    from embroiderly.web import create_app
    client = create_app(tmp_path).test_client()
    threads = client.get('/lettering/native/thread?hex=%23000000').get_json()['threads']
    assert len(threads) == 3 and threads[0]['delta_e'] == 0 and threads[0]['hex'] == '#000000'
    assert client.get('/lettering/native/thread?hex=black').status_code == 400
    advice = client.post('/lettering/native/advice', json=dict(text='God Great', font='pacifico', height_mm=20,
                                                               available_width_mm=200, puff=True, puff_foam_mm=3)).get_json()
    assert advice['problems'][0]['fix']['set'] == {'font': 'russo_one'}


def test_fixed_length_and_shape_problems_come_with_fixes_that_work():
    body = dict(text='CHAMPIONS', font='graduate', height_mm=8, available_width_mm=300, fit_length_mm=20)
    result = sl.advice(body)
    assert 'overlap' in result['problems'][0]['message']
    body.update(fixes(result)[0])
    assert 40 < body['fit_length_mm'] < 80 and sl.advice(body)['problems'] == []
    assert {'fit_length_mm': ''} in fixes(sl.advice(dict(body, text='CHAMP\nIONS')))
    # A full circle takes a second line along the bottom; a wave that bends too far gets a gentler one.
    circle = dict(body, text='TEAM\nSINCE 99', baseline='circle', circle_mm=60, fit_length_mm='')
    assert sl.advice(circle)['problems'] == []
    assert sl.advice(dict(circle, text='A\nB\nC'))['problems']
    wave = dict(circle, text='CHAMPIONS', baseline='wave', wave_percent=20)
    gentler = fixes(sl.advice(wave))
    assert gentler and gentler[0]['wave_percent'] < 20
