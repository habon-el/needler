from PIL import Image
from embroiderly.photo_stitch import generate


def test_marked_feature_coverage_uses_exported_threads(tmp_path):
    source=tmp_path/'prepared.png'
    Image.new('RGBA',(40,40),'red').save(source)
    plan=generate(source,tmp_path/'export',20,{
        'portrait_features':[{'kind':'mouth','bounds':[10,10,30,30]}]})
    assert plan['thread_width_mm']==.4
    feature=plan['portrait_audit']['feature_coverage'][0]
    assert feature['selected_pixels']==400
    assert 0<feature['covered_pixels']<=400
    assert feature['visible_thread_colours']==1
    assert feature['kind']=='mouth'
