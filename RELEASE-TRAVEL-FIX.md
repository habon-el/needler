# Physical thread-span release checks — 7 October 2026

Three synthetic failures reproduced against the previous release gate:

1. Needle at (1,1), jump to (5,1), sew at (5,5): commanded legs avoid a central hole but the loose thread spans the diagonal through it. Previously accepted.
2. STOP between needle penetrations: treated as a cut, so a following crossing was accepted. STOP alone does not detach thread.
3. Needle at (1,1), jump to (5,1), sew at (9,1): checked as a 4 mm stitch instead of the actual 8 mm sewn span. Previously accepted.

The new gate retains the last needle penetration across jumps and STOP, checks loose spans against removed areas, and measures sewn length from that penetration. TRIM and the existing colour-change boundary reset attachment. Explicit cut/position/restart remains valid. No machine files are rewritten by this change; old cached downloads get the stricter check immediately when served by the updated app.

Tests: all three failing regressions were observed before the fix. Four new travel tests and the existing download test passed after it. Full suite: **297 passed in 46.76 seconds**. Original satin and raised-satin fixtures still pass both format checks. Circles, HELLO and Tatami retain their known short-segment refusals. No thresholds were relaxed.

## Remaining release blockers, not completion claims

Short-segment path generation still needs a geometry-aware correction. Blindly raising an engine minimum can remove or distort small lettering; this is explicitly documented by the engine: https://inkstitch.org/docs/preferences/#minimum-stitch-length-mm . No blanket filter has been added.

Actual foam puff is not implemented or validated. Manufacturer guidance describes a different physical process: foam fixation, satin coverage and foam removal, not a shaded preview or repeated ordinary satin. Reference: https://www.madeira.com/embroidery-solutions/service/support/embroidery-best-practice/dimensional-embroidery-with-3d-foam . Development requires explicit foam/material/machine profiles, end coverage, suitable-column validation, stop/placement instructions, and real sew-outs before a production-ready claim. It remains deferred until the safety fixes are complete, as requested.

Public deployment also needs host/account configuration and verification of customer isolation; physical testing needs machine access and samples. These are not demonstrated by passing unit tests.
