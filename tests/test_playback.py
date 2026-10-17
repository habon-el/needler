from embroiderly.playback import build_playback
from embroiderly.simulation import PreviewSegment
from embroiderly.export import read_written_commands
import pyembroidery as emb


def test_playback_matches_written_file(tmp_path):
    paths = [PreviewSegment(((0,0),(20,0)), '#000000', 'sewn'),
             PreviewSegment(((30,10),(40,10)), '#ff0000', 'sewn')]
    payload = build_playback(paths, tmp_path, 0.5)
    stream = read_written_commands(tmp_path / 'experimental.dst')
    assert len(payload['steps']) == len(stream)
    assert payload['stitch_count'] == sum(c & emb.COMMAND_MASK == emb.STITCH for x,y,c in stream)
    assert payload['trim_count'] == sum(c & emb.COMMAND_MASK == emb.TRIM for x,y,c in stream)
    assert payload['colors'] == ['#000000', '#ff0000']
    assert [(s['x'],s['y']) for s in payload['steps']] == [(x/10,y/10) for x,y,c in stream]
