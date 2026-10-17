from embroiderly.thread_recolour import colour_mapping

def svg(path,colours,paths=('M 0,0 L 5,0 L 5,5 Z','M 10,0 L 15,0 L 15,5 Z'),height=20):
    path.write_text(f'<svg width="20mm" height="{height}mm" viewBox="0 0 20 20">'+''.join(f'<path d="{d}" style="fill:{c};fill-rule:evenodd;stroke:none"/>' for c,d in zip(colours,paths))+'</svg>')

def test_pure_colour_change_maps_without_route_order_dependency(tmp_path):
    a=tmp_path/'a.svg';b=tmp_path/'b.svg'
    svg(a,['#000000','#ff0000']);svg(b,['#ffffff','#00ff00'])
    assert colour_mapping(a,b)=={'#000000':'#ffffff','#ff0000':'#00ff00'}

def test_merges_size_changes_and_shape_changes_require_generation(tmp_path):
    a=tmp_path/'a.svg';b=tmp_path/'b.svg'
    svg(a,['#000000','#ff0000']);svg(b,['#ffffff','#ffffff'])
    assert colour_mapping(a,b) is None
    svg(b,['#ffffff','#00ff00'],height=30)
    assert colour_mapping(a,b) is None
    svg(b,['#ffffff','#00ff00'],paths=('M 0,0 L 6,0 L 5,5 Z','M 10,0 L 15,0 L 15,5 Z'))
    assert colour_mapping(a,b) is None
