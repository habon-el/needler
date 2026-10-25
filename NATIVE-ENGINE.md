# Native stitch engine and embroidery fonts

Updated 2026-10-18. Needler needs no outside embroidery or drawing program. The engine
reads the same annotated SVG that the pipeline already writes and returns the
pyembroidery JSON plan consumed by the unchanged writers, repairs and release
gate. Generation runs in-process on Windows, macOS and Linux.

## Modules

| Module | Role |
|---|---|
| `svg_geometry.py` | Geometry-only SVG reader: paths (all commands), shapes, transforms, units, origin. |
| `stitch_engine.py` | Element → stitch blocks; locks, trims, colour changes, joins, 0.1 mm grid tidy. |
| `stitch_fills.py` | Tatami (sections, stagger, underlay, edge travel), contour, spiral ripple, meander stipple. |
| `stitch_satin.py` | Satin columns: rails + rungs or matched cross-sections, pull compensation, underlays. |
| `stitch_paths.py` | Running/bean stitch, min/max stitch length, chaining, inside-shape travel router. |
| `satin_font.py` | TrueType glyph → skeleton → strokes → cross-section satin columns → sewing order. |
| `embroidery_fonts.py` | Embroidery font catalogue, kerning, multi-line layout, in-letter travel connectors. |
| `vector_raster.py` | SVG rendering for typed lettering and SVG uploads (no outside program). |

Element attributes keep the existing `inkstitch:` namespace names (fill_method,
angle, row_spacing_mm, satin_column, zigzag_spacing_mm, lock_start, trim_after,
…) so saved designs, caches and tests stay compatible. Our own fonts add
`satin_pairs="indexed"`: rail vertex *i* is stitched to rail vertex *i*.

## Verified (2026-10-18, Windows 11, Python 3.13)

- Full suite: 529 passed, 1 skipped (local landing sample).
- Every artwork style (tatami, contour, ripple, stipple, motif, cross, embossed,
  satin, 3D satin, running/satin borders, black lines, bean) passes the release gate.
- Embroidery fonts, every glyph alone: 4 mm — 152/152 for both fonts;
  10 mm — 148/152 (small_font: 6 7 9 Å; lato_black: R e g Ä). Failing glyphs are
  blocked by the gate, never exported.
- Further formats from the checked PES: JEF, EXP, XXX, U01, PEC pass readback
  checks. VP3 is not offered: its readback turns travel into stitches.

## Small designs (added 2026-10-19)

- Designs may be 3–400 mm tall (was 10–400 mm).
- Areas no thicker than 4.5 mm (largest inscribed circle) that the user has
  not given a stitch style are sewn as satin columns (`fill_method="auto_satin"`,
  traced with the same machinery as the embroidery fonts) with 0.1 mm pull
  compensation per side; wider areas stay tatami.
- On very small designs one pixel is finer than the machine file's 0.1 mm grid.
  The stitched area's edge gets the grid rounding (0.05 mm) as allowance;
  with colour removal, stitches are instead kept 0.05 mm inside the edge and
  satin gets no outward compensation, so removed areas stay exact.
- Verified: a star at 10, 5, 4 and 3 mm, "ABC" text art at 5 mm and a badge
  logo at 60–8 mm all generate and pass the release gate. Strokes thinner than
  one thread (about 0.4 mm), e.g. badge lettering below ~20 mm, cannot sew cleanly.

## Known limits

- Physical sew-outs are still required; nothing here is a sewability certificate.
- Junction overlaps in fonts are automatic, not hand-digitized; dense letters
  (K, R, 8, &) have more overlap than a commercial font.
- Travel inside fills follows edges; complex artwork with many holes may still
  need cuts where no inside route exists.

## 3D puff (added 2026-10-19)

- Area style `puff` (`fill_method="puff_satin"`, `puff_foam_mm`), the design option `puff`
  (every area whose widest point is between the foam thickness and 6 mm: 3–6 mm on 3 mm foam,
  2–6 mm on 2 mm foam) and `puff` + `puff_foam_mm` on native lettering (same stroke rule; puff
  letters may go up to `puff_max_scale`, 22–26 mm, because strokes must be as wide as the foam).
