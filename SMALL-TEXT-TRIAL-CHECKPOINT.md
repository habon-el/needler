# Small lettering trial — 13 October 2026

## Native Text workflow — current checkpoint

This section supersedes the trial-only UI/status below. The local Text tool now
offers Build & check stitches → Save checked lettering → Download DST/PES.
It uses installed embroidery-font satin geometry, not raster tracing. Existing
artwork designs and their original fonts are not silently migrated. Retype or
reuse the words in Text and explicitly choose the native font/size to rebuild.

Implemented: independent rail/rung outlines (including closed counters and rungs
before rails), source-centred coordinates, 0.45 mm generation minimum, the app's
existing 0.6 mm retracing locks, trims between disconnected pieces such as i/j
dots, source glyph counts, and written needle-point presence in each source
column. Every download rechecks the exact written DST/PES through the shared
0.3–7 mm and removed-area/uncut-travel gate. No threshold was lowered. A bounded
0.071 mm source-envelope allowance accounts for snapping endpoints by up to
0.05 mm on each file-grid axis; this does not authorise whole letter counters.

The same checked files are reused for repeat downloads and fit-only width edits.
Explicit save is bound to the recipe. Changing size regenerates from vectors;
changing words, font, size, alignment, colour or available width invalidates the
current approval. New results are separate local records, never original-image
replacement. Native download errors stay as plain text in the dialog.

Live app check, `jesus is / kings`, nominal size 5, available width 50 mm:
29.6 × 15.2 mm; 961 stitches; 14 cuts in both formats; nonzero lengths 0.4–2.11
mm; 0 short, 0 long, 0 crossings, 0 exposed uncut travels, 0 missing source
columns. First build 10.955 s; repeat checks 0.284 and 0.938 s. Three downloads
were byte-identical in both formats. Changing available width to 20 mm took
0.016 s, reused geometry, and correctly refused fit without shrinking.

Fifteen real generator cases: Jesus text, Hello World, tiny, Baby 0689 and
punctuation at nominal 4/5/6 mm, plus the four-line verse in 100/110 mm spaces.
All written pairs had 0 short/long/crossing/uncut-travel findings; two 6 mm cases
were too wide for 50 mm and were not approved. The verse was actually 97.8 ×
23.6 mm, 5,234–5,239 stitches and 83 cuts, not exactly 100/110 mm wide. These
are space-fit tests, not proof of requested-width or reference-count equivalence.

Remaining: font auto-routing is NOT cold-run deterministic (fresh uncached
generations vary). Snapshot reuse makes actual repeat downloads identical, not
the underlying generator. Glacial Tiny is disabled in the UI because its outline
verification failed. Only Small Font nominal 4–6 mm is exposed. Density/repeated
penetration assessment, exact cap-height sizing, cap-specific sew order and
physical sew-out are not certified. The interface flags font/size and density/
sew-out limits before save; the other engineering gaps are recorded here.
Passing these file checks is not proof of readable or needle-safe sewing.

Verification: 381 Python tests passed; native browser save/download/bookmark,
fit refusal, slow/stale replies, unsupported glyph errors, narrow layout and
keyboard recovery passed. Configured workspace/browser-state checks passed.
Demo DST/PES export bytes match checkpoint 960d53a. All 15 source-column presence
checks pass in both written formats. Machine results and hashes are local in
work/native-lettering-verification; screenshots are in outputs.
Strict static audit is not globally clean: 86 findings, including 3 new externally
wired buttons verified in the browser. No inline no-op handlers were added to
silence that detector. Changes are local and uncommitted: Git author identity is
not configured. No remote is configured; no customer files were pushed.

## Rectangle error follow-up

The saved customer options were selection=full; the screenshot's failing box
was unsaved, so its exact coordinates cannot be recovered. Reproduction found:
one Auto select click committed a zero-area rectangle and produced the same
margin error; a valid box around the customer's transparent letters erased all
30,364 opaque pixels because transparent RGB matched foreground RGB.

Rectangle gestures now remain drafts until valid release. Click/flat/tiny
gestures and Escape preserve selection/history/playback. Existing alpha defines
the cutout inside the box; opaque sources still use GrabCut. Full-boundary boxes
are accepted when alpha supplies background evidence. The mask-cache version
changed so old destructive masks are not reused. Other cleanup remains separate.

