# Release handoff

## Decision requested — remaining corner repairs

See RELEASE-CORNER-DECISION.md for measured 0.20 mm fill-row turns. Exact-path redistribution cannot repair these. Recommend an explicit preview-and-approve connector repair with Undo and coverage checks; awaiting direction before adding this editing workflow. Ordered geometry-first continuation paused; other release audits remain open. No application changes this investigation; latest suite remains 305 passing.

## Latest checkpoint — spacing repair (9819d3d)

See RELEASE-SPACING-FIX.md: 305 tests passed; ten-pair trim parity and original circles warm/cold byte equality confirmed. Straight-run repair preserves exact outlines but genuine short corners remain blocked. Next investigate remaining short legs without dropping corners or weakening the gate; shape changes require explicit review. Local server needs restarting to load this repair.

Bird preview failure also fixed in e90e55f (BIRD-DECORATIVE-FIX.md): all valid boundary components preserved, small embossed regions retain base fill with notices. Real bird generated 12,106 stitches; playback verified. No claim of physical sew-out or genuine foam-puff validation.

## Current checkpoint — 7 October 2026

Completed: 6661675 fixes knockout routing on the machine grid (regression observed failing before); a033e73 fixes physical thread spans across jumps and STOP (three failures reproduced before correction). See RELEASE-GRID-FIX.md and RELEASE-TRAVEL-FIX.md. Latest full suite: 297 passed in 46.76 seconds. All 18 previously generated audit files remain byte-identical; HELLO knockout now passes removed-area readback but still fails its short-segment release check. Safety thresholds are unchanged.

Next: reproduce and correct short-stitch geometry for the original circles/HELLO/Tatami without blind detail removal or weakening the 0.3–7 mm gate. Original fixtures are under /tmp/needlora-readonly-20260930-89kslgb3; latest generated evidence under /tmp/output-safety-final-nst9hwe1. Reference engine minimum filtering explicitly exempts locks and can distort small lettering; do not blindly turn it up. Genuine foam puff is deferred until necessary fixes are complete and cannot be called validated without physical sew-outs.

Hourly thread continuation configured as finish-embroidery-release-fixes. Pause it when all actionable work is complete or external inputs block further progress; do not repeat unchanged checks. Production hosting/customer isolation, machine-specific hoop constraints and physical samples remain open. Preserve the three unrelated untracked landing images.

## Previous checkpoint

Current bounded task: make two existing workspace browser acceptance scripts independent of deleted/trashed customer fixtures.

Original failure reproduced: browser_workspace_states.py navigated to the hard-coded customer design and timed out on “This design is in Trash”. Prior closure recorded the same blocker for both suites.

Implementation: tests/browser_workspace_isolated.py creates temporary synthetic artwork, an isolated Flask instance on an ephemeral port and an isolated Chromium profile. The suites receive WORKSPACE_URL. The playback check generates a real machine plan in the temporary project instead of loading a customer's cached output. Source uploads and production settings are not modified.

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:work/deps python3 tests/browser_workspace_isolated.py`.

Result: both suites passed on 7 October: seven topics preserve values; erase draft/cancel/apply/Undo; canceled brush rollback; keyboard/native select; 390px reflow; queued generation, timeout and retry; visible real stitches and advancing playback. Screenshots are in outputs/workspace-*.png and outputs/erase-area-draft.png.

Full unit-suite baseline remains 292 passing from the preceding checkpoint; not rerun for this test-only change. No machine-file change is expected because application code is untouched. These two former Trash-fixture blockers are closed; other static-audit, participant and production-security checks are not.

No stitch-generation, export-policy, product UI or production configuration changes in this task. Remaining product issues are in RELEASE-CHECKLIST.md; the next geometry investigation should reproduce the known original HELLO knockout crossing refusal. Keep its safety gate intact.
