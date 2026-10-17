# Output-safety corrections — 30 September 2026

Safety snapshot: `8611112`, tag `before-fixes`. Images, credentials, customer
uploads and model assets are excluded. Baseline: 264 tests passed.

## Fix 1 — explicit DST cuts

The original two-circle regression failed: decoded DST 0 trims, PES 1.
The raw engine plan contains a JUMP, not a TRIM. PES/PEC serialization inserts
the cut, so setting `explicit_trim` on the original plan alone does not fix it.
`machine_files.write_pair` now uses written PES as the canonical command stream
and emits DST with pyembroidery `trim_at=3`, with normalization disabled after
splitting travel into DST-representable distances. Every explicit TRIM becomes
three jumps: +0.2/+0.2 mm, -0.4/-0.4 mm, +0.2/+0.2 mm (net zero).

The application decodes this exact signature rather than guessing from travel
distance. The stock decoder suppresses redundant cuts after colour changes;
our decoder preserves those explicit cut commands as well. No vendor code was
changed. Configure the machine for the three-jump convention; a real machine
sew-out is still required, and universal machine support is not claimed.

Both formats now share PES readback rather than independently normalizing the
input plan. PES uses full_jump=False (already used by the portrait exporter) so
the first sewn move after a jump is not converted into another positioning jump.
Without that setting the legacy first-move regression loses a 2 mm sewn move.
Consequently some PES bytes also change; this is not honestly describable as a
DST-only change. Fixture comparisons must distinguish this normalization
correction from the explicit DST trim encoding.

## Fix 2 — routing-aware cache eligibility

The new warm/cold circles test was run before the fix and failed with the
command-equality refusal from engine.py. After the fix, 11 focused tests pass,
including identical PES and DST bytes for warm/cold knockout circles. Cache
eligibility now includes knockout mode, mask, scale, writer and routing versions.
Old manifests without that policy do not qualify. The equality guard is retained.

## Fix 3 — one download release gate

The new endpoint regression failed before this change: invalid PES bytes returned
HTTP 200 when playback.json existed. All PES/DST download routes now call the
same readback gate. It snapshots both files, checks hashes and bound source-mask
context, enforces 0.3–7 mm nonzero spans, rejects stitches/uncut travel across
removed areas, and rejects cumulative uncut travel above 6 mm. It returns the
exact checked bytes. Refusals include a plain sentence and command coordinates.

This is conservative exposure screening, not future-coverage inference. Zero
movement needle penetrations are not treated as sewn spans. Legacy files without
context require regeneration. Source-mask checking retains the existing one-pixel
boundary allowance; raster resolution is not physical validation. Generation and
preview remain available when release fails, so rejected output can be inspected.

## Fix 4 — measured cleanup review

The original 0.5 × 0.5 mm case now has a 0.25 mm² review entry at
[48,48,50,50], not a padded contrast box. Save, generation and size-set generation
refuse pending cleanup decisions. Keep it restores source pixels; Let it go
accepts that measured removal. Existing options/history own both decisions.

Both new backend regressions failed before this correction (missing review and
save incorrectly returning 200). They pass now. The real Chromium workflow also
passed actual-size text, absence of both false reassurance messages after removal,
Keep it, Let it go, Undo and 390px reflow. Full suite at this checkpoint:
273 passed (baseline 264). No customer designs were changed by this check.

## Fix 5 — small letter holes

New Baby 0689 regression failed before the fix: 943 core pixels across nine
real counters were filled. After: zero counter pixels filled, nine reviewable
parts, zero silent fills. Circularity, solidity and aspect ratio provide tentative
shape labels, not semantic certainty. Every small enclosed hole remains open by
default; Fill this speck is explicit and reversible. Small-hole presence pauses
edge smoothing rather than risking closure. White-part restoration remains separate.

19 focused tests passed. Real Chromium verified all nine controls, filling one,
reopening it and narrow layout. The original 13-word upload/propose/apply/save/
repeat batch now passes 13/13, including all nine 0.1372–0.4306 mm² Baby counters.
All cases measured zero background retained, zero solid-ink loss, zero filled
counter-core pixels, immutable sources and identical repeat previews. Evidence:
 /tmp/fixed-lettering-qxl0pzc9/results.json (local diagnostic, not a sew-out).

## Fix 6 — remove unsupported foam-puff controls

The new regression failed on the original puff checkbox. Both the checkbox and
height slider, their event bindings and the puff rendering branch are removed
from design.html. The page says plainly that foam puff digitizing is unavailable.
Existing fill/border preview remains; no new stitch-generation capability added.

Capability gap: true foam-puff digitizing is not implemented. It would need
foam-aware satin geometry, end caps/perforation, validated underlay and physical
sew-outs. Raised-light rendering and layered satin are not substitutes.

## Remaining evidence

Per-fix tests, release-gate checks and final fixture comparisons are recorded
as the corrections are completed. This file is not a physical sewability claim.
