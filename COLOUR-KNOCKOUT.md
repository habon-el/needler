# Lettering and line-art colour removal

Implemented and checked on 27 September 2026. The original Big thanks upload and
its saved settings were not changed. Browser checks use separately uploaded copies.

## Use it

Open an image in the existing workspace. Flat artwork with a dominant border colour
offers a before/after removal proposal. Review it, then **Apply removal**. Nothing
is applied by classification alone. Alternatively choose **Remove colour**, click
the colour on the original, and select **Remove this colour everywhere** or
**Only this area**. The colour swatch is also a keyboard-accessible alternative.

The tolerance is CIE76 Delta-E in CIELab. The before/after slider works with the
keyboard and shares the existing zoomable canvas. Larger enclosed colour regions
appear as unticked parts with source-context thumbnails. Tick one to keep it.
After Apply, ticking a part restores it in one click, through normal Undo history.
**Undo brush cleanup only** keeps the colour removal but restores the tiny holes.
**Save design** persists accepted operations. The assistant phrases “remove the
white” and “keep only the black” use this same local proposal, not a paid model.
The latter is the requested white-knockout shortcut, not a classifier that removes
every non-black colour from a multicolour photograph.

## Verification

Actual source: `work/uploads/e2742318856746e2b8a749b2dcecdf15.webp`, 612 × 408 pixels.
SHA-256: `8c76ca58fdfa36fbee5223559ceafd71b23bf0b6809a838fc9b718263b8dd8f0`.
Test scale: 150 × 100 mm image canvas; the ink occupies a smaller bounding box.

| Requested check | Observed result |
|---|---|
| Remove exterior and enclosed white | **0.0000 mm²** matching white in the final prepared artwork; transparent background and holes |
| Preserve letter/heart openings | All **7 larger enclosed parts** remain open and unticked; inspected in the wipe and stitch preview |
| Fill brush specks, report count | Actual image: **2** specks filled with neighbouring ink, not white alpha. Controlled synthetic fixture: **214** specks; cleanup-only Undo tested |
| No white halo | Final artwork has one near-black palette entry, **#020202**; grey edge mixtures assigned to the closer Lab endpoint; boundary fixture and actual preview checked |
| Cartoon with white eyes | Two synthetic white-eye components offered independently; restoring one leaves the other removed and the exterior transparent |
| White lettering on a black badge | Synthetic HI text offered as unticked parts and restored without restoring the exterior; explicitly chosen small threshold for this small fixture |
| Real machine output and playback | **9,994 stitches, 8 trims, one thread colour**. App generation succeeds, the canvas is nonblank, Play advances, and completed stitches retain the openings |
| No sewn/loose crossings over removed areas | Both decoded **PES and DST** checked. Zero crossings of transparent interiors beyond a **one-source-pixel contour/rounding allowance**; this is not a zero-error physical sew-out claim |
| Determinism | Repeated preparation byte-identical; synthetic guarded PES/DST repeat byte-identical; repeat actual prepared image matches |
| Other export fixtures | All **six original PES/DST fixtures byte-identical**, photographic input unchanged |
| Original upload | SHA-256 unchanged; no settings saved to the original design |

The first actual export check exposed three short sewn connectors across gaps.
The opt-in routing guard now locks, trims and jumps exposed connectors instead of
sewing through removed pixels. It also secures raw uncut jump transitions. Eight
connectors in this plan are guarded. It preserves fill paths and checks both files
after encoding. An unsafe result fails before replacing existing machine files.
The guard is enabled only by accepted colour-knockout operations, not other designs.

## Test evidence and honest limits

- `PYTHONPATH=src:work/deps python3 -m pytest -q`: **258 passed**.
- JavaScript syntax checks: preparation, workspace, assistance and colour-knockout pass.
- `tests/browser_colour_knockout.py`: real-browser auto proposal, cancel, pointer
  sampling, native scope keyboard changes, keyboard wipe, assistant command,
  Apply, cleanup-only Undo, one-click part restoration, HTTP failure/retry,
  stale response rejection, save/reload, 390-pixel layout and reduced motion pass.
- `tests/browser_knockout_playback.py`: generation through the app, visible
  stitches, Play, single thread colour and both machine-file readbacks pass.
- `tests/verify_colour_knockout.py`: actual-source preparation, deterministic
  comparison and machine-path measurements; results in
  `outputs/colour-knockout/verification.json`.
- Module/knowledge baseline re-established in baseline-only commit **e44c84a**;
  `tests/verify_module_boundary.py` passes. Other local work is not included in that commit.
- Premium strict static audit exits 1 with **78 literal-button findings**.
  All 78 are traced to existing external/delegated handlers in
  `outputs/colour-knockout-static-triage.json`. This records why they are detector
  false positives; it does not pretend the strict command passed or certify every
  legacy control. New controls are also exercised in the browser tests.
- **Not passed:** configured legacy `browser_workspace.py` and
  `browser_workspace_states.py` stop at their fixture's Trash page. The user's
  trashed design was not restored to make tests pass. Targeted owned-copy tests
  above cover this change; the old fixture dependency remains to be replaced.
- **Not tested:** physical sew-out, machine trimmer compatibility, other browsers,
  real screen-reader interaction and novice participant comprehension.

## Boundaries and ownership

No new AI, semantic OCR or subject model is used. Flat-art detection is conservative
and heuristic, not proof of artistic intent. Intentional small white marks can be
indistinguishable from brush texture: adjust the area threshold or undo cleanup.
The seven larger openings in this actual design are protected independently of
closing. No claim is made that arbitrary microscopic letter counters can always
be distinguished automatically from texture.

Brush area 1 mm², close radius 0.15 mm (maximum 0.2 mm), and Delta-E 12 come from
`knowledge/knockout.json#brush.cleanup`. They are explicitly **unverified user-brief
seeds**, not established universal embroidery limits, and replace no prior setting.
At this source scale a pixel is about 0.245 mm, so the effective close radius is
**0 mm**: rounding up would exceed the requested physical limit. On higher
resolution inputs, the radius is rounded down and reported. Closing works per ink
component and excludes protected larger holes.

Preparation options/history remain the only design-state owner. Controls live in
Subject / Select & approve, with a labelled Remove colour tool. The frontend skills
guided reuse of existing tokens, canvas, native inputs, inline errors and explicit
Apply/Undo rather than a second editor. No visual identity or routing redesign.
Generic smoothing, small-area removal and mask cleanup are temporarily bypassed
and visibly disabled while knockout is active; their stored values are retained.

Removal respects the selected subject and existing erasures. It cannot recover ink
already excluded by selection, cropping or erasing. Original uploads stay intact.
Portrait mode and saved local recovery patches are currently incompatible with
this operation and produce explicit errors, not silently reintroduced white or
misleading measurements. A border or stitch style that places stitches in removed
areas can be rejected by the export guard and must be reviewed. Limits of 16
operations and 256 recoverable enclosed parts fail explicitly rather than silently
discarding extra parts. No source pixels or recoverable originals are deleted.

The latest owned preview URL is recorded in `outputs/colour-knockout/browser-fixture.json`;
actual playback evidence and its prepared-file identity are in `browser-playback.json`.
