from pathlib import Path
import types
import numpy as np
from embroiderly import detail_loss

def test_reused_stage_masks_preserve_every_diagnostic():
    code=Path(detail_loss.__file__).read_text()
    old=code.replace('    stage_changes={key:np.any(before!=after,axis=2) for key,(before,after) in stages.items()}\n','').replace('changed=region&stage_changes[key]','changed=region&np.any(before!=after,axis=2)').replace('changed=selected&stage_changes[stage]','changed=selected&np.any(before!=after,axis=2)')
    reference=types.ModuleType('embroiderly._reference')
    exec(compile(old,'reference_detail_loss','exec'),reference.__dict__)
    source=np.full((64,64,3),180,dtype=np.uint8)
    source[8:56:8,8:56]=10
    output=np.full((64,64,4),180,dtype=np.uint8);output[:,:,3]=255
    selected=np.ones((64,64),bool)
    stages={'merge':(source,output[:,:,:3]),'smooth':(source,source.copy())}
    result=detail_loss.check(source,output,selected,100,stages)
    assert result['findings']
    assert result==reference.check(source,output,selected,100,stages)
