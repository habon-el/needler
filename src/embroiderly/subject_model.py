"""Optional local SAM2; cache encoded images, persist accepted binary masks.

No network downloads. Missing/failed models fall back to deterministic GrabCut.
"""
import hashlib
import os
import threading
import time
from collections import OrderedDict

import cv2
import numpy as np

_lock = threading.Lock()
_cache = OrderedDict()
_model = None
_encoder_times={}
MAX_CACHED_IMAGES=4


def image_key(image):
    rgb=np.asarray(image.convert("RGB"))
    return image.info.get("source_sha256") or hashlib.sha256(rgb.tobytes()+str(rgb.shape).encode()).hexdigest()


def synchronize():
    # CUDA work is asynchronous; include completed work in measured timings.
    import sys
    torch=sys.modules.get("torch")
    if torch is not None and torch.cuda.is_available():torch.cuda.synchronize()


def cached_predictor(image,factory=None):
    key=image_key(image)
    if key in _cache:return _cache[key],True,0.0
    if len(_cache)>=MAX_CACHED_IMAGES:raise RuntimeError("Embedding capacity reached; existing sessions retained. Restart the local service to release them.")
    predictor=(factory or _predictor)()
    synchronize();start=time.perf_counter();predictor.set_image(np.asarray(image.convert("RGB")));synchronize()
    elapsed=(time.perf_counter()-start)*1000
    _cache[key]=predictor;_encoder_times[key]=elapsed
    return predictor,False,elapsed


def warm_image(image):
    with _lock:
        try:
            _,reused,elapsed=cached_predictor(image)
            return dict(available=True,embedding_reused=reused,encoder_ms=elapsed,initial_encoder_ms=_encoder_times.get(image_key(image)))
        except Exception as error:return dict(available=False,reason=str(error),encoder_ms=None,decoder_ms=None)



def mask_runs(mask):
    flat = np.asarray(mask, dtype=np.uint8).ravel()
    changes = np.flatnonzero(np.diff(flat)) + 1
    runs = np.diff(np.r_[0, changes, len(flat)]).tolist()
    return ([0] if flat[0] else []) + runs


def unpack_mask(runs, shape):
    size = int(np.prod(shape))
    if (not isinstance(runs, list) or not 1 <= len(runs) <= size + 1
            or any(type(n) is not int or n < 0 for n in runs) or sum(runs) != size):
        raise ValueError("Invalid subject mask.")
    return np.repeat(np.arange(len(runs)) % 2, runs).reshape(shape).astype(bool)


def _predictor():
    global _model
    checkpoint = os.environ.get("EMBROIDERLY_SAM2_CHECKPOINT", "")
    config = os.environ.get("EMBROIDERLY_SAM2_CONFIG", "")
    if not checkpoint and not config:
        from .sam2_local import available, Predictor
        if available(): return Predictor()
    if not checkpoint or not config:
        raise RuntimeError("SAM2 not configured")
    if _model is None:
        from sam2.build_sam import build_sam2
        _model = build_sam2(config, checkpoint, device=os.environ.get("EMBROIDERLY_SAM2_DEVICE", "cpu"))
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    return SAM2ImagePredictor(_model)


