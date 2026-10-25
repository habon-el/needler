"""Find a valid stitch plan for current artwork, never an unrelated older edit."""
from .preparation_identity import preparation_key
import json
import math
from pathlib import Path

DEFAULTS = dict(region_styles={}, ink_only=False, line_art=False, ink_length_mm=2, ink_bean_repeats=0, selection='full', count=4, brightness=1, contrast=1,
                height_mm=100, floor_mm2=1, simplify=0, smooth=1,
                mask_holes_mm2=1, mask_smooth=0, edge=0,
                hints=[], edits=[], locks=[], merges={})


def equivalent(a, b):
    def normalized(value):
        result={**DEFAULTS, **value}
        result.pop('interactions', None)  # UI history count is not stitch geometry.
        result.pop('canvas_guides', None)  # Nor are the canvas guides.
        return result
    return normalized(a)==normalized(b)


def read_plan(path):
    try:
        payload=json.loads(path.read_text())
        if not isinstance(payload,dict):return None
        steps=payload.get('steps');colours=payload.get('colors')
        if not isinstance(steps,list) or not steps or not isinstance(colours,list) or not colours:
            return None
        def valid_colour(value):
            return isinstance(value,str) and len(value)==7 and value[0]=='#' and all(c in '0123456789abcdefABCDEF' for c in value[1:])
        if not all(valid_colour(c) for c in colours):return None
        for step in steps:
            if not isinstance(step,dict) or step.get('t') not in {'stitch','jump','trim','color_change','end','unknown'}:
                return None
            if not valid_colour(step.get('color')):return None
            if any(type(step.get(axis)) not in (int,float) or not math.isfinite(step[axis]) for axis in ('x','y')):return None
        count=sum(s['t']=='stitch' for s in steps)
        if not count:return None
        origin=payload.get('origin_mm',[0,0])
        if not isinstance(origin,list) or len(origin)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in origin):return None
        payload.update(stitch_count=count,trim_count=sum(s['t']=='trim' for s in steps),origin_mm=origin)
        return payload
    except (OSError, ValueError, TypeError):
        return None


def matching_plan(root, source, options):
    root,source=Path(root),Path(source)
    source_bytes=source.read_bytes()
    key=preparation_key(source_bytes,options)
    name='prepared_'+key
    exact=read_plan(root/'work'/'inkstitch-preview'/name/'playback.json')
    if exact is not None:return dict(playback=exact,simulation='/engine/'+name+'.png?view=1')
    candidates=[]
    # Older plans may have an earlier interaction counter or omitted defaults.
    for path in (root/'work'/'uploads').glob('prepared_*.prep.json'):
        try:
            metadata=json.loads(path.read_text())
            if metadata.get('source')==source.name and equivalent(metadata.get('options',{}),options):
                stored=metadata['options']
                expected=preparation_key(source_bytes,stored)
                # Do not restore plans if the source bytes or preparation version changed.
                if path.name=='prepared_'+expected+'.prep.json':
                    candidates.append('prepared_'+expected)
        except (OSError,ValueError,TypeError,KeyError):
            continue
    for candidate in dict.fromkeys(candidates):
        payload=read_plan(root/'work'/'inkstitch-preview'/candidate/'playback.json')
        if payload is not None:
            return dict(playback=payload,simulation='/engine/'+candidate+'.png?view=1')
    return {}
