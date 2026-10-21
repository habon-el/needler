from copy import deepcopy
import json
import numpy as np
from PIL import Image
import pytest
from embroiderly.piece_layout import inventory, change, guard
from embroiderly.region_stitches import inventory as region_inventory
from embroiderly.preparation import prepare


def sample():
    rgb=np.zeros((400,400,3),np.uint8)
    alpha=np.zeros((400,400),bool);alpha[80:281,80:281]=True
    options={'height_mm':80,'floor_mm2':1,'smooth':0,'mask_holes_mm2':0,'count':2}
    regions=region_inventory(rgb,alpha,.2,options)
    return regions,options


def test_resize_is_outline_transform_with_stable_identity_and_real_bounds():
    regions,o=sample();before=inventory(regions,o,400,400,.2);p=before['pieces'][0]
    assert p['width_mm']==40 and p['height_mm']==40
    updated=change(o,before,dict(ids=[p['id']],field='width_mm',value=20,linked=True))
    after=inventory(regions,updated,400,400,.2)['pieces'][0]
    assert after['id']==p['id'] and after['width_mm']==after['height_mm']==20
    assert after['area_mm2']==p['area_mm2']/4
    assert after['nodes']==p['nodes']
    assert 'stitches' not in updated


def test_lock_blocks_edit_hide_style_and_global_assistant_patch():
    regions,o=sample();r=inventory(regions,o,400,400,.2);key=r['pieces'][0]['id']
    locked=change(o,r,dict(ids=[key],field='locked',value=True));r=inventory(regions,locked,400,400,.2)
    for field,value in [('width_mm',20),('name','Nose'),('visible',False),('style','satin')]:
        with pytest.raises(ValueError,match='locked'):change(locked,r,dict(ids=[key],field=field,value=value))
    with pytest.raises(ValueError,match='locked'):guard(locked,{**locked,'height_mm':40})
    with pytest.raises(ValueError,match='locked'):guard(locked,o)
    assert not change(locked,r,dict(ids=[key],field='locked',value=False))['piece_edits'][key]['locked']


def test_tiny_piece_is_red_not_removed_and_rotation_keeps_centre():
    regions,o=sample();r=inventory(regions,o,400,400,.2);p=r['pieces'][0]
    tiny=change(o,r,dict(ids=[p['id']],field='width_mm',value=.5))
    after=inventory(regions,tiny,400,400,.2)['pieces'][0]
    assert after['audit']['level']=='red' and after['area_mm2']==.25
    rotated=change(o,r,dict(ids=[p['id']],field='rotation',value=33))
    p2=inventory(regions,rotated,400,400,.2)['pieces'][0]
    assert p2['x_mm']==pytest.approx(p['x_mm']) and p2['y_mm']==pytest.approx(p['y_mm'])
    moved=change(o,r,dict(ids=[p['id']],field='position',value=[-13.1,-45]))
    p3=inventory(regions,moved,400,400,.2)['pieces'][0]
    assert p3['x_mm']==pytest.approx(-13.1) and p3['y_mm']==pytest.approx(-45)
    assert p3['audit']['outside_hoop']


def test_stale_identity_rejected_not_reassigned():
    regions,o=sample();r=inventory(regions,o,400,400,.2);key=r['pieces'][0]['id']
    named=change(o,r,dict(ids=[key],field='name',value='Nose'))
    with pytest.raises(ValueError,match='shapes changed'):inventory({**regions,'areas':[]},named,400,400,.2)


@pytest.mark.parametrize('value',[float('nan'),float('inf'),None,'20',0,-1])
def test_invalid_sizes_rejected(value):
    regions,o=sample();r=inventory(regions,o,400,400,.2)
    with pytest.raises(ValueError):change(o,r,dict(ids=[r['pieces'][0]['id']],field='width_mm',value=value))


def make_image(path):
    rgba=np.zeros((400,400,4),np.uint8);rgba[80:281,80:281]=[30,70,140,255]
    Image.fromarray(rgba).save(path)


def test_real_regeneration_and_exact_undo(tmp_path):
    from embroiderly.engine import digitize
    source=tmp_path/'source.png';make_image(source);_,o=sample()
    image,_,report=prepare(source,o)
    piece=report['piece_layout']['pieces'][0]
    def generate(options,folder):
        image,_,report=prepare(source,options);path=tmp_path/(folder+'.png');image.save(path)
        path.with_suffix('.prep.json').write_text(json.dumps(dict(options=options,report=report)))
        plan=digitize(path,tmp_path/folder,80)
        return plan,{ext:(tmp_path/folder/('design.'+ext)).read_bytes() for ext in ('pes','dst')}
    before,files=generate(o,'before')
    smaller=change(o,report['piece_layout'],dict(ids=[piece['id']],field='width_mm',value=20))
    after,_=generate(smaller,'after')
    ratio=after['stitch_count']/before['stitch_count']
    assert .2<ratio<.4,(before['stitch_count'],after['stitch_count'])
    restored,undo=generate(o,'undo');assert undo==files
    named=change(o,report['piece_layout'],dict(ids=[piece['id']],field='name',value='Nose'))
    _,named_files=generate(named,'named');assert named_files==files
    moved=change(o,report['piece_layout'],dict(ids=[piece['id']],field='position',value=[10,-10]))
    placed,_=generate(moved,'moved')
    sewn=[s for s in placed['steps'] if s['t']=='stitch']
    assert (min(s['x'] for s in sewn)+max(s['x'] for s in sewn))/2==pytest.approx(10,abs=.11)
    assert (min(s['y'] for s in sewn)+max(s['y'] for s in sewn))/2==pytest.approx(-10,abs=.11)
    def spacing(plan):
        # Fills run along each shape's long side: measure across the rows, whatever their angle.
        import math
        pairs=[(a,s) for a,s in zip(plan['steps'],plan['steps'][1:]) if a['t']==s['t']=='stitch']
        angles=[round(math.degrees(math.atan2(s['y']-a['y'],s['x']-a['x']))%180) for a,s in pairs if math.hypot(s['x']-a['x'],s['y']-a['y'])>1]
        turn=-math.radians(max(set(angles),key=angles.count))
        rot=lambda p:(p['x']*math.cos(turn)-p['y']*math.sin(turn),p['x']*math.sin(turn)+p['y']*math.cos(turn))
        ys=sorted({round(rot(s)[1],2) for a,s in pairs if abs(rot(s)[1]-rot(a)[1])<.02 and abs(rot(s)[0]-rot(a)[0])>1})
        differences=[round(b-a,1) for a,b in zip(ys,ys[1:]) if b-a>.1]
        return float(np.median(differences))
    before_spacing,after_spacing=spacing(before),spacing(after)
    # User-approved twill generation preset replaces implicit 0.25 mm rows.
    assert .35<=before_spacing<=.45 and .35<=after_spacing<=.45
    print(json.dumps(dict(before=before['stitch_count'],after=after['stitch_count'],ratio=ratio,undo_exact=True,
                         before_row_spacing_mm=before_spacing,after_row_spacing_mm=after_spacing)))

