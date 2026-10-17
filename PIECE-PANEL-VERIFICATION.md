# Layers and Transform checkpoint — 7 October 2026

Implemented and verified for prepared colour artwork. This is not a claim that all requested capabilities or physical sewability are complete.

## Evidence

| Acceptance | Result |
|---|---|
| Simple / Advanced selected-piece screenshots | `outputs/piece-panel-verification/simple.png`, `advanced.png` |
| Linked 40 → 20 mm | Height 40 → 20 mm; 3,315 → 974 stitches (29.38% of original). Boundary/underlay costs prevent an exact quarter. Decoded median row spacing 0.2 → 0.2 mm, within the 0.2–0.3 mm file-grid range of the existing 0.25 mm preset. Real engine tested. |
| Too-small geometry | 0.5 mm piece retained, RED, generation withheld; Undo restores it. |
| Position | Browser drag updates X/Y live; typed −13.1 mm moves geometry. Engine test verifies exported centre at requested 10, −10 mm within 0.11 mm. |
| Lock | Disabled fields; pointer handler refuses dragging. Server tests reject manual, legacy, automatic and assistant mutation; explicit unlock required. Actual locked drag gesture not separately browser-tested. |
| Units | Settings owns mm/in; browser verifies 40 mm displays 1.575 in. Geometry remains mm. All transform dimensions share conversion code; every field not individually browser-tested in inches. |
| Undo | Resize restores PES and DST bytes exactly in real-engine test; browser Undo restores size/playback. |
| Grouping | Synthetic 26-piece design: 26 individual rows → 3 collapsed group headers. Nested Head visibility hides both children, retains all 26 pieces. No semantic recognition claimed. |
| Setting ownership | Table below. |
| Untransformed exports | All 18 existing machine files byte-identical to corrected safety baseline. Existing unsafe HELLO knockout remains refused. Naming-only edit also byte-identical. |

Baseline: 278 tests. Final suite: **292 passed**, 51.78 seconds on this machine. Browser suite `tests/browser_pieces.py` passed separately. It uses temporary synthetic designs, not customer uploads. A strict static UI audit still reports 78 pre-existing findings; not a clean audit. Older browser suites depending on a trashed customer fixture remain blocked and were not counted as passes. No participant study or physical sew-out was performed.

## Settings: one saved owner, shared presentation

| Setting | Saved owner | Editing surface |
|---|---|---|
| Piece name / group path | preparation options `piece_edits` | Properties header / Advanced group |
| Visibility | same | Row/group/header eye: equivalent commands to the same value, not independent states |
| Lock | same; enforced by server guard | Header lock; unlock explicitly before editing |
| X / Y / W / H / rotation | same, affine matrix in mm | Transform; canvas gestures share its command path |
| Proportion link | transient PiecePanel state | Transform; forced on in Simple |
| Nodes / audit / sew-order / swatch | derived inventory, read-only | Properties / Pieces |
| Stitch type | existing preparation `region_styles` | Existing illustrated gallery; selected Pieces supply targets |
| Units | SettingsService `units` | Settings only; Transform is an echo/conversion |
| Selection / group expansion / Simple–Advanced | transient PiecePanel state | Pieces and Properties |
| Global finished size / artwork preparation | existing preparation options | Existing artwork topics; blocked while a piece is locked |
| Thread colour / colour preservation | existing palette options | Existing Colours editor; preservation is not named Lock |
| Playback / total stitch count | generated plan, read-only | Existing transport and thread strip |
| Reference hoop | inventory reference, default 100 × 100 mm | Read-only tooltip and canvas; not a new machine setting |

The old region target select is hidden as a compatibility adapter. It is not a second visible selection editor. Simple/Advanced reuse the same fields. No per-piece density or stitch-length fields were invented.

## Capability gaps and boundaries

- Automatic anatomical names/hierarchy do not exist. Users can name/group pieces; fallback groups are spatial Upper/Middle/Lower, names Part n.
- Sew-order reordering is missing; therefore no drag handle is shown.
- Per-piece spacing, stitch length, staggers, underlay, pull compensation, entry/exit and tie-in/tie-off editing remain missing. Implementing these requires object-level generator options, persistence, audit and export regressions.
- Exact per-piece stitch-count attribution is missing; the transport reports the real total.
- The hoop is a rectangular reference, not integrated with a validated machine profile or clamp geometry. Real hoop validation remains unfinished.
- This transform path supports colour artwork, not portrait/ink-only pipelines; a design-wide border combined with piece geometry edits is explicitly refused.
- Source geometry changes invalidate saved piece identities rather than silently reattaching names or locks. Semantic remapping is missing.
- Area/bounding-span warnings are geometric heuristics, not comprehensive thin-neck, density, fabric or sewability assessment. Nothing is automatically deleted by a transform.
- Rotation of normal fill/satin uses existing engine options; decorative motif orientation and design-wide fill-angle override behaviour are not fully verified.
- A human-readable size analogy (such as coin size) is not provided; precise measurements are shown.
- Physical sew-outs, human usability studies and remaining legacy-surface checks are pending.

## Technical contract

Piece IDs come from original, untransformed contours. X/Y are relative to the initial outline union centre, aligned to the reference hoop centre; positive Y is down. W/H use actual outline bounds. Rotation is around the piece centre (combined centre for multi-select). Geometry lives in millimetres; generated machine files use their existing grid. Resize regenerates vector-derived stitches and reruns the existing release gate: it never stretches old stitch coordinates. Undo restores options and regenerates deterministically as one history operation. Failed generation does not overwrite saved options. Revision checks reject stale piece edits, and a per-design mutation lock serializes server writes.
