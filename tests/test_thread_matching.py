import pytest
from embroiderly.thread_matching import colour_distance, rank_threads

def test_published_ciede2000_reference_pairs():
    # Sharma, Wu & Dalal supplementary test data, rows 1 and 2.
    assert colour_distance([50,2.6772,-79.7751],[50,0,-82.7485])==pytest.approx(2.0425,abs=0.00005)
    assert colour_distance([50,3.1571,-77.2803],[50,0,-82.7485])==pytest.approx(2.8615,abs=0.00005)

def test_rankings_are_explicit_deterministic_and_exact_match_first(tmp_path):
    p=tmp_path/"catalogue.gpl"
    p.write_text("GIMP Palette\nName: test\n255 0 0 Red 100\n0 0 255 Blue 200\n254 3 1 Near Red 300\n")
    a=rank_threads("#ff0000",p)
    assert a==rank_threads("#ff0000",p)
    assert a[0]["code"]=="100" and a[0]["delta_e"]==0
    assert a[0]["method"]=="CIEDE2000"
    assert len(a)==3

def test_missing_catalogue_is_optional(tmp_path):
    assert rank_threads("#ff0000",tmp_path/"missing.gpl")==[]