Nine backend regressions and the pointer regression were checked failing on the
pre-fix code. After: 366 pytest tests passed; selection browser checks, both
configured workspace browser commands, JS syntax and git diff --check passed.
The restarted live app returned HTTP 200 cold/warm for this image: 30,364 visible
pixels retained, zero lost, zero background added. Original/saved-option hashes
unchanged. No customer stitches were generated, approved or exported in this check.
Strict UI audit still reports 83 pre-existing findings; not a clean global audit.
This selection repair does not establish tiny-letter legibility or physical safety.

## Width and readability follow-up

The Size & fabric panel now has an editable canvas width linked to the existing
height_mm owner. Explicit mm units, one-decimal display, Enter/blur commit,
Escape/invalid-input cancellation, Undo, and invalidation of old exports were
checked in the isolated browser. Actual resizing still requires regeneration.
No customer image, saved recipe or settings were changed in live verification.

Typed artwork now measures reference capital H from its source font, not block
height divided by line count. At 50 mm canvas width, the saved four-line verse's
reference capital is about 2.38 mm. Its current saved canvas is 52.2 × 18.0 mm,
with capitals about 2.5 mm. This is a pre-stitch source estimate, not a sewability
claim. The review heading now flags lettering even without tiny-area warnings.

The Text trial checks available width (default 50 mm) without resizing words.
Hello World at nominal 4 mm measured 37 × 4.2 mm; 9 trims, nonzero lengths
0.3–2.2 mm, zero short/long segments in both formats. Repeated trials produced
703 and 705 stitches: exact generation determinism is NOT established.
The original four-line verse measured 97.8 × 23.6 mm, 5,178 stitches, 75 trims,
10 short segments and no long segments. It does NOT fit 50 mm unchanged and is
not release-approved. Reflow/more space or revised wording remains a user choice.

Verification: 357 Python tests passed in the full suite; the new width/lettering
browser test and both configured workspace browser commands passed. JavaScript
syntax and git diff checks passed. The strict static UI audit still reports 83
findings (not a clean audit or a full accessibility certification).
Screenshots: outputs/width-editor-live.png and outputs/lettering-width-trial.png.
Source font checks follow https://inkstitch.org/docs/lettering/ and the installed

This checkpoint supersedes the UI-integration status in SMALL-TEXT-CHECKPOINT.md.
It is not a release approval or a claim of physically safe stitching.

## Implemented

- Tools → Text → Try small embroidery lettering uses the installed embroidery
  fonts, not raster tracing. Existing words/alignment are reused; font and nominal
  height are explicit trial choices. Existing saved designs remain unchanged.
- The generated SVG is rebuilt with the 0.45 mm source minimum. Temporary PES
  and DST files are read back and measured. The preview shows DST stitch paths.
- Editing inputs invalidates stale results. Busy, invalid-input, failure and
  timeout states are explicit. No trial download is offered.
- Existing export checks and their 0.3 mm minimum are unchanged.

## Evidence

- Full Python suite: 349 passed in 64.94 seconds.
- Focused checks: 33 passed. JavaScript syntax checks passed.
- Live browser trial, Small Font, `tiny`, nominal 4 mm: 244 stitches, 3 trims,
  actual bounding box 11.8 × 5.8 mm; nonzero stitch lengths 0.300–2.102 mm;
  zero short/long stitches in both saved formats.
- Browser checks also exercised invalid 3 mm input, busy feedback, stale result
  clearing, 390 px dialog width and Escape/focus return. This is not a full
  accessibility audit or physical sew-out.
- Strict static UI audit has 83 findings; it is NOT clean. Several checks flag
  JavaScript-wired buttons as actionless, including the trial button whose real
  handler was exercised. The remaining findings are not all triaged.

## Still blocked

The trial always returns release_approved=false. Letter-hole containment,
density/repeated penetrations, complete glyph/punctuation retention and machine
fit require validation before this path may export. Physical sew-out is pending.
Nominal font size is not an exact measured capital height.

The rebuilt four-line verse at nominal 4 mm still had 10 short segments in a
separate readback test. Passing `tiny` does not mean arbitrary small text passes.
The production Text creation route remains the existing outline workflow; this
trial does not silently replace it. Below 4 mm is not enabled.

Changes are local and uncommitted. No remote is configured; Git author identity
was unavailable for the earlier commit attempt. No customer files were pushed.
