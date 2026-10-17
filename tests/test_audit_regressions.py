import json
from embroiderly.model import Command, CommandKind as K, Design, Thread
from embroiderly.export import export_design
from embroiderly.audit import audit_file
from embroiderly.playback import build_playback
from embroiderly.simulation import PreviewSegment


def test_first_sewn_move_after_jump_is_measured(tmp_path):
    design=Design((Command(K.JUMP,0,0),Command(K.STITCH,2,0)),(Thread('#000000'),))
    result=export_design(design,tmp_path,'move')
    assert audit_file(result.dst_path).max_stitch_mm == 2


def test_empty_selection_updates_saved_playback(tmp_path):
    build_playback([PreviewSegment(((0,0),(10,0)),'#000000','sewn')],tmp_path,1)
    build_playback([],tmp_path,1)
    assert json.loads((tmp_path/'playback.json').read_text())['stitch_count']==0
