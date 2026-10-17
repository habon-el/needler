# Output-safety pass — 5 October 2026

## Handoff

The six requested corrections are implemented and committed locally on
`fixes/output-safety-20260930`. Safety snapshot: `8611112`, tag `before-fixes`.
No push is claimed. Customer images, model files and credentials were not added.
This closes implementation of this bounded pass, not production-launch certification.

## Verification

- Before: **264 pytest tests passed**. Final: **278 passed in 33.56 seconds**.
- Regression failures were actually exercised before correction: DST zero cuts
  versus PES one; warm-cache command-equality refusal; invalid download HTTP 200;
  missing cleanup review/save accepted; Baby counters filled; puff controls present.
- Follow-up regressions also demonstrated the blank DST label changing, altered
  verification context still hitting cache, and smoothing bypassing detail review.
- Isolated Chromium: actual 0.5 × 0.5 mm / 0.25 mm² warning, truthful messages,
  Keep it / Let it go / Undo, nine hole controls, explicit fill/reopen and 390px
  reflow passed. No customer design was changed by those checks.
- JavaScript syntax checks and `git diff --check` passed.
- Original 13-word background-removal batch: **13/13 passed**, including JPEG,
  reverse lettering and Baby 0689 at 10 mm. All nine small counters remain open;
  zero solid-ink core loss or retained background in these samples. Repeat images
  match and source images remain unchanged. No claim about all possible artwork.
- Original circles: warm/cold PES bytes identical; warm/cold DST bytes identical.
- Two older browser scripts (`browser_workspace.py`, `browser_workspace_states.py`)
  could not run their workflows: their hard-coded customer fixture is in Trash.
  They timed out on the Trash screen. It was not restored merely to pass tests.
- Strict UI audit still reports 78 pre-existing actionless-button findings. This
  static audit is not green; it does not replace the focused browser evidence.
  A whole-application accessibility/interaction certification is not claimed.

## Decoded trim parity

Old counts use the audit's stock reader. New DST counts decode the documented
explicit three-jump signature, including redundant cuts after colour changes.
Machine settings must match; no physical-machine test was performed.

| Fixture | Before PES / DST | After PES / DST |
|---|---:|---:|
| Shape | 2 / 0 | 1 / 1 |
| Text L | 0 / 0 | 0 / 0 |
| Photographic | 162 / 157 | 162 / 162 |
| Original circles, normal | 1 / 0 | 1 / 1 |
| Original circles, knockout (cold baseline) | 1 / 1 | 1 / 1 |
| Original HELLO, normal | 4 / 1 | 4 / 4 |
| Tatami preview | 0 / 0 | 0 / 0 |
| Satin preview | 0 / 0 | 0 / 0 |
| Raised satin preview | 0 / 0 | 0 / 0 |
| Original HELLO, knockout | Generation refused | Still refused; no released pair |

All nine produced pairs have matching decoded cuts. The tenth case has no
approved pair and is not counted as a successful generation.

## Exact changed machine fixtures

Old six reference hashes were reproduced and checked against the committed
baseline before comparison. Full hashes and refusal locations are retained in
`OUTPUT-SAFETY-RESULTS.json`. Original fixture files were not overwritten.

Changed:

- `shape.pes`: first-move normalization (`full_jump=False`) preserves the sewn
  move following a jump, avoiding an added positioning jump/cut. **Not solely a
  DST trim-byte change.** This is an explicit acceptance exception, not hidden.
- `shape.dst`: shared PES command stream and explicit cut encoding.
- `photographic.dst`: explicit cuts preserve all 162 PES cuts.
- `two-circles-normal/design.dst`: explicit cut before the crossing.
- `hello-world-normal/design.dst`: explicit cuts match the four PES cuts.

The other 13 machine files across these nine fixture pairs are byte-identical,
including both knockout-circle files and both Tatami/satin/raised-satin previews.
The initial unrelated Untitled-header change was corrected before handoff.
The shared release gate itself does not rewrite machine files. The old module/
export hash baseline was not silently re-recorded to bless intentional changes.

## Remaining limits — do not mistake refusal for repaired stitch geometry

- Original circles are now format-consistent and cache-consistent, but their
  generated 0.22 mm span is rejected by the requested 0.3–7 mm release policy.
- Normal HELLO and Tatami have 0.20 mm spans and are likewise blocked, with a
  location. Satin and raised-satin audit samples pass both download checks.
- Knockout HELLO still fails its existing crossing verification. It is not offered
  as safe output. Resolving its stitch geometry is unfinished work outside these
  release-gate corrections; no export-success claim is made for it.
- The screen retains the existing one-pixel mask-boundary allowance. A raster
  check and matched cuts do not establish actual fabric/machine performance.
- True foam puff is still missing. Its misleading checkbox/height slider are
  removed; layered satin and lighting are not foam-puff digitizing.
- Small-hole shape labels are tentative. Ambiguous holes remain open; explicit
  user filling is reversible. There is no claimed semantic letter recognition.
- Three controlled real sew-out photographs and physical machine validation
  remain unavailable. No diagnostic or sewability certification is implied.

## Commits

1. `1ce106a` — explicit DST/PES cut parity.
2. `38bad98` — routing-aware recolour cache.
3. `bf5a226` — one fail-closed machine-file download gate.
4. `160e86e` — real-size cleanup review and truthful messages.
5. `965a4c7` — small counter preservation and explicit speck filling.
6. `3c2dcf3` — remove unsupported puff controls.

Follow-ups: `d53039a` preserves DST labels; `18779a8` binds cached output to
verification context; `7b1f8c0` includes smoothing in cleanup review.

Implementation details: `OUTPUT-SAFETY-FIXES.md`. Reproduction:
`tests/verify_output_safety.py`, `tests/browser_cleanup_review.py`, and the new
per-fix pytest regressions. The diagnostic script requires the original local
audit fixtures and does not manufacture a passing result if they are missing.
