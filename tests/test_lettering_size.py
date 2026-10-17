import json
import pytest
from PIL import Image
from embroiderly.lettering import catalogue
from embroiderly.lettering_size import source_metrics, saved_metrics, width_fit
from embroiderly.web import create_app


def recipe(text):
    font=next(f for f in catalogue().values() if f['family']=='DejaVu Sans' and f['style']=='Book')
    return dict(text=text,font=font['id'],height_mm=25,spacing=0,align='center')


def test_capital_is_not_multiline_block_height():
    single=source_metrics(recipe('H'))
    multi=source_metrics(recipe('Hello\nWorld\nHello\nWorld'))
    assert single['capital_per_canvas_mm']==pytest.approx(1/1.08)
    assert multi['capital_per_canvas_mm']<.2
    assert multi['line_count']==4
    # Recipe height is not the current edited canvas height.
    taller=source_metrics({**recipe('Hello\nWorld\nHello\nWorld'),'height_mm':80})
    assert multi==taller


def test_width_fit_does_not_resize():
    assert width_fit(37,50)==dict(actual_width_mm=37,available_width_mm=50,fits=True,overflow_mm=0,resized=False)
    result=width_fit(97.8,50)
    assert not result['fits'] and result['overflow_mm']==47.8
    assert result['actual_width_mm']==97.8 and not result['resized']


@pytest.mark.parametrize('width',[0,4.9,401,float('nan'),float('inf')])
def test_invalid_width(width):
    with pytest.raises(ValueError):width_fit(37,width)


def test_workspace_metrics_are_read_only(tmp_path):
    client=create_app(tmp_path).test_client()
    name='lettering-'+'c'*32+'.png'
    source=tmp_path/'work/uploads'/name
    Image.new('RGBA',(310,100),'black').save(source)
    r=tmp_path/'work/decisions'/(name+'.lettering.json')
    r.write_text(json.dumps(recipe('Hello\nWorld')))
    before=source.read_bytes(),r.read_bytes()
    html=client.get('/artwork/'+name).get_data(as_text=True)
    assert 'window.letteringSizeMetrics=' in html and 'capital_per_canvas_mm' in html
    assert '/static/design-size.js' in html
    preview=client.post('/lettering/preview',json=recipe('Hello\nWorld')).get_json()
    assert preview['size']['line_count']==2
    assert 0<preview['size']['reference_capital_mm']<preview['size']['height_mm']
    assert before==(source.read_bytes(),r.read_bytes())
    assert saved_metrics(r.parent,'photo.png') is None
    r.write_text('{}')
    assert saved_metrics(r.parent,name)['unavailable']
