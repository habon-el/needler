"""Regenerate placement-specific machine files from artwork, never scale stitches."""
from .knowledge_messages import message as knowledge_message
import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np
import pyembroidery as emb

from .engine import digitize
from .preparation import load_image, cached_selection, prepare
from .finished import render_finished

PRESETS = [
    {"label":"Left chest","axis":"width","mm":80},
    {"label":"Cap front","axis":"height","mm":55},
    {"label":"Sleeve","axis":"width","mm":60},
    {"label":"Jacket back","axis":"width","mm":280},
]

def resolve_size(size, image_size, bounds):
    axis=size.get("axis")
    mm=float(size.get("mm",0))
    if axis not in {"width","height"} or not math.isfinite(mm) or not 3<=mm<=400:
        raise ValueError(knowledge_message('size_sets.16'))
    left,top,right,bottom=bounds
    span=(right-left) if axis=="width" else (bottom-top)
    if span<=0: raise ValueError("Select a nonempty subject.")
    return mm*image_size[1]/span

def exported_audit(path, stitches_per_minute=600):
    """Read snapped exported coordinates. Length is geometric, not consumption."""
    from .machine_files import read_pattern
    pattern=read_pattern(path)
    counts={"stitch_count":0,"trim_count":0,"jump_count":0,"color_changes":0}
    sewn=jumps=longest=0.0;previous=(0.0,0.0);thread=0;per_colour={}
    min_length=math.inf;max_length=0.0
    bounds=[]
    for x,y,flags in pattern.stitches:
        command=flags & emb.COMMAND_MASK
        point=(x/10,y/10);length=math.dist(previous,point)
        if command==emb.STITCH:
            counts["stitch_count"]+=1;sewn+=length
            key=pattern.threadlist[thread].hex_color() if thread<len(pattern.threadlist) else "unknown"
            per_colour[key]=per_colour.get(key,0.0)+length
            min_length=min(min_length,length);max_length=max(max_length,length)
            bounds.append(point)
        elif command==emb.JUMP:
            counts["jump_count"]+=1;jumps+=length;longest=max(longest,length)
            bounds.append(point)
        elif command==emb.TRIM: counts["trim_count"]+=1
        elif command==emb.COLOR_CHANGE:
            counts["color_changes"]+=1;thread+=1
        previous=point
    width=max((p[0] for p in bounds),default=0)-min((p[0] for p in bounds),default=0)
    height=max((p[1] for p in bounds),default=0)-min((p[1] for p in bounds),default=0)
    return dict(**counts,total_jump_mm=jumps,longest_jump_mm=longest,
        total_travel_mm=sewn+jumps,thread_length_mm=sewn,thread_length_by_colour_mm=per_colour,
        shortest_stitch_mm=0 if min_length==math.inf else min_length,longest_stitch_mm=max_length,
        written_width_mm=width,written_height_mm=height,
        runtime_seconds=counts["stitch_count"]/stitches_per_minute*60+jumps/3000*60+
                        counts["trim_count"]*2+counts["color_changes"]*15,
        runtime_assumptions=knowledge_message('size_sets.17'),
        length_assumptions="Geometric sewn path only; excludes bobbin, fabric penetration and wastage.",
        measured_file=Path(path).name)

