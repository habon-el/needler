# Automatic repair: step 1 investigation

Target: prepared_eb53b7a9f4ff3d83fd7ce53d, 32 mm tall.
Installed engine: Ink/Stitch v3.2.2. No AGENTS.md found in the project tree.
No application code, customer design, cache or export baseline changed in this pass.
The source-setting experiment ran only in a temporary directory.

## Confirmed settings

All 80 generated path elements have no Ink/Stitch parameter overrides.
SVG metadata contains the version marker but no minimum-length override.
User engine configuration sets default_min_stitch_len_mm to 0.1.
Effective row spacing: 0.25 mm; global minimum: 0.1 mm; maximum fill
stitch length: 3.0 mm. These differ from the app's 0.3–7 mm release policy.

Version-matched sources inspected:
- https://github.com/inkstitch/inkstitch/blob/v3.2.2/lib/elements/fill_stitch.py
- https://github.com/inkstitch/inkstitch/blob/v3.2.2/lib/elements/element.py
- https://github.com/inkstitch/inkstitch/blob/v3.2.2/lib/utils/settings.py

## Measurements and classification limits

Decoded PES contains 7,518 STITCH commands and 1,084 nonzero short consecutive
STITCH spans: 414 vertical, 126 horizontal, 544 diagonal. These are observable
directions, NOT reliable semantic categories.

The raw generator JSON contains only threadlist, stitches and extras; commands
contain x, y and command type. It has no object IDs, lock flags, row IDs or outline
corner tags. Thus row turns / in-row / locks / between-object classification is
unresolved for these 1,084 spans; none of those categories is claimed to be zero.
Raw pre-rounding output has 1,832 short spans and 198 spans which become short
only after rounding to the machine grid. Those are a DIFFERENT processing stage,
before PES normalization and existing straight-run repair; 198 is not asserted
to be the snap-only category of the final 1,084.

## Disposable source-setting experiment

Applied min_stitch_length_mm=0.45 and row_spacing_mm=0.4 to all 80 paths.
Ran the actual installed generator and existing PES/DST writer/straight-run repair.

| Measurement | Existing | Source-setting experiment |
|---|---:|---:|
| Total machine commands | 7,602 | 3,986 |
| Short consecutive sewn spans | 1,084 | 19 |
| Consecutive sewn spans crossing removed-area core | 173 | 123 |

Crossings use the existing release mask and its existing one-pixel allowance;
they are not yet classified into holes, outline excursions or other exclusions.
First experimental refusal: command 3, 0.10 mm at x 78.70, y 12.70 mm.
Counts of commands are not per-object stitch-count or density measurements.

## Stop condition and required plan correction

The spacing mismatch is real, but short-stitch smoothing alone does not address
the 173 pre-existing removed-area crossings (123 remain after source correction).
Deleting more points cannot be assumed to repair those crossings. Safe release
needs explicit containment-aware rerouting as well as short-span repair.

The automatic rules also need generator-level provenance BEFORE filtering and
serialization: object IDs, locks, row/outline roles and pre-grid coordinates.
Without it we cannot prove that a repair preserves lock stitches, does not change
locked objects, or stays under the per-object 5% limit. Guessing tags from nearby
coordinates is not a safe substitute.

Per the user's instruction, stop before production implementation when findings
contradict the proposed path to an automatic successful export. Proposed amended
order: provenance capture → explicit fabric/minimum settings → bounded short-span
repair AND containment rerouting → exception-only approval → unchanged release
gate. Distinguish source-regeneration count changes from the repair-only 5% limit.

Regression implementation, overlays, per-object density reports, exception UI,
fixture rebaselining and three-run determinism are NOT complete. Existing tests
were not rerun because production code was unchanged. Physical sew-out: pending.
