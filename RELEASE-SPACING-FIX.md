# Straight-run spacing checkpoint — 7 October 2026

The repair redistributes undersized penetrations only along exactly straight,
forward runs on the decoded 0.1 mm grid. Endpoints, corners, reversals, coincident
penetrations and command boundaries are preserved. No smoothing or detail
deletion is permitted. The 0.3–7 mm release gate is unchanged. The cache routing
policy now includes the repair implementation digest.

The serialized regression first reproduces a 0.20 mm refusal with the unchanged
writer default, then passes PES and DST readback with repair enabled. Repeated
writes are byte-identical. This is an explicit before/after execution, not an
old-tree checkout. A separate regression confirms short corners remain refused.
Full suite: **305 passed in 41.92 seconds** (/tmp/spacing-suite.log).

Original verification rerun: /tmp/output-safety-final-kxl_b3ul/results.json,
compared with /tmp/output-safety-final-nst9hwe1/results.json.

| Fixture | Changed files | PES / DST trims |
|---|---|---|
| shape | none | 1 / 1 |
| text-L | none | 0 / 0 |
| photographic | none | 162 / 162 |
| two-circles-normal | PES, DST | 1 / 1 |
| two-circles-knockout | PES, DST | 1 / 1 |
| hello-world-normal | PES, DST | 4 / 4 |
| hello-world-knockout | PES, DST | 10 / 10 |
| preview-tatami | PES, DST | 0 / 0 |
| preview-satin | none | 0 / 0 |
| preview-raised_satin | none | 0 / 0 |

These ten changed files intentionally redistribute straight-run needle points;
they are not another trim-convention change. Trim parity remains intact. Original
knockout circles remain warm/cold byte-identical in both formats.

## Remaining blocker

Short spans reduced from 16 to 13 for circles, 492 to 413 for normal HELLO,
and 41 to 39 for Tatami. These designs still fail the short-stitch release gate.
File generation is not successful release. Real corner legs cannot be fixed by
this geometry-preserving operation. Further correction must preserve counters
and explicitly review any shape change; blindly dropping points is prohibited.
No physical sew-out or foam-puff validation was performed.
