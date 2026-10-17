from pathlib import Path


def test_legacy_design_does_not_offer_unimplemented_foam_puff():
    page=(Path(__file__).parents[1]/'src/embroiderly/templates/design.html').read_text()
    assert 'id="puffOn"' not in page
    assert 'id="puffHeight"' not in page
    assert "el('puffOn')" not in page
    assert "el('puffHeight')" not in page
    assert 'Foam puff digitizing is not available' in page