def regenerate_sizes(source, options, sizes, directory):
    if not isinstance(sizes,list) or not 1<=len(sizes)<=8:
        raise ValueError("Choose between one and eight sizes.")
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    image=load_image(source)
    mask=cached_selection(source,image,options,directory/"masks")
    yy,xx=np.where(mask)
    if not len(xx): raise ValueError("The subject selection is empty.")
    bounds=(int(xx.min()),int(yy.min()),int(xx.max()+1),int(yy.max()+1))
    # Validate all sizes before creating any machine files.
    heights=[resolve_size(size,image.size,bounds) for size in sizes]
    result=[]
    for i,(size,height) in enumerate(zip(sizes,heights)):
        row={"label":str(size.get("label","Custom"))[:60],"axis":size["axis"],"mm":float(size["mm"]),
             "index":i,"status":"failed"}
        target=directory/str(i);target.mkdir(exist_ok=True)
        try:
            artwork,palette,report=prepare(source,options,directory/"masks",target_height_mm=height)
            row["preparation"]=report
            from .cleanup_review import require_review
            require_review(report)
            row["features_below_floor"]=report["below_floor_before"]
            row["features_remaining_below_floor"]=report["below_floor_after"]
            row["mask_features_removed"]=report["mask_specks_removed"]
            minimum=report["minimum_region_area_before_mm2"]
            row["remedy"]=None
            if report["below_floor_before"] and minimum>0:
                required=float(size["mm"])*math.sqrt(report["floor_mm2"]/minimum)
                row["remedy"]=("Under the current area heuristic, retaining the smallest colour region would need about "
                   +str(round(required,1))+" mm "+size["axis"]+
                   ". Alternatively simplify that detail or review it manually; this is not a guarantee of sewability.")
            if not palette:
                raise ValueError("Cleanup removed all selected detail at this size. Increase size or simplify the source artwork.")
            prepared=target/"artwork.png";artwork.save(prepared)
            prepared.with_suffix(".prep.json").write_text(json.dumps({"source":str(source),"options":options,"report":report},sort_keys=True))
            payload=digitize(prepared,target,height)
            pes=exported_audit(target/"design.pes")
            dst=exported_audit(target/"design.dst")
            row.update(status="generated",audit=pes,dst_audit=dst,
                hashes={f:hashlib.sha256((target/("design."+f)).read_bytes()).hexdigest() for f in ("pes","dst")})
            render_finished(payload,"#c2baa8").save(target/"preview.png")
            (target/"playback.json").write_text(json.dumps(payload))
        except (ValueError,OSError,subprocess.TimeoutExpired) as error:
            row["error"]=str(error)
        result.append(row)
    (directory/"report.json").write_text(json.dumps(result,indent=2))
    return result

def register_size_sets(app,root):
    from flask import abort,jsonify,request,send_from_directory
    uploads=root/"work"/"uploads";sets=root/"work"/"size-sets"

    @app.post("/size-set/<name>")
    def build_size_set(name):
        source=uploads/Path(name).name
        if not source.is_file(): abort(404)
        try:
            data=request.get_json()
            if not isinstance(data,dict) or data.get("subject_confirmed") is not True:
                raise ValueError("Please confirm the selected subject first.")
            options=data.get("options")
            if not isinstance(options,dict): raise ValueError("Missing artwork settings.")
            sizes=data.get("sizes",PRESETS)
            digest=hashlib.sha256(source.read_bytes()+json.dumps({"options":options,"sizes":sizes},sort_keys=True).encode()+b"size-set-v1").hexdigest()[:32]
            # Requests get separate folders, avoiding overlapping writes. The binary
            # basename and generation inputs stay stable for reproducibility.
            from uuid import uuid4
            run=digest+"-"+uuid4().hex[:12]
            folder=sets/run
            rows=regenerate_sizes(source,options,sizes,folder)
            for row in rows:
                if row["status"]=="generated":
                    base="/size-set-file/"+run+"/"+str(row["index"])+"/"
                    row["preview"]=base+"preview.png"
                    row["pes"]=base+"design.pes";row["dst"]=base+"design.dst"
            (folder/"manifest.json").write_text(json.dumps({"source":source.name,"options":options,"sizes":sizes,"results":rows},indent=2))
            return jsonify(run=run,results=rows)
        except (ValueError,TypeError,KeyError) as error:
            return jsonify(error=str(error)),400

    @app.get("/size-set-file/<run>/<int:index>/<filename>")
    def size_set_file(run,index,filename):
        if len(run)!=45 or any(c not in "0123456789abcdef-" for c in run):
            abort(404)
        if not 0<=index<8 or filename not in {"preview.png","design.pes","design.dst"}: abort(404)
        if filename != 'preview.png':
            from .release_gate import download
            return download(sets/run/str(index),filename.rsplit('.',1)[1])
        return send_from_directory(sets/run/str(index),filename)
