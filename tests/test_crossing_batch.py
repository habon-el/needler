import random

import numpy as np

from embroiderly.knockout_routing import RemovedPixels


def one_by_one(mask, a, b):
    # The original per-segment check: crosses_many must give the same answers.
    a = (np.asarray(a) / 10 + mask.origin) / mask.scale
    b = (np.asarray(b) / 10 + mask.origin) / mask.scale
    xy = np.rint(np.linspace(a, b, max(2, int(np.linalg.norm(b-a)*4)+1))).astype(int)
    h, w = mask.core.shape
    if ((xy[:, 0] < 0) | (xy[:, 0] >= w) | (xy[:, 1] < 0) | (xy[:, 1] >= h)).any():
        return True
    return bool(mask.core[xy[:, 1], xy[:, 0]].any())


def test_batch_matches_one_by_one():
    rng, pick = np.random.default_rng(7), random.Random(7)
    alpha = np.ones((120, 160), bool)
    for _ in range(20):
        x, y = rng.integers(0, 160), rng.integers(0, 120)
        alpha[max(0, y-5):y+5, max(0, x-5):x+5] = False
    mask = RemovedPixels(alpha, 0.25, (-2.0, 1.5))
    segments = []
    for _ in range(4000):
        x, y = pick.randint(-60, 700), pick.randint(-60, 520)
        kind = pick.random()
        end = ((x, y) if kind < .2 else (x + pick.randint(-70, 70), y) if kind < .5
               else (x, y + pick.randint(-70, 70)) if kind < .7
               else (x + pick.uniform(-90, 90), y + pick.uniform(-90, 90)))
        segments.append(((x, y), end))
    expected = [one_by_one(mask, a, b) for a, b in segments]
    assert any(expected) and not all(expected)
    assert mask.crosses_many(segments) == expected
    assert [mask.crosses(a, b) for a, b in segments[:200]] == expected[:200]
    assert mask.crosses_many([]) == []
