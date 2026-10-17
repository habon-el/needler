from embroiderly.playback import build_playback
from embroiderly.simulation import PreviewSegment


def test_touching_paths_continue_without_cut(tmp_path):
    paths=[PreviewSegment(((0,0),(10,0)),'#000000','sewn'),
           PreviewSegment(((10,0),(10,10)),'#000000','sewn')]
    result=build_playback(paths,tmp_path,1)
    assert result['trim_count']==0


def test_gap_keeps_cut_and_travel(tmp_path):
    paths=[PreviewSegment(((0,0),(10,0)),'#000000','sewn'),
           PreviewSegment(((20,0),(20,10)),'#000000','sewn')]
    result=build_playback(paths,tmp_path,1)
    assert result['trim_count']>=1
    assert any(s['t']=='jump' and s['x']==20 for s in result['steps'])