- Revised 2026-10-20 after published puff digitizing guidance, so the foam stays tight:
  1. Placement: a 2.5 mm running line 0.3 mm inside each puff area, sewn on the fabric before
     the stop (`Block.placement`, `inkstitch:puff_placement` for lettering).
  2. Stop: the first puff block always changes thread, even to the same colour. PES lists the
     colour once and reads the change back as STOP; playback and the gates treat it as a change.
  3. Tack-down / perforation: a 1 mm running stitch around the area first (inside the sewn
     columns for lettering).
  4. Each column (`stitch_satin._puff_satin`): a 1.7 mm centre walk, a cap at the far end (short
     1 mm stitches side by side across the open end), a zigzag underlay back at 1.8 mm, a cap at
     the start, then satin at 0.22 mm. Pull compensation 0.4 mm (0.3 mm on 2 mm foam; 0 with
     colour removal), reduced so no stitch exceeds 6.9 mm: a split stitch cuts the foam apart.
  5. Tie-offs over foam are six 1 mm stitches (`PUFF_LOCK`) instead of four 0.6 mm ones.
  6. Caps only on open ends: an end that runs into another stroke is a join (`outline` for
     areas, `inkstitch:puff_caps` set by the font layout for lettering).
  7. The pull value is the outer edge (0.45 / 0.35 mm); the satin sews 0.05 mm inside it so the
     0.1 mm machine grid never puts a needle hole past the edge.
- Lettering verifier: the envelope raster gets one extra GRID cell, because filling the polygon
  could move its edge inward and eat the 0.07 mm quantisation allowance (flat Lato Black
  "HABONIMANA" at 14 mm failed on a 0.06 mm rounding). A real 0.18 mm crossing remains for flat
  Lato Black "HABONIMANA" at 15 mm (not puff); not yet fixed.
- Not done yet: overlapping joined columns by 3+ stitches, and slower speed / looser tension are
  only in the sewing instructions (Check stitches), not in the file.
- Verified: a badge (ring + lettering puffed, star and background flat) and "PUFF" Lato Black
  lettering at 22 mm (3 mm foam) and 15 mm (2 mm foam) pass the release gate. The foam height in
  the 3D view is illustrative; foam brands and machines differ, so a sample sew-out is required.

## Satin and lettering automation (added 2026-10-24)

Feature-by-feature roadmap: `FEATURE-ROADMAP.md`.

- Auto split: flat satin stitches longer than 7 mm are divided at points that move row to row
  (`stitch_satin.split_rows`), so the holes don't line up into a groove. `inkstitch:satin_split_mm`
  (0 = off). Puff keeps its own 6.9 mm rule.
- Auto spacing: narrow columns sew up to 0.06 mm more open, columns over 5 mm up to 0.03 mm denser
  (`auto_spacing`). On for auto-satin areas; `inkstitch:satin_auto_spacing` on satin columns.
- Auto underlay by median column width (`auto_underlay`): under 1.5 mm none, to 3 mm centre walk,
  then edge run, plus zigzag from 6 mm. On for auto-satin areas; `inkstitch:satin_underlay="auto"` on columns.
- `inkstitch:pull_compensation_percent`: extra pull as a share of the column width.
- Lettering by capital height (`embroidery_fonts.size_profile`): under 5 mm no underlay and spacing at
  least 0.42 mm below 6 mm; 5–10 mm centre walk; over 10 mm edge run, plus zigzag on strokes over 3.5 mm.
- Fabric presets reach lettering: the Fabric menu on the lettering panel adds half of the fabric's
  extra satin pull (at most 0.15 mm) to the font's; the height solver uses the same value.
- Closest join: each colour's areas are sewn nearest-first from where the last area ended (`engine.closest_join`).
- Thresholds are our own, informed by published digitizing guidance. Physical sew-outs are still pending.

## More stitch types (added 2026-10-24)

- Outlines on running-stitch strokes, `inkstitch:outline_style` = `backstitch` (forward 2.5 mm, back 30%),
  `stemstitch` (slanted, overlapping by half; slant at most 40% of the stitch length), `blanket`
  (spikes every `outline_spacing_mm`, into closed shapes unless `blanket_side="outside"`) or `zigzag`;
  width `outline_width_mm`. Offered as subject-border styles; the release mask covers their band.
- Fills: `step_fill` (tatami with chevron needle offsets, `stitch_fills.STEP_PATTERN`), `gradient_fill`
  (rows from `row_spacing_mm` to `gradient_open_spacing_mm`, default 1.6, no underlay; sections are
  cut, never travelled across, and branching skips it) and `radial_fill` (rays from the centre that start
  where neighbours are a row apart; tatami when rays reach under 85% of the area). Offered as area styles.
