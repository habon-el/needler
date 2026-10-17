import json
import numpy as np
import pytest
from PIL import Image,ImageDraw
from embroiderly.web import create_app
from embroiderly.photo_stitch import generate,verify_file
from embroiderly.portrait import proposal


def test_oblique_portrait_exports_with_safe_pec_entries(tmp_path):
    path=tmp_path/'diagonal.png';image=Image.new('RGBA',(60,60),'red')
    ImageDraw.Draw(image).rectangle((30,0,59,59),fill='blue');image.save(path)
    result=generate(path,tmp_path/'out',25,{'photo_angle':31})
    for ext in ('pes','dst'):assert verify_file(tmp_path/'out'/('design.'+ext))['violations']==0
    audit=result['portrait_audit']
    assert 0<audit['max_written_penetration_mm']<=.6
    for overlap in audit['overlaps']:
        assert overlap['written_left_mm']<=overlap['limit_mm']
        assert overlap['written_right_mm']<=overlap['limit_mm']


def test_portrait_proposal_does_not_apply_settings(tmp_path):
    client=create_app(tmp_path).test_client()
    Image.new('RGBA',(40,40),'red').save(tmp_path/'work/uploads/p.png')
    r=client.post('/portrait/p.png',json={'options':{'count':4},'action':'propose'})
    assert r.status_code==200,r.json
    assert r.json['patch']['count']==10
    assert not (tmp_path/'work/decisions/p.png.preparation.json').exists()
    assert not list((tmp_path/'work/uploads').glob('prepared_*.png'))


def test_bad_portrait_feature_is_rejected(tmp_path):
    client=create_app(tmp_path).test_client()
    Image.new('RGBA',(40,40),'red').save(tmp_path/'work/uploads/p.png')
    for feature in ({'kind':'mouth','bounds':[0,0,100,100]},{'kind':'made-up','bounds':[0,0,10,10]}):
        result=client.post('/artwork/p.png',json={'options':{**proposal(),'portrait_features':[feature]}})
        assert result.status_code==400


def test_missing_detector_keeps_manual_mode_available(tmp_path,monkeypatch):
    import cv2,skimage.feature
    from embroiderly.portrait import detect_portrait
    monkeypatch.delattr(cv2,'CascadeClassifier',raising=False)
    def missing(*args,**kwargs):raise OSError('Unavailable')
    monkeypatch.setattr(skimage.feature,'Cascade',missing)
    assert detect_portrait(Image.new('RGB',(50,50),'red'))['likely'] is False


def test_invalid_portrait_size_does_not_publish_files(tmp_path):
    # Constraint guard is also applied to files supplied independently of the planner.
    import pyembroidery as emb
    path=tmp_path/'bad.pes';pattern=emb.EmbPattern();pattern.add_thread('#ff0000')
    pattern.add_stitch_absolute(emb.STITCH,10,0)
    pattern.add_stitch_absolute(emb.STITCH,10,0)
    emb.write_pes(pattern,str(path),{'version':6,'full_jump':False})
    with pytest.raises(ValueError):verify_file(path)
