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

def test_builtin_machine_charts_need_no_installation():
    matches=rank_threads("#ffffff")
    assert len(matches)==3 and all(m["brand"] for m in matches)
    assert matches[0]["delta_e"]<2
    brother=rank_threads("#0a55a3",brands=["Brother"])
    assert brother[0]["brand"]=="Brother" and brother[0]["delta_e"]==0

def test_pcm_palette_is_read_from_pyembroidery():
    from embroiderly.thread_matching import CHARTS, chart
    assert len(CHARTS) == 6
    pcm = chart("Pfaff PCM")
    assert len(pcm) == 16 and pcm[0] == ((0, 0, 0), "PCM Color 1", "1") and pcm[-1][0] == (255, 255, 255)
    match = rank_threads("#808000", brands=["Pfaff PCM"], limit=1)[0]
    assert match["brand"] == "Pfaff PCM" and match["code"] == "12" and match["delta_e"] == 0

def test_every_chart_matches_on_its_own():
    from embroiderly.thread_matching import charts
    for name in charts():
        matches = rank_threads("#c03030", brands=[name])
        assert len(matches) == 3 and {m["brand"] for m in matches} == {name}
    assert rank_threads("#c03030", brands=["Nothing"]) == []

def test_text_page_thread_names_follow_the_chosen_chart(tmp_path):
    from embroiderly.web import create_app
    client = create_app(tmp_path).test_client()
    body = client.get("/lettering/native/thread?hex=%23123456&chart=Janome").get_json()
    assert {t["brand"] for t in body["threads"]} == {"Janome"} and "Pfaff PCM" in body["charts"]
    assert client.get("/lettering/native/thread?hex=%23123456&chart=Nope").status_code == 400