- Shortening: on the inside of tight satin curves every other stitch stops 35% short
  (`stitch_satin.shorten_inner`); on for auto satin, `inkstitch:satin_shortening` on columns.
- Verified: each fill and border on a 60 mm badge passes the release gate (tests/test_stitch_types_engine.py).

## Lettering layout (added 2026-10-24)

- `embroidery_fonts.layout(..., letter_spacing_mm, line_spacing, baseline, radius_mm, sequence)`; checked by
  `small_lettering.layout_options` (spacing -2 to 10 mm, line spacing 70-250%, radius 5-1000 mm).
- Each letter has one affine placement used for its columns, fill outline and travel area. Arcs
  (`arc_over`, `arc_under`) keep letters rigid, centred on the circle and turned to its tangent; one line only;
  the size still means letter size. Text longer than 95% of the circle is refused.
- `sequence='centre'`: middle letter to the right end, then left of the middle to the left end (caps).
- Touching letters (script fonts) are joined by travel inside both letters' columns instead of a cut
  (`_join_touching`): Pacifico "Hello" 4 cuts to 1, Lobster 7 to 4. Separate letters keep their cut.
- Recipes store only non-default layout keys, so earlier saved lettering keeps its cache key.
- UI: one collapsed "Layout" section on the lettering panel (baseline, radius for arcs, spacing, letter order).

## Auto-digitizing roles (added 2026-10-24)

- Digitize for me leaves out a plain border colour (`colour_knockout.proposal_patch`) unless the request
  says to keep the background. Before, a white background was sewn as fill (badge: 18,794 to 8,193 stitches).
- Hairlines: pixel-thin pieces at least 1 mm long (`fill_coverage.HAIR_MIN_MM`) are sewn as a run along the
  line and back instead of blocking generation; areas thinner than 0.45 mm (`engine.HAIRLINE_MM`) are a run
  around their edge instead of satin. Shorter specks are still reported.
- `outlines: true` (+ `outline_colour`): one running line along every colour boundary and the outer edge,
  traced by the line-art router and sewn last. Panel: "Add a dark outline around each colour".
- Detail slider (1 fewer … 5 more) sets `floor_mm2` 8 / 3 / 1 / 0.5 / 0.25 mm²; the middle keeps the default.

## Appliqué (added 2026-10-24)

- Area style `applique` (`fill_method="applique"`, `applique_cover_mm`, default 3): `stitch_engine._applique`
  sews a 2.5 mm placement run on the edge, then after a stop an open zigzag tack-down 0.8 mm inside it,
  then after a stop for trimming a satin cover centred on the cut edge (dense zigzag where corners are too
  sharp for satin rails). The inside is not stitched. Pieces narrower than twice the cover are refused.
- Stops: `Block.stop_before` forces a change to the same thread; PES reads it back as STOP (2 per piece).
- The release mask includes the cover band outside the edge (engine.py).
- Export cutting: `applique-cut.svg` (pieces at actual size, mm) next to the machine files;
  `/applique-cut/<prepared name>`; a link appears in Save and download when the design has appliqué.
- Verified in the studio: approve subject, choose Appliqué for an area, stitches build, cutting file downloads.

## Holes (added 2026-10-24)

- Option `area_holes` ({area id: "fill"}, checked by `region_stitches.hole_choices`): the area is sewn from its
  outer outline only, so stitches run straight across its holes. A hole under another colour is sewn over
  (no gap can open at its edge); an empty hole is filled. The hole counts as intended stitching in the
  release mask. Works in the colour loop (engine.py) and the piece path (piece_generation.py).
- Area inventory reports `holes` and `holes_filled`; the area style panel shows "Sew over holes in this
  area" only when the selected areas have holes. Cutting a hole is done with Erase area.

## Piece editing (added 2026-10-24)

- New piece commands (`piece_layout.change`): `mirror` ("x" left-right, "y" top-bottom; the stored rotation
  flips so fill rows mirror too), `rotate_by` (a delta, the ±15°/45° buttons), `skew` (−60° to 60°, around the
  selection centre), `duplicate` ([dx, dy] mm) and `delete` (copies only).
- A copy is a `piece_edits` entry with `source` = the original's id: it reuses the original's outline and
  colour with its own transform, style, lock and holes choice; at most 100. Copies force the piece path and
  are not "stale" area styles. Locked pieces refuse every command.
