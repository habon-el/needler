"""Explicit local-model smoke test, not a paid AI or semantic-accuracy test.

Run from project: PYTHONPATH=src:work/deps python3 tests/sam2_smoke.py
Uses fixed diagnostic points on the user-authorized Sasuke upload. Writes only
ignored QA evidence, never an upload, saved design, stitch plan or machine file.
"""
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image

from embroiderly.ai_draft import review_image
from embroiderly.subject_model import propose_mask


def main():
    path = Path('work/uploads/7c43c02327ab49c9aaccce7ed3d2deb1.png')
    original_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    image = Image.open(path).convert('RGBA')
    prompts = [{'point':p, 'label':l} for p,l in [
        ([350,200],1),([180,50],1),([550,80],1),([180,400],1),([500,400],1),
        ([25,120],0),([40,240],0),([690,250],0),([680,40],0)]]
    started = time.monotonic()
    mask, info = propose_mask(image, prompts, [70,0,620,434], border_background=False)
    first_ms = (time.monotonic()-started)*1000
    again, warm = propose_mask(image, prompts, [70,0,620,434], border_background=False)
    assert info['method']=='SAM2', info['fallback_reason']
    assert warm['embedding_reused'] and warm['encoder_ms']==0
    assert np.array_equal(mask, again)
    assert hashlib.sha256(path.read_bytes()).hexdigest()==original_hash
    cutout = image.copy(); cutout.putalpha(Image.fromarray(mask.astype(np.uint8)*255))
    comparison = Image.new('RGB', (image.width*2,image.height))
    comparison.paste(image.convert('RGB'),(0,0)); comparison.paste(review_image(cutout),(image.width,0))
    evidence = Path('.simple-ui-evidence'); evidence.mkdir(exist_ok=True)
    comparison.save(evidence/'sam2-sasuke-fixed-points.png')
    report = dict(test='Real SAM2; fixed diagnostic points, not AI-selected points',
        source_sha256=original_hash, original_unchanged=True, mask_repeat_identical=True,
        method=info['method'], first_ms=round(first_ms,1),
        warm_decoder_ms=round(warm['decoder_ms'],1), retained_pixels=int(mask.sum()),
        semantic_accuracy='Not scored; no labelled ground-truth mask', applied=False)
    (evidence/'sam2-smoke.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__': main()
