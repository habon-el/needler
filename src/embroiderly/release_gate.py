"""Fail-closed post-write release gate shared by every machine-file download.

No future-coverage claim: uncut travel is conservatively exposed unless cut.
The 6 mm travel policy and 0.3–7 mm nonzero sewn-segment limits are explicit
application release constraints, not universal physical machine guarantees.
"""
import base64
import hashlib
import io
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import numpy as np
import pyembroidery as emb
from .machine_files import read_pattern
from .knockout_routing import RemovedPixels

VERSION=1
_PASSED={}   # file pairs that passed checked_bytes in this process (see there)
MIN_STITCH_MM=.3
MAX_STITCH_MM=7.
MAX_UNCUT_TRAVEL_MM=6.


class ReleaseError(ValueError):
    def __init__(self, reason, point=None, index=None):
        self.location=None if point is None else dict(x_mm=round(point[0]/10,3),y_mm=round(point[1]/10,3),command=index)
        suffix='' if point is None else f' at x {point[0]/10:.2f}, y {point[1]/10:.2f} mm (command {index})'
        super().__init__('Export blocked: '+reason+suffix+'.')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def record_context(directory, alpha, scale, origin):
    """Bind source-space context to both completed binaries, never bless safety."""
    directory=Path(directory)
    record=dict(version=VERSION,shape=list(alpha.shape),scale=float(scale),origin=list(origin),
                mask=base64.b64encode(np.packbits(alpha).tobytes()).decode(),
                files={fmt:digest((directory/('design.'+fmt)).read_bytes()) for fmt in ('pes','dst')})
    temp=directory/('release-context.'+uuid4().hex+'.tmp')
    temp.write_text(json.dumps(record,sort_keys=True));temp.replace(directory/'release-context.json')


def read_context(directory):
    try:
        record=json.loads((Path(directory)/'release-context.json').read_text())
        h,w=record['shape'];scale=record['scale'];origin=record['origin']
        if record['version']!=VERSION or type(h) is not int or type(w) is not int or not 0<h*w<=16000000:
            raise ValueError()
        if not math.isfinite(scale) or scale<=0 or len(origin)!=2 or not all(math.isfinite(v) for v in origin):raise ValueError()
        raw=base64.b64decode(record['mask'],validate=True)
        if len(raw)!=(h*w+7)//8:raise ValueError()
        mask=np.unpackbits(np.frombuffer(raw,dtype=np.uint8))[:h*w].reshape(h,w).astype(bool)
        return record,mask
    except (OSError,KeyError,TypeError,ValueError,OverflowError):
        raise ReleaseError('source verification is missing or invalid; generate stitches again') from None


def check_pattern(pattern, alpha, scale, origin):
    from .export_findings import inspect, summary
    issues=inspect(pattern,alpha,scale,origin)
    if issues:
        first=issues[0];location=first['location']
        error=ReleaseError(summary(issues)+'; '+first['reason'],
                           None if location is None else [location['x_mm']*10,location['y_mm']*10],
                           None if location is None else location['command'])
        error.issues=issues
        raise error




def checked_bytes(directory, fmt):
    """Validate both siblings, then return the exact bytes checked (no TOCTOU)."""
    directory=Path(directory)
    record,mask=read_context(directory)
    try:files={f:(directory/('design.'+f)).read_bytes() for f in ('pes','dst')}
    except OSError:raise ReleaseError('a machine file is missing; generate stitches again') from None
    if record.get('files')!={f:digest(data) for f,data in files.items()}:
        raise ReleaseError('machine files changed since generation; generate stitches again')
    # The same bytes checked against the same source context give the same
    # answer: skip re-parsing a pair that already passed in this process.
    # The key binds both files' digests and the whole release context.
    key=(record['files']['pes'],record['files']['dst'],digest(json.dumps(record,sort_keys=True).encode()))
    if key in _PASSED:
        return files[fmt]
    # Parsers work from an immutable byte snapshot; never reopen the live target
    # after checking it. Cache hits and legacy downloads use this exact same gate.
    with TemporaryDirectory(prefix='needlora-release-') as temp:
        patterns={}
        for f,data in files.items():
            p=Path(temp)/('design.'+f);p.write_bytes(data)
            try:pattern=read_pattern(p)
            except Exception:raise ReleaseError('the machine file cannot be read') from None
            check_pattern(pattern,mask,record['scale'],record['origin']);patterns[f]=pattern
        if patterns['pes'].count_stitch_commands(emb.TRIM)!=patterns['dst'].count_stitch_commands(emb.TRIM):
            raise ReleaseError('PES and DST disagree about thread cuts')
    _PASSED[key]=True
    while len(_PASSED)>256:_PASSED.pop(next(iter(_PASSED)))
    return files[fmt]


# Further machine formats are converted from the checked PES and checked again.
# VP3 is omitted: its readback cannot distinguish travel from sewn stitches.
FORMATS={'dst':'DST — Tajima and most commercial machines','pes':'PES — Brother / Babylock',
         'jef':'JEF — Janome','exp':'EXP — Melco / Bernina','xxx':'XXX — Singer',
         'u01':'U01 — Barudan','pec':'PEC — Brother (older)'}


def cut_events(pattern):
    """Thread cuts between sewn sections: a trim with a following colour change
    is one cut, and a cut after the last stitch changes nothing on fabric."""
    count=0;sewing=False;pending=False
    for _,_,flags in pattern.stitches:
        kind=flags&emb.COMMAND_MASK
        if kind==emb.STITCH:
            if pending:count+=1;pending=False
            sewing=True
        elif kind in (emb.TRIM,emb.COLOR_CHANGE,emb.NEEDLE_SET) and sewing:pending=True;sewing=False
    return count


# Writer/reader settings that keep explicit cuts in formats with optional trims.
FORMAT_SETTINGS={'jef':({'trims':True},{'trims':True})}


def converted_bytes(directory, fmt):
    """Bytes of a further machine format, written from the checked PES pattern
    and accepted only if its own readback passes the same release checks."""
    if fmt in ('pes','dst'):
        return checked_bytes(directory,fmt)
    if fmt not in FORMATS:
        raise ReleaseError('this machine format is not supported')
    record,mask=read_context(directory)
    source=checked_bytes(directory,'pes')
    with TemporaryDirectory(prefix='needlora-convert-') as temp:
        pes=Path(temp)/'design.pes';pes.write_bytes(source)
        pattern=emb.EmbPattern(str(pes))
        target=Path(temp)/('design.'+fmt)
        write_settings,read_settings=FORMAT_SETTINGS.get(fmt,(None,None))
        emb.write(pattern,str(target),write_settings)
        data=target.read_bytes()
        try:readback=emb.EmbPattern(str(target),settings=read_settings)
        except Exception:raise ReleaseError('the converted machine file cannot be read') from None
        if cut_events(readback)!=cut_events(pattern):
            raise ReleaseError(f'{fmt.upper()} cannot store this design\'s thread cuts exactly; use PES or DST')
        check_pattern(readback,mask,record['scale'],record['origin'])
    return data


def download(directory, fmt, name='design'):
    from flask import jsonify,send_file
    try:data=converted_bytes(directory,fmt)
    except ReleaseError as error:return jsonify(error=str(error),location=error.location,issues=getattr(error,'issues',[])),422
    return send_file(io.BytesIO(data),mimetype='application/octet-stream',as_attachment=True,
                     download_name=name+'.'+fmt)
