# Editable lettering workspace — verification, 14 October 2026

## What this pass fixes

Native embroidery-font text now opens at `/text/<recipe-id>` in the main
workspace. The same editable recipe supplies Update stitches, Save design,
the source-shape comparison, actual DST playback and checked DST/PES downloads.
Resizing regenerates the font geometry; it does not stretch an existing file.
Changing words, colour, alignment, size or available width invalidates approval
and old download links. Previous saved versions are preserved.

Before this pass, native letters were confined to a separate Text-dialog preview;
the main image workspace could still generate stitches from the underlying PNG.
Old native bookmarks now redirect to the text workspace. Known saved typed PNG
designs are blocked from re-entering picture digitizing and offer an explicit
embroidery-font rebuild instead. Their original image/font remains unchanged.
Ordinary outline-font creation is labelled artwork-only, not native embroidery.

No photo segmentation, cleanup or stitch-generation algorithm was changed in
this pass. Native source-outline SVG is for display only; it never goes through
raster preparation. Playback reads a snapshot of the checked machine file.

## Actual engine checks

`tests/native_workspace_matrix.py` ran the real installed font engine in a
disposable application, then checked workspace loading, explicit approval and
three downloads of each format. These are measured file results, not sew-outs.

| Words | Nominal font size mm | Stitched width × height mm | Stitches | Cuts | Stitch length mm | End-to-end seconds |
|---|---:|---:|---:|---:|---:|---:|
| Hello World | 4 | 37.0 × 4.2 | 706 | 9 | 0.400–2.200 | 12.02 |
| Hello World | 5 | 46.0 × 5.2 | 852 | 9 | 0.400–2.474 | 11.44 |
| Hello World | 6 | 55.2 × 6.2 | 983 | 9 | 0.500–2.159 | 11.75 |
| tiny | 4 | 11.8 × 5.8 | 249 | 4 | 0.400–2.102 | 7.98 |
| tiny | 5 | 14.5 × 7.2 | 296 | 4 | 0.400–2.470 | 7.99 |
| tiny | 6 | 17.6 × 8.6 | 335 | 4 | 0.500–2.200 | 7.95 |
| jesus is / kings | 4 | 24.0 × 12.4 | 784 | 14 | 0.400–2.202 | 11.18 |
| jesus is / kings | 5 | 29.6 × 15.2 | 961 | 14 | 0.400–2.200 | 11.17 |
| Baby 0689 | 4 | 34.2 × 5.6 | 721 | 7 | 0.447–2.000 | 10.63 |
| i j . , : | 4 | 18.8 × 5.8 | 180 | 7 | 0.500–2.400 | 8.15 |

All ten cases, both formats: **0 short stitches, 0 long stitches, 0 empty-area
crossings, 0 uncut travel violations, 0 missing source columns** under the
existing checks. DST and PES cut counts match in every row. Three downloads of
each saved version were byte-identical. No raster uploads were created.

The available width in this matrix was 60 mm. A width is a fit constraint:
Hello World at nominal 6 mm is 55.2 mm wide and would not fit a 50 mm space.
The app does not silently shrink it. Nominal font size is not an exact measured
capital height. Height includes descenders and line breaks.

Raw reports and SHA-256 values: `work/native-workspace-verification/results.json`.
Runtime includes generation, verification, workspace fetch, approval and six
downloads; it is not a machine run-time estimate.

## Regression and browser evidence

- Python suite before this integration: 381 passing tests.
- Suite after integration: 387 passing tests.
- Six new tests cover exact machine-file playback/no raster calls, route and
  recipe restoration, corrupt-file refusal, regenerated size/new immutable ID,
  the legacy typed-PNG guard and old-bookmark redirection.
- Isolated browser runs: native Text dialog; main native workspace; existing
  size controls; general artwork workspace and error/loading states.
- Verified main-canvas playback, explicit Save, real DST/PES downloads, resize,
  Undo of recipe fields, width refusal without shrinking, invalid-size focus,
  unsupported-character refusal without word substitution, stale-response
  invalidation, and 390 px layout.
- A forced download refusal stays in the workspace with a readable message
  and preserves the words; it does not open a raw JSON page.
- Captured native workspace requests never entered `/artwork/`,
  `/lettering/create` or `/studio-export/`.
- General artwork checks passed for selection/generation, playback, loading,
  timeout/retry and contrast. They used disposable artwork, not customer files.