def propose_mask(image, prompts, box=None, factory=None, *, border_background=True):
    from .preparation import points, LOCK
    rgb = np.asarray(image.convert("RGB")); h, w = rgb.shape[:2]
    if not isinstance(prompts, list) or len(prompts) > 100:
        raise ValueError("Use at most 100 subject clicks.")
    xy = points([p["point"] for p in prompts], w, h) if prompts else []
    labels = [p["label"] for p in prompts]
    if any(type(v) is not int or v not in (0, 1) for v in labels):
        raise ValueError("Subject clicks must add or subtract.")
    if box is not None:
        if not isinstance(box, list) or len(box) != 4:
            raise ValueError("Invalid subject box.")
        a, b = points([box[:2], box[2:]], w, h)
        box = [*a, *b]
        if not a[0] < b[0] or not a[1] < b[1]:
            raise ValueError("Drag a larger subject box.")
    if not any(labels) and box is None:
        raise ValueError("Click the subject first, then subtract background.")
    key = image_key(image)
    encoder_ms=decoder_ms=None
    fallback_reason=None
    cached = False
    candidates=[]
    with _lock:
        try:
            predictor,cached,encoder_ms=cached_predictor(image,factory)
            synchronize();decode_start=time.perf_counter()
            masks, scores, _ = predictor.predict(
                point_coords=np.array(xy) if xy else None,
                point_labels=np.array(labels) if xy else None,
                box=np.array(box) if box is not None else None,
                multimask_output=True)
            synchronize();decoder_ms=(time.perf_counter()-decode_start)*1000
            ranked = []
            visible = np.asarray(image.getchannel("A")) > 127
            for i, score in enumerate(scores):
                candidate = np.asarray(masks[i], dtype=bool)
                if candidate.shape != (h,w) or not np.isfinite(score): continue
                candidate = candidate & visible
                if candidate.sum() < 5: continue
                conflicts = sum(bool(candidate[y,x]) != bool(label) for (x,y),label in zip(xy,labels))
                # Model confidence must not override explicit keep/remove hints.
                ranked.append((conflicts, -float(score), i, candidate))
            if not ranked: raise ValueError("Empty model mask")
            ranked.sort(key=lambda item: item[:3])
            mask = ranked[0][3]
            for conflicts, negative_score, _, candidate in ranked:
                candidates.append(dict(mask_runs=mask_runs(candidate), score=-negative_score,
                                       prompt_conflicts=conflicts))
            method = "SAM2"
        except Exception as error:
            # Keep existing embeddings; a failed decoder must not force re-encoding.
            fallback_reason=str(error)
            fallback_start=time.perf_counter()
            plane = np.full((h, w), cv2.GC_PR_BGD, np.uint8)
            if box:
                x, y, r, b = box; plane[y:b, x:r] = cv2.GC_PR_FGD
            # Legacy rectangle tools assume a background margin. AI subject
            # selection must not force cropped hair/clothes at the frame to BG.
            # Probable background can be reclassified; explicit seeds still win.
            border = cv2.GC_BGD if border_background else cv2.GC_PR_BGD
            plane[[0, -1], :] = border; plane[:, [0, -1]] = border
            for p, label in zip(xy, labels):
                cv2.circle(plane, p, max(2, round(min(h, w) * .012)), cv2.GC_FGD if label else cv2.GC_BGD, -1)
            plane[np.asarray(image.getchannel("A")) <= 127] = cv2.GC_BGD
            with LOCK:
                cv2.setRNGSeed(0)
                cv2.grabCut(rgb, plane, None, np.zeros((1, 65)), np.zeros((1, 65)), 3, cv2.GC_INIT_WITH_MASK)
            mask = (plane == cv2.GC_FGD) | (plane == cv2.GC_PR_FGD)
            method = "GrabCut fallback"
            cached = False
            fallback_ms=(time.perf_counter()-fallback_start)*1000
    mask &= np.asarray(image.getchannel("A")) > 127
    if np.count_nonzero(mask) < 5:
        raise ValueError("No subject found. Try a box or the existing lasso tool.")
    return mask, {"method": method, "embedding_reused": cached,"candidates":candidates,
        "prompt_conflicts":sum(bool(mask[y,x]) != bool(label) for (x,y),label in zip(xy,labels)),
        "encoder_ms":encoder_ms if method=="SAM2" else None,"decoder_ms":decoder_ms if method=="SAM2" else None,
        "initial_encoder_ms":_encoder_times.get(key) if method=="SAM2" else None,
        "encoder_to_decoder_ratio":_encoder_times.get(key,0)/max(decoder_ms or 0,1e-9) if method=="SAM2" else None,
        "fallback_reason":fallback_reason,"fallback_ms":fallback_ms if method!="SAM2" else None}
