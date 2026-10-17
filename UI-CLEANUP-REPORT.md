# UI cleanup checkpoint — 14 October 2026

**The layout-only update is implemented and tested. The entire brief is not complete:** the capability gaps below need a separately approved change. No stitching, export writer, release check, font recipe or generation setting was changed.

Restore point: local commit `51527e1`. Git was clean immediately after that commit. No GitHub operation was performed. The app runs with `PYTHONPATH=src:work/deps python3 -m embroiderly.web` at http://127.0.0.1:5050.

## What changed

- Added equal **Type text / Upload image** entry buttons. Type text opens the existing native editor empty; it does not generate or save on opening.
- Consolidated the workspace into **Edit → Check stitches → Save and download**. The separate visible Stitches tab and View stitches link are gone. Original handlers remain internal targets.
- Removed visible duplicate check/save/download actions. Save design stays in the header with a confirmed Saved/Unsaved label. The single download choice delegates to the existing release handlers.
- Moved native results and file/route warnings into Check stitches. Moved explanations and existing image topics into closed Details/Expert settings. Both text and image essential panels fit at 1366 × 768 when closed.
- Moved library rename into the card, retaining validation, cancellation and revision checks. Generated IDs are replaced visually by date-based image labels; stored names are untouched until renamed.
- Reworded “source columns” as “letter parts,” “retracing locks” as explained tie-off stitches, and WebGL fallback as a plain flat-preview explanation. Installed-font attribution remains.

## Evidence

| Fixture | DST commands before → after | PES commands before → after | Full decoded command comparison |
|---|---:|---:|---|
| Hello World, nominal 5 mm | 858 → 858 | 857 → 857 | Identical in each format |
| Green rectangle image | 886 → 886 | 885 → 885 | Identical in each format |
| tiny, nominal 4 mm | 259 → 259 | 259 → 259 | Identical in each format |

All six files were downloaded through the app and read back. Coordinates and command flags—including jumps and trims—match exactly, not just stitch counts. Hashes: `ui-before-exports.json` / `ui-after-exports.json`. This checks unchanged saved designs, not fresh cold-run generator determinism.

- Before: **387 tests passed**. After: **391 tests passed** (four new presentation tests).
- **33 browser assertions passed** in the final run: validation, duplicate actions, save/download state, undo, inline rename, search, narrow viewport, high contrast, offline retry, stale reply and failed approval. An earlier fresh-design run also exercised approval before the first download.
- Changed JavaScript passes `node --check`; `git diff --check` passes.
- Strict static audit: **87 findings, not a clean pass**. 86 are “actionless button” heuristics that do not follow external vanilla-JS bindings; one is a textarea rule whose `resize:none` is defined in CSS. New workflow actions and textarea were checked in the browser. The full set of legacy surfaces was not retested; no blanket dismissal is claimed.
- Headless browser used a flat preview; hardware-accelerated rendering, physical sew-out and testing by a real novice were not verified.

## Before / after screenshots

All screenshots are local, at 1366 × 768. Before did not have separate workflow steps or an Expert settings section: those images show the equivalent old surfaces, not invented prior states.

| Surface | Before | After |
|---|---|---|
| Start | [Before](/home/guyha/Documents/Codex/2026-09-04/files-mentioned-by-the-user-embroiderybuildprompt/ui-before-start.png) | [After](/home/guyha/Documents/Codex/2026-09-04/files-mentioned-by-the-user-embroiderybuildprompt/ui-after-start.png) |
| Library | [Before](/home/guyha/Documents/Codex/2026-09-04/files-mentioned-by-the-user-embroiderybuildprompt/ui-before-library.png) | [After](/home/guyha/Documents/Codex/2026-09-04/files-mentioned-by-the-user-embroiderybuildprompt/ui-after-library.png) |
| Edit | [Before](/home/guyha/Documents/Codex/2026-09-04/files-mentioned-by-the-user-embroiderybuildprompt/ui-before-edit.png) | [After](/home/guyha/Documents/Codex/2026-09-04/files-mentioned-by-the-user-embroiderybuildprompt/ui-after-edit.png) |
| Check stitches | [Before](/home/guyha/Documents/Codex/2026-09-04/files-mentioned-by-the-user-embroiderybuildprompt/ui-before-check.png) | [After](/home/guyha/Documents/Codex/2026-09-04/files-mentioned-by-the-user-embroiderybuildprompt/ui-after-check.png) |
| Save/download | [Before](/home/guyha/Documents/Codex/2026-09-04/files-mentioned-by-the-user-embroiderybuildprompt/ui-before-download.png) | [After](/home/guyha/Documents/Codex/2026-09-04/files-mentioned-by-the-user-embroiderybuildprompt/ui-after-download.png) |
| Settings closed | [Before](/home/guyha/Documents/Codex/2026-09-04/files-mentioned-by-the-user-embroiderybuildprompt/ui-before-settings-closed.png) | [After](/home/guyha/Documents/Codex/2026-09-04/files-mentioned-by-the-user-embroiderybuildprompt/ui-after-settings-closed.png) |
| Expert details | [Before](/home/guyha/Documents/Codex/2026-09-04/files-mentioned-by-the-user-embroiderybuildprompt/ui-before-settings-expert.png) | [After](/home/guyha/Documents/Codex/2026-09-04/files-mentioned-by-the-user-embroiderybuildprompt/ui-after-settings-expert.png) |

Additional: `ui-after-image-edit.png`, `ui-after-new-text.png`, `ui-after-narrow.png`. Screenshots and test machine files remain local and are excluded from commits; no customer images are committed.

## Capability gaps — not built in this layout-only pass

1. **Unified native-text/image library:** native text is still an immutable saved-link model, outside DesignLibrary. A persistent text-project index and rename integration need metadata/controller work. The library currently lists image projects only.
2. **Names and placement:** old uploads did not retain original filenames; layout cannot recover them. Placement is not stored for native text. Date-based fallback labels are explicit, not subject guesses.
3. **Native text spacing / expert stitch settings:** no editable spacing, underlay, density or pull-compensation owner exists for native fonts. No dummy controls were added.
4. **Measured capital-height colour indicator:** the native size is nominal, not an actual capital measurement. The UI says so; it does not pretend nominal 5 mm proves a 5 mm capital. Width × height is the existing checked-file measurement.
5. **Per-letter fixes and grouping:** reports contain command locations, not mapped letter identities or repair proposals. All existing failures remain visible; no unsupported Fix it button, new repair or silent change was added. Image review/repair tools remain reachable under their existing owners.

The requested scope question about library integration is still awaiting a choice. No expansion into new embroidery capabilities was taken.

## Changed code

Presentation: `templates/artwork.html`, `landing.html`, `library.html`, `lettering-native.html`; `static/workflow.js`, `workflow.css`, `start-choices.css`, `library.js`, `lettering-native.js`, `lettering-workspace.js`, `stitch-layer.js`. The preparation controller has only a successful-save UI notification and a wording change. `lettering_workspace.py` adds the empty editor view only. Project instructions/design contract and verification scripts/tests were also added or updated.
