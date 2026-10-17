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
    return files[fmt]


def download(directory, fmt):
    from flask import jsonify,send_file
    try:data=checked_bytes(directory,fmt)
    except ReleaseError as error:return jsonify(error=str(error),location=error.location,issues=getattr(error,'issues',[])),422
    return send_file(io.BytesIO(data),mimetype='application/octet-stream',as_attachment=True,
                     download_name='design.'+fmt)