- Panel: one row of buttons under Rotation (⇋ Mirror, ⇅ Mirror, ↺ 15°, ↻ 15°, ↻ 45°, Duplicate, Delete copy
  for copies) and a Skew ° field.
- Knife (`knife` command, [[x1,y1],[x2,y2]] mm): cuts one piece along the extended line. Each part is a
  piece entry with `source` (colour) and its own `rings` (picture pixels before transforms), keeping the
  piece's transform and style; a cut original is marked `cut` and leaves the list. Parts can be cut again,
  moved, duplicated and deleted. Panel: ✂ Knife, then drag a line across the selected piece.
- Appliqué release coverage: `stitch_engine.applique_coverage` marks where the placement, tack-down and satin
  cover really sew (mitred corners included), in both the colour loop and the piece path; the piece-path
  canvas gets a 5 mm margin when a design has appliqué. The engine cache key includes the release mask,
  so a mask-only change can no longer reuse an outdated check.

## Satin corners, double zigzag, density (added 2026-10-24)

- Double zigzag underlay: `zigzag_underlay="double"` adds a second pass back with peaks between the first
  pass's; auto underlay picks it for columns 8 mm and wider.
- Cap corners: `borders.satin_rails` cuts any mitre longer than twice the half-width back to that length
  (corners sharper than about 60°) instead of refusing the border; only near-hairpins are refused.
- Density (`density`: lighter / normal / denser = spacing × 1.12 / 1 / 0.9) scales fill row spacing and satin
  spacing in `generation_policy.apply`; puff keeps its own. Menu "Density" next to Fabric.

## Direction and order (added 2026-10-24)

- `area_angles` ({area id: degrees}, −180 to 180; 0 = horizontal rows, positive = rising to the right),
  checked by `region_stitches.angle_choices`, overrides the automatic fill angle in the colour loop and the
  piece path (absolute on the hoop). Style panel: "Stitch direction °", empty = automatic.
- Auto start: `stitch_engine.generate` passes the last stitch so far to each element; tatami starts at its
  nearest corner.
- Piece path: pieces are grouped by thread colour (stable, first-seen order), so copies and cut parts do not
  add colour changes.

## Drawing shapes (added 2026-10-24)

- Pieces panel → "Draw a shape": Rectangle and Ellipse (drag corner to corner), Polygon
  (click each corner; double-click, Enter or clicking the first point closes it; Esc cancels)
  and Freehand (hold and draw). The Thread colour picker sets the shape's colour.
- Server command `piece_command = {ids: [], field: 'draw', value: {shape, points, colour}}`;
  points are millimetres on the hoop. The outline is stored in `piece_edits` as
  `{drawn: '#rrggbb', rings, name}` in picture pixels, so every piece command (move, size,
  rotate, mirror, skew, duplicate, knife, style, stitch direction) works on it.
- A self-crossing freehand line keeps its largest enclosed part; shapes under 1 mm² are refused.
- Only shapes found in the picture set the hoop origin, so drawing never moves other pieces.
- Deleting a drawn shape also removes its copies and cut parts.

## Text page ease of use (added 2026-10-25)

- Shape row (Straight / Arch / Smile) and a Curve slider in degrees under the font. `arc_degrees`
  replaces the radius: the circle follows the words' length (`radius = width / angle`), so the curve
  looks the same for any words and always fits. Lettering saved with `arc_radius_mm` keeps it until
  the slider moves. Reopening saved text now restores its shape, curve, spacing and fabric.
- The instant preview draws the curve with the same placement as the stitches.
- `/lettering/native/advice` (`small_lettering.advice`): every problem at once, each with a fix the
  screen applies in one click: a puff-ready font, the allowed height, one line for curves, max width.
  The width is measured from the laid-out letters (`laid_out_width`, ~0.05 s, within 0.5 mm of the
  stitched width), not estimated.
- "Max width (mm)" (was "Space available"), default 100 mm; "For" item presets; Fabric and
  "Spacing & letter order" on the visible panel; thread names under the colour
  (`/lettering/native/thread`).
- Ask AI (`text_ai.py`, `/lettering/native/ask`): Claude calls `check_text` (the advice check, no
  stitches) and `finish`; at most 8 turns, the last one asks it to finish; whatever is left is fixed
  with the check's own fixes. Shares auto-digitize's spending limits. About $0.10 per request.

