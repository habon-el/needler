"""Regressions for the September 30 readback audit; all artwork is synthetic."""
import math
import json
import numpy as np
import pyembroidery as emb
from PIL import Image, ImageDraw
from embroiderly.model import Design, Thread, Command, CommandKind
from embroiderly.export import export_design


def circles():
    commands=[]
    # Two 3 mm circles, 4 mm edge-to-edge gap. Explicit non-sewing move.
    for center in (1.5,8.5):
        commands.append(Command(CommandKind.JUMP,center+1.5,1.5))
        for i in range(25):
            angle=i*math.tau/24
            commands.append(Command(CommandKind.STITCH,center+1.5*math.cos(angle),1.5+1.5*math.sin(angle)))
    return Design(threads=(Thread('#000000','black'),),commands=tuple(commands))


def test_circle_dst_pes_trim_parity(tmp_path):
    result=export_design(circles(),tmp_path,'circles')
    pes=emb.EmbPattern(str(result.pes_path));dst=emb.EmbPattern(str(result.dst_path))
    assert pes.count_stitch_commands(emb.TRIM)>0
    assert dst.count_stitch_commands(emb.TRIM)==pes.count_stitch_commands(emb.TRIM)


def test_trim_writer_does_not_change_unrelated_dst_title(tmp_path):
    from embroiderly.machine_files import write_pair
    pattern=emb.EmbPattern();pattern.add_thread('#000000');pattern.extras['name']=''
    pattern.stitches=[[10,10,emb.JUMP],[10,10,emb.STITCH],[30,10,emb.STITCH],[30,10,emb.END]]
    emb.write_dst(pattern,str(tmp_path/'before.dst'))
    write_pair(pattern,tmp_path/'after.pes',tmp_path/'after.dst',{'version':6})
    assert (tmp_path/'before.dst').read_bytes()==(tmp_path/'after.dst').read_bytes()


def circle_image(path,knockout=False):
    image=Image.new('RGBA',(130,60),(0,0,0,0));draw=ImageDraw.Draw(image)
    draw.ellipse((15,15,45,45),fill='black');draw.ellipse((85,15,115,45),fill='black')
    image.save(path)
    path.with_suffix('.prep.json').write_text(json.dumps({'options':{'colour_knockouts':[{}]} if knockout else {}}))
