from PIL import Image
from embroiderly.advisors import lookup
from embroiderly.assistance import local_edit
from embroiderly.knowledge_messages import message
from embroiderly.knowledge_store import load_knowledge


def test_cap_existing_value_wins_over_unconfirmed_seed():
    row,citation=lookup(load_knowledge(),'placements.json','cap.front')
    assert row['height_range_mm']==[0,55]
    assert row['previous_value']['value']==55
    assert row['previous_value']['line']==78
    assert row['previous_value']['file']=='src/embroiderly/assistance.py'
    assert row['previous_value']['date_of_swap']=='2026-09-21'
    assert row['proposed_seed_value']['value']==50
    assert not row['verified_by_user'] and citation['unconfirmed_seed_difference']
    patch,reason=local_edit('fit a cap',{'selection':'full'},Image.new('RGBA',(40,40),'red'))
    assert patch['height_mm']==55
    assert 'Unconfirmed seed difference' in reason


def test_each_legacy_replacement_has_complete_previous_value():
    rows=load_knowledge()['legacy.json']['rows']
    assert len(rows)==19
    for row in rows:
        prior=row['previous_value']
        assert prior['value']==row['text']
        assert prior['file'].startswith('src/embroiderly/') and prior['line']>0
        assert prior['date_of_swap']=='2026-09-22'
        assert isinstance(prior['numeric_literals'],list)
        assert not row['verified_by_user']


def test_message_interpolation_keeps_measurements_and_cites_assumption():
    text=message('refinement.10',v0=.5)
    assert '0.500 mm' in text and '1 mm' in text
    assert 'legacy.json#refinement.10 v1' in text and 'not shop-verified' in text
