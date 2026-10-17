import xml.etree.ElementTree as ET
import numpy as np
import pyembroidery as emb
import pytest
from embroiderly.generation_policy import apply
from embroiderly.repair_pipeline import propose
from embroiderly.release_gate import check_pattern,ReleaseError


def test_explicit_generation_settings_and_cuts():
    root=ET.Element('svg');ET.SubElement(root,'metadata')
    p=ET.SubElement(root,'path',style='fill:#000000;stroke:none')
    result=apply(root,{})
    ns='{http://inkstitch.org/namespace}'
    assert p.get(ns+'min_stitch_length_mm')=='0.45'
    assert p.get(ns+'row_spacing_mm')=='0.4'
    assert p.get(ns+'trim_after')=='true'
    assert result['collapse_len_mm']==0
    with pytest.raises(ValueError,match='Unlock'):
        apply(root,{'piece_edits':{'a':{'locked':True}}})


def test_all_violations_reported_without_weakening_gate():
    p=emb.EmbPattern();p.stitches=[[10,10,emb.JUMP],[10,10,0],[12,10,0],[50,10,0]]
    mask=np.ones((100,100),bool);mask[:,25:40]=False
    with pytest.raises(ReleaseError) as caught:check_pattern(p,mask,.1,[0,0])
    assert {i['code'] for i in caught.value.issues}=={'short','crossing'}
    assert {i['location']['command'] for i in caught.value.issues}=={2,3}


def test_lock_points_never_deleted_and_unsafe_candidate_not_automatic():
    p=emb.EmbPattern();p.stitches=[[10,10,emb.JUMP],[10,10,0],[12,10,0],[10,10,0],[12,10,0],[10,10,0],[30,10,0],[30,10,emb.END]]
    candidate,report=propose(p,np.ones((100,100),bool),.1,[0,0])
    assert candidate.stitches==p.stitches
    assert not report['automatic'] and report['issues']