- Changed JavaScript passes Node syntax checks; `git diff --check` passes.
- Strict static UX audit: 86 pre-existing findings, 0 unresolved setting owners;
  not claimed clean. Count did not increase. External-listener buttons flagged
  by the static detector were exercised in browser tests.
- Browser screenshot rendering used the declared line fallback because headless
  Chromium lacked the required WebGL surface; hardware thread shading was not
  validated by that run.

Screenshots:
`outputs/lettering-workspace-desktop.png` and
`outputs/lettering-workspace-mobile.png`.
Browser logs are in `/tmp/lettering-workspace-final-browser.log`,
`/tmp/native-lettering-integration.log`, `/tmp/lettering-size-integration.log`
and `/tmp/lettering-workspace-regression.log`.

## Existing saved files

This integration did not change the native generator or rewrite existing machine
files. The previously saved customer-selected native version
`1eba7577a27f73d3cbb682f2424534034e87fbcc544af5cd2423536193f28679`
retains these pre-pass SHA-256 values:

- DST: `5a09fa248fcab658dbf1fd85984919b36585168b6f8a492f2de739f24f93a94c`
- PES: `71d9432af98808839725d0475011643f41e5251e31671ac2605880714ebcc328`

The running local app was restarted from this repository and checked over HTTP:
old bookmark redirects to the native workspace, the workspace/plan return 200,
and both downloads return 200 with the unchanged hashes above. The saved plan
has 961 stitches, 14 cuts, lengths 0.4–2.11 mm and no reported short stitches,
removed-area crossings, uncut travel violations or missing source columns.

No export baseline was deliberately changed in this pass. This is not a claim
that every customer design has been re-exported.

## Changed files in this integration only

The working tree contains earlier, uncommitted work; the following is the
bounded list changed by this integration, not the complete Git status:

- `src/embroiderly/lettering_workspace.py` — native workspace/data adapter.
- `src/embroiderly/lettering.py` — register that adapter.
- `src/embroiderly/preparation.py` — native bookmark redirect and typed-PNG guard.
- `src/embroiderly/static/lettering-workspace.js` and `.css` — existing workspace
  controls connected to the native recipe and preview.
- `src/embroiderly/static/lettering-native.js` — reusable controller events,
  workspace link and checked-download handling.
- `src/embroiderly/static/preparation.js` — native playback/display adapter and
  protection against applying picture operations to native letters.
- `src/embroiderly/static/lettering.js` — native Text focus and artwork-only copy.
- `src/embroiderly/static/design-size.js` — single native size owner; stale
  reference corrected.
- `src/embroiderly/static/refinement.js` and `sewout-review.js` — avoid
  image-only requests in a native project.
- `src/embroiderly/templates/artwork.html`, `lettering-native.html`,
  `lettering-tool.html` — adapter inclusion, link and accurate legacy wording.
- `tests/test_lettering_workspace.py`, `test_legacy_lettering_transition.py`,
  `browser_lettering_workspace.py`, `browser_native_lettering.py`,
  `native_workspace_matrix.py` — regression/integration verification.
- `UX-CONTRACT.md` and this checkpoint.

## Limits, honestly retained

- Enabled font: installed Ink/Stitch Small Font, nominal 4–6 mm. This is not
  arbitrary-font or arbitrary-language support. Unsupported characters stay
  visible with an error. Glacial Tiny remains disabled pending verification.
- Ordinary artwork fonts are not converted into native embroidery columns by
  this pass. The user must explicitly choose an available embroidery font.
- Native projects reopen via their saved link. They are not yet included in the
  image-only Recent designs library.
- Undo restores editable recipe fields and requires a new check; it is not a
  stored stitch-snapshot undo.
- Density, repeated-penetration risk, exact capital-height sizing, cap-specific
  sew order and physical readability/needle safety are not certified.
- Fresh uncached Ink/Stitch runs can differ. The identical-download result is
  for repeated downloads of one saved checked version, not proof of cold-run
  generator determinism.
- Physical sew-out: **pending**. Image-pipeline fidelity work: deliberately
  deferred at the user's request.

## Safety copy and repository state

Pre-pass source archive:
`/tmp/embroiderly-text-integration-RVdq6W/source-before.tar.gz`.
Existing customer images, machine files and unrelated edits were preserved.
No commit or push was made: this repository has no Git remote and no configured
author identity. No identity or remote was invented. The archive is local and
temporary, not an off-machine backup.

The frontend design skills were applied to preserve existing workspace controls,
native form behaviour and clear stale/check/save/error states, not introduce a
new visual theme.

