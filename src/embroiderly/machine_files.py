"""Shared serialization boundary; DST uses explicit PES readback trims.

The DST convention is pyembroidery trim_at=3: three small, net-zero jumps.
Machine trim settings must match this convention; it is not a universal machine
compatibility guarantee. PES/PEC can add trims to input jumps, hence readback is
the canonical command stream instead of two independently normalized plans.
"""
from pathlib import Path
import math
import pyembroidery as emb

DST_SETTINGS = {'trim_at': 3, 'explicit_trim': False, 'tie_on': False, 'tie_off': False}


def write_pair(pattern, pes, dst, pes_settings=None, *, repair_spacing=False):
    pes, dst = Path(pes), Path(dst)
    emb.write_pes(pattern, str(pes), {'full_jump': False, **(pes_settings or {})})
    canonical = emb.EmbPattern(str(pes))
    spacing_report = None
    if repair_spacing:
        from .stitch_spacing import repair
        from .release_gate import MIN_STITCH_MM, MAX_STITCH_MM
        spacing_report = repair(canonical, MIN_STITCH_MM, MAX_STITCH_MM)
        if spacing_report['straight_runs']:
            emb.write_pes(canonical, str(pes), {'encode': False, **(pes_settings or {})})
            canonical = emb.EmbPattern(str(pes))
    # Preserve even redundant explicit cuts after colour changes. The generic
    # normalizer discards those. Split only travel for DST's 12.1 mm axes limit.
    transport = canonical.copy()
    # PES v6 invents an Untitled label; preserve the caller's original metadata.
    transport.extras = pattern.extras.copy()
    transport.stitches = []
    previous = (0, 0)
    for x, y, command in canonical.stitches:
        if command & emb.COMMAND_MASK == emb.JUMP:
            count = max(1, math.ceil(max(abs(x-previous[0]), abs(y-previous[1]))/121))
            for i in range(1, count+1):
                transport.stitches.append([round(previous[0]+(x-previous[0])*i/count),
                                           round(previous[1]+(y-previous[1])*i/count), command])
        else:
            transport.stitches.append([x, y, command])
        previous = (x, y)
    emb.write_dst(transport, str(dst), {**DST_SETTINGS, 'encode': False})
    decoded = read_pattern(dst)
    if decoded.count_stitch_commands(emb.TRIM) != canonical.count_stitch_commands(emb.TRIM):
        raise ValueError('Export blocked: DST and PES disagree about thread cuts; review this design.')
    if spacing_report is not None:canonical.extras['spacing_repair']=spacing_report
    return canonical


def read_pattern(path):
    """Decode our explicit DST cut convention, including cuts after colour changes.

    pyembroidery's default heuristic suppresses these when already 'trimmed'.
    Recognize only the actual three-jump signature, never guess from distance.
    """
    if Path(path).suffix.lower() != '.dst':
        return emb.EmbPattern(str(path))
    pattern = emb.EmbPattern(str(path), settings={'trim_at': None, 'clipping': False})
    result=[]; previous=[0, 0]; i=0
    while i < len(pattern.stitches):
        seq=pattern.stitches[i:i+3]
        expected=[[previous[0]+2,previous[1]+2],[previous[0]-2,previous[1]-2],previous]
        if len(seq)==3 and all(s[2]&emb.COMMAND_MASK==emb.JUMP and s[:2]==p for s,p in zip(seq,expected)):
            result.append([*previous,emb.TRIM]);i+=3
        else:
            result.append(pattern.stitches[i]);previous=pattern.stitches[i][:2];i+=1
    pattern.stitches=result
    return pattern
