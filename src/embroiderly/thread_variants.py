"""Non-destructive thread edits on a resolved stitch plan."""
import json,re,shutil
from pathlib import Path
from uuid import uuid4
import pyembroidery as emb
from flask import request,jsonify

def recolour_plan(payload,choices):
    palette=set(payload['colors'])
    if not isinstance(choices,dict) or set(choices)!=palette:raise ValueError('Provide a choice for each thread colour.')
    for choice in choices.values():
        if not isinstance(choice,dict) or type(choice.get('include')) is not bool or not isinstance(choice.get('thread'),str) or not re.fullmatch('#[0-9a-fA-F]{6}',choice['thread']):
            raise ValueError('Invalid thread selection.')
    out=emb.EmbPattern();previous=(0,0);active=None;connected=False;count=0
    for step in payload['steps']:
        point=(step['x']*10,step['y']*10);choice=choices[step['color']]
        if step['t']=='stitch' and choice['include']:
            colour=choice['thread'].lower()
            if active!=colour:
                if active is not None:out.trim();out.color_change()
                out.add_thread(colour);active=colour;connected=False
            if not connected:out.add_stitch_absolute(emb.JUMP,*previous)
            out.add_stitch_absolute(emb.STITCH,*point);connected=True;count+=1
        elif step['t']=='jump':
            if connected:out.add_stitch_absolute(emb.JUMP,*point)
        elif step['t']=='stitch' or step['t'] in ('trim','color_change'):
            if connected:out.trim()
            connected=False
        previous=point
    if not count:raise ValueError('Keep at least one colour with stitches.')
    out.end();return out

def register_thread_variants(app,root):
    @app.post('/thread-variant/<name>')
    def thread_variant(name):
        from .saved_plans import read_plan
        original=root/'work'/'uploads'/Path(name).name
        folder=root/'work'/'inkstitch-preview'/original.stem
        payload=read_plan(folder/'playback.json')
        if not original.is_file() or payload is None:return jsonify(error='Generate a stitch plan first.'),404
        try:pattern=recolour_plan(payload,request.get_json(silent=True))
        except (ValueError,KeyError,TypeError) as error:return jsonify(error=str(error)),400
        variant='threads-'+uuid4().hex
        target=root/'work'/'inkstitch-preview'/variant;target.mkdir()
        from .machine_files import write_pair
        write_pair(pattern,target/'design.pes',target/'design.dst',{'version':6})
        written=emb.EmbPattern(str(target/'design.pes'))
        colours=[t.hex_color() for t in written.threadlist];steps=[];index=0
        types={emb.STITCH:'stitch',emb.JUMP:'jump',emb.TRIM:'trim',emb.COLOR_CHANGE:'color_change',emb.END:'end'}
        for x,y,command in written.stitches:
            kind=types.get(command&emb.COMMAND_MASK,'unknown')
            if kind=='color_change':index+=1
            steps.append(dict(x=x/10,y=y/10,t=kind,color=colours[index]))
        result={**payload,'steps':steps,'colors':colours,'stitch_count':sum(s['t']=='stitch' for s in steps),'trim_count':sum(s['t']=='trim' for s in steps),'generation_mode':'thread selection variant'}
        if result.get('border'):
            choice=request.json.get(result['border']['colour'])
            if choice and choice['include']:result['border']={**result['border'],'colour':choice['thread']}
            elif choice:result.pop('border')
        from .release_gate import read_context,record_context,ReleaseError
        try:
            context,mask=read_context(folder)
            record_context(target,mask,context['scale'],context['origin'])
        except ReleaseError:
            pass  # Legacy variants remain previewable but cannot be downloaded.
        (target/'playback.json').write_text(json.dumps(result))
        new_name=variant+original.suffix
        shutil.copyfile(original,root/'work'/'uploads'/new_name)
        return jsonify(url='/engine/'+new_name+'?view=1')
