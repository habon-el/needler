"""Ask AI on the Text page, with a scripted stand-in for Claude (no network, no cost)."""
from types import SimpleNamespace as NS

import pytest

from embroiderly import text_ai

START = dict(text='God Great', font='pacifico', height_mm=31.2, available_width_mm=50, align='center',
             colour='#202020', baseline='straight')


class Script:
    """Answers with the given tool calls, one response per turn; records what Claude was shown."""
    def __init__(self, *turns):
        self.turns, self.seen = list(turns), []
        self.messages = self

    def create(self, **request):
        self.seen.append(request['messages'][-1]['content'])
        calls = [NS(type='tool_use', id=f'call{len(self.seen)}{i}', name=name, input=args)
                 for i, (name, args) in enumerate(self.turns.pop(0))]
        usage = NS(input_tokens=1000, output_tokens=200, cache_creation_input_tokens=0, cache_read_input_tokens=0)
        return NS(content=calls, stop_reason='tool_use', usage=usage)


def test_claude_checks_then_finishes_and_the_check_reports_problems(tmp_path):
    first = dict(shape='arc_under', curve_degrees=90, puff=True)
    script = Script([('check_text', dict(settings=first))],
                    [('finish', dict(settings=dict(first, font='russo_one', height_mm=20, max_width_mm=150),
                                     note='Curved down, bold font for puff.'))])
    values, note, left, usd = text_ai.ask('curve it down and make it 3D puff', START, tmp_path, client=script)
    # The first check told Claude that Pacifico cannot puff, with the fix.
    assert 'cannot be 3D puff' in script.seen[1][0]['content'] and 'russo_one' in script.seen[1][0]['content']
    assert values['font'] == 'russo_one' and values['baseline'] == 'arc_under' and values['arc_degrees'] == 90
    assert values['puff'] is True and values['puff_foam_mm'] == 3 and values['text'] == 'God Great'
    assert note.startswith('Curved down') and left == [] and usd > 0
    assert (tmp_path/'claude-spend.json').is_file()


def test_problems_claude_leaves_are_fixed_by_the_check(tmp_path):
    script = Script([('finish', dict(settings=dict(font='russo_one', puff=True), note='Puff.'))])
    values, _, left, _ = text_ai.ask('3D puff', START, tmp_path, client=script)
    # Height and width were out of range: the check's own fixes were applied.
    assert left == [] and 17 <= values['height_mm'] <= 24 and values['available_width_mm'] > 50


def test_requests_are_checked(tmp_path):
    with pytest.raises(ValueError):
        text_ai.ask('', START, tmp_path, client=Script())
    (tmp_path/'claude-spend.json').write_text('{"usd": 99}')
    with pytest.raises(ValueError, match='limit'):
        text_ai.ask('curve it', START, tmp_path, client=Script())


def test_claude_can_choose_a_full_circle_and_a_fixed_length(tmp_path):
    names = {t['name']: t for t in text_ai.tools(['graduate'], ['twill'])}
    shape = names['check_text']['input_schema']['properties']['settings']['properties']
    assert {'circle', 'wave'} <= set(shape['shape']['enum']) and 'fixed_length_mm' in shape
    script = Script([('finish', dict(settings=dict(text='TEAM\nSINCE 99', font='graduate', height_mm=8,
                                                   shape='circle', max_width_mm=120), note='Round a circle.'))])
    values, _, left, _ = text_ai.ask('put it round a circle', START, tmp_path, client=script)
    assert values['baseline'] == 'circle' and values['circle_mm'] == 60 and 'arc_degrees' not in values
    assert left == []
    script = Script([('finish', dict(settings=dict(font='graduate', text='CHAMPIONS', height_mm=8, shape='wave',
                                                   fixed_length_mm=70, max_width_mm=120), note='Wave, 70 mm.'))])
    values, _, left, _ = text_ai.ask('a wave, exactly 70 mm long', START, tmp_path, client=script)
    assert values['wave_percent'] == 6 and values['fit_length_mm'] == 70 and left == []
