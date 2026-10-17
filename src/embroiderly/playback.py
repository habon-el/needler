"""Experimental image-path export and playback of the actual written DST."""
from math import ceil, hypot
import json
import pyembroidery as emb
from .model import Command, CommandKind as K, Design, Thread
from .export import export_design, read_written_commands


def build_playback(paths, directory, scale):
    commands, threads = [], []
    previous = (0.0, 0.0)
    colour = None
    for path in paths:
        if path.kind != 'sewn' or len(path.points) < 2:
            continue
        points = [(x * scale, y * scale) for x, y in path.points]
        continuous = bool(commands) and path.colour == colour and points[0] == previous
        if path.colour != colour:
            if colour is not None:
                commands.append(Command(K.COLOR_CHANGE, *previous))
            threads.append(Thread(path.colour))
            colour = path.colour
        elif commands and not continuous:
            commands.append(Command(K.TRIM, *previous))
        if not continuous:
            commands.append(Command(K.JUMP, *points[0]))
        previous = points[0]
        for target in points[1:]:
            start = previous
            parts = max(1, ceil(hypot(target[0]-start[0], target[1]-start[1]) / 3))
            for i in range(1, parts+1):
                point = tuple(start[j] + (target[j]-start[j])*i/parts for j in (0, 1))
                commands.append(Command(K.STITCH, *point))
            previous = target
    if not commands:
        payload = {'steps': [], 'colors': [], 'stitch_count': 0, 'trim_count': 0}
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'playback.json').write_text(json.dumps(payload))
        return payload
    result = export_design(Design(tuple(commands), tuple(threads)), directory, 'experimental')
    types = {emb.STITCH:'stitch', emb.JUMP:'jump', emb.TRIM:'trim', emb.COLOR_CHANGE:'color_change', emb.END:'end'}
    steps = [{'x': x/10, 'y': y/10, 't': types.get(flags & emb.COMMAND_MASK, 'unknown')}
             for x, y, flags in read_written_commands(result.dst_path)]
    # DST does not embed RGB threads: persist the ordered export palette with
    # a digest binding it to this exact written stream.
    import hashlib
    colour_index = 0
    for step in steps:
        if step['t'] == 'color_change':
            colour_index += 1
        if colour_index >= len(threads):
            raise ValueError('Written colour sequence exceeds the export palette')
        step['color'] = threads[colour_index].hex
    if sum(s['t']=='color_change' for s in steps) != len(threads)-1:
        raise ValueError('Written colour changes disagree with thread list')
    payload = {'source_sha256': hashlib.sha256(result.dst_path.read_bytes()).hexdigest(),
               'steps': steps, 'colors': [t.hex for t in threads],
               'stitch_count': sum(s['t']=='stitch' for s in steps),
               'trim_count': sum(s['t']=='trim' for s in steps)}
    (directory / 'playback.json').write_text(json.dumps(payload, separators=(',', ':')))
    return payload
