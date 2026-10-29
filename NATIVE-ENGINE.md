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

## Lessons from professional designs (added 2026-10-25)

- Smart satin (`engine.thin_limbs`, `stroke_like`): a plain area thicker than 4.5 mm is opened with a
  4.5 mm disc; what the opening removes, in parts of at least 1.5 mm² that are at least twice as long
  as wide, is a limb. The body keeps its tatami and each limb becomes `auto_satin` (columns along the
  centre line, rails from the true outline, so the satin tapers with the shape), grown 0.4 mm into the
  body. A body that would fall apart keeps the area whole. Long bands (length >= 4 x width) up to 6.5 mm
  wide are satin. `smart_satin: false` turns limbs off. Satin column joins may travel within the
  pulled edge (pull + 0.1 mm), which removed cuts between columns.
- The Satin style tries the straight converter first, then the shape-following satin for any area up
  to 8 mm wide (`region_stitches.satin_reason`); 3D satin still needs a straight band (`raised_reason`).
- `sew_order: 'layers'` (`engine.layer_passes`): each part's depth is how many parts of other threads
  enclose it; parts are sewn by depth, then colour order; fills still grow under later parts.
- `outline_colour: 'auto'`: each boundary pixel belongs to the part on top (the later one), outlined in
  a darker shade of its thread (`engine.darker`). Auto-digitize outlines default to auto.
- Area style `shaded`: the area's tatami plus a gradient in a 30% darker shade across it.
- Border `border_inner: 'triple'`: a triple-stitch ring 1.2 mm inside the border band.
- Lettering `frame` (circle, oval, square, diamond, hexagon, shield, heart), `frame_mm` 1.6-5 and
  `classic` (2-3 initials, middle x1.35): the frame is a satin column (`borders.satin_rails`) around
  the letters with corners rounded by 2.5 x its half width, sewn last; it counts as sewn area in the
  release gate like the letters. Not with 3D puff yet.

## Click to fill (added 2026-10-25)

- `piece_command {field: 'click_fill', value: {point (mm), colour, holes}}`; the route passes the
  prepared artwork (`piece_layout.change(..., image=)`). The sewn pixels are grown by 0.4 mm to bridge
  small gaps, the clicked empty pixel's 4-connected space is taken (refused if it reaches the image
  edge: open to the outside), grown back to the lines and 0.3 mm under them.
- Stored like a drawn shape (`drawn`, `rings` with holes) plus `under: true`; `piece_generation`
  sews `under` pieces first, so the lines and (without holes) the parts inside lie on top.
- Choosing any drawing tool switches to the Stitch artwork view, where clicks reach the pieces.

## Open stitched lines (added 2026-10-25)

- `draw` with shape `line` (clicked points) or `freehand_line` (simplified 0.1 mm) and
  `stitch: 'running' | 'triple'`; stored as a drawn piece with one open ring and `line`.
- Inventory reports a line's length instead of an area; lines cannot be cut or given area styles.
- `piece_generation` sews a line as a running stitch (2.5 mm) or a triple stitch (2.2 mm,
  `bean_stitch_repeats` 1); a 0.6 mm band along it is sewn area for the release gate.

## Printable worksheet (added 2026-10-25)

- `worksheet.py` builds one self-contained HTML page from the saved stitch plan (`playback.json`
  for pictures, `workspace_data` for lettering): routes `/worksheet/<prepared name>` and
  `/lettering/native/<key>/worksheet`; the Save and download step links to it.
- Sewing time uses the studio's assumptions (600 stitches/min, 2 s per cut, 15 s per thread change).
  Hoop: the smallest of 100x100, 130x180, 160x260, 200x200, 200x300, 240x350, 360x200 mm that fits
  with 10 mm to spare, either way round. Threads: the one chart with the lowest total colour
  difference over the design's colours. Puff and appliqué stops are noted on their thread.
- The picture is an SVG in millimetres, so printing at 100% gives an actual-size placement template.

## Outlines per part (added 2026-10-25)

- `area_outlines: {part id: {stitch: running|triple|satin, offset_mm 0-6, width_mm 1.2-5, colour}}`,
  set with the piece command `outline` (None removes it); checked by `part_outlines.choices`.
- `part_outlines.add` draws the part's rings (offset outward with round joins when a gap is set):
  running 2.5 mm, triple 2.2 mm with `bean_stitch_repeats` 1, or satin halves (`borders.satin_rails`).
  For satin each edge line is smoothed on its own (simplify 0.15 mm, then closing and opening by
  2.5 x the half width) and points closer than 0.15 mm are dropped, so pixel-traced edges and hole
  edges do not fold. The band it sews is added to the release mask.
- Engine and piece path both collect outlines with their parts and sew them after all fills; the
  piece path widens its canvas by the outline's reach. Locked parts keep their outline.

## Sewing order by hand (added 2026-10-25)

- `sew_sequence: [part id, ...]` (at most 2000, no repeats), set with the piece command `sew_order`
  (a full list with every part in its new place; None goes back to automatic); checked by
  `sew_sequence.choices`. The order moves no piece, so the lock guard ignores it.
- `sew_sequence.arrange`: named parts follow the list; a part not named (new, redrawn, or a speck
  too small to be a part) keeps its automatic place right after the part sewn before it.
- Colour generator: after the automatic order (colours or Best look), `engine.hand_passes` cuts
  each thread into one pass per part (its outer ring minus its holes; same ids as the Pieces panel)
  and sews them in the chosen order. Fills still reach under the parts sewn after them.
- Piece path: `piece_generation.append` reorders the pieces the same way.
- The stitch result carries `sew_parts` (part ids in sewing order); the Pieces panel numbers its
  rows by it and builds the new list from it: Sew earlier / later swap the selection one step,
  Sew in the order I picked puts the picked parts together, in click order, at the first one's place.

## Hoop picker (added 2026-10-25)

- `hoops.py`: `CATALOG` of sewing fields (mm, as the hoop sits on the machine) for common sizes
  and machine brands; ids are `<brand>-<w>x<h>`. The user's own hoops are kept for every design
  in `work/hoops.json` (`mine-<hex>`, name up to 40 characters, 10-1000 mm, at most 50).
  Routes: `GET/POST /api/hoops`, `DELETE /api/hoops/<id>`.
- A design keeps `hoop_id` and `piece_hoop_mm` = [width, height] as placed; Turn swaps the two.
  `piece_layout.inventory` checks pieces against that field (red "outside the hoop") and refuses
  an id that is not `[a-z0-9-]{1,60}`. The hoop moves no piece, so the lock guard ignores it.
- `hoop-controls.js` (inside the fabric box): the menu, Turn, a fit note from the visible parts'
  outlines (or the canvas), "Show on canvas" (per browser) and My own hoop. The Pieces panel
  paint draws the hoop, centred on the design, with its name. Changing the hoop is a design
  setting like the fabric: stitches are generated again.
- The worksheet names the chosen hoop and, when the design is larger, says so and suggests the
  smallest common hoop that fits.


## Named colourways (added 2026-10-25)

- `colourways.py`: per design in `work/decisions/<name>.colourways.json` (copied with the design
  like its other sidecars), a list of `{id: cw-<hex>, name, threads: {merges, border_colour?}}`;
  names up to 40 characters, unique ignoring case, at most 20. `threads` holds only thread
  choices: `merges` (artwork colour -> thread colour, the same option the swatches set) and the
  border thread. Routes: `GET/POST /api/colourways/<name>`, `PATCH` (rename) and
  `DELETE /api/colourways/<name>/<id>`.
- The list is not a preparation option, so naming, renaming or deleting changes no stitches and
  no plan fingerprint. The colourway in use is not stored: it is the one whose threads equal the
  design's current `merges` (and border thread while a border is sewn).
- `colourway-controls.js` (under the thread swatches): the menu, a name field, Save as new,
  Rename, Delete. Picking a colourway puts its threads into the options like a swatch change;
  stitches are then generated again. Same parts in the same order is a colour-only change, so
  the verified routing is reused (`thread_recolour.reuse`), and a colourway generated before is
  found again by `matching_plan`. Machine files are those of the colourway in use.
- Not kept per colourway: part outline colours (`area_outlines`) and the fabric colour.

## Fewer cuts between outlines (added 2026-10-25)

- `engine.colour_outlines` finds colour edges with eight neighbours. With four, a slanted or round
  edge was a chain of pixels touching only at corners; the line tracer broke it into pieces (a cut
  each) and lost the slanted stretches.
- `part_outlines.in_order`: outlines per part are sewn thread by thread (first-seen order), each
  thread nearest first, in both the colour generator and the piece path.
- With branching on (`generation_policy`, the default), plain running and triple lines keep their
  centre line on the block (`Block.line`, `Block.restitch`). `stitch_engine._begin_near` sews an
  element's lines nearest first and begins a ring at its point nearest the needle.
- `_branch` for two lines of one thread: a ring sewn after a cut begins where it comes nearest the
  next line (`_line_toward`); then `_Lines` (the thread's lines, a point every 0.5 mm, joined where
  they come within 0.35 mm) finds the shortest way, at most `LINE_BRANCH_MM` 12 mm, from the needle
  onto the next line: anywhere on a ring (chosen also near the line after it), else one of its ends
  (reversed if needed). The travel is sewn as 2 mm running stitches on lines sewn before or sewn
  over next, never across fabric, and the cut goes. Lines farther apart still cut.
- Measured (80 mm test designs, trims in the whole design):
  - Colour outlines, one thread (overlapping squares, a ring in a ring, a triangle, two circles):
    18 before, 12 after (outline thread 12 to 6, one per separate outline).
  - Same, outline colour Auto: 22 before, 13 after.
  - Outlines per part on all 7 parts, running or triple, one thread: 14 before, 12 after.
  - Colour outlines on ten 10 mm stripes (50 mm high): 14 before, 7 after.

## Satin here: satin / fill split by hand (added 2026-10-25)

- Piece command `split_satin` with a line (two points, mm on the hoop), drawn like the knife.
  `piece_layout.knife(..., satin=True)` cuts the piece along it, then picks the smallest side that
  `region_stitches.satin_reason` accepts (up to `TURNING_SATIN_MM` wide); when neither side can be
  satin it refuses and asks for a cut closer to the thin part.
- The satin side is grown by `engine.LIMB_OVERLAP_MM` (0.4 mm, scaled by the piece's transform)
  into the other side, so the two overlap and no gap opens at the cut, as in the automatic
  thin-limb split. The rest keeps its style (Tatami if the piece was Satin) and is stored first,
  so the fill is sewn before the satin, which lies on top. Both stay one thread: no colour change.
- Pieces panel: "Satin here" next to Knife, for one selected filled piece.

## Wide lettering columns (added 2026-10-25)

- Above a font's own satin range (`max_scale`, widest stroke about 4.2 mm) letters stay satin while
  the words' widest stroke is at most `small_lettering.SPLIT_SATIN_MAX_MM` (12 mm); only above that
  are they tatami fill (`small_lettering.satin_top`, `uses_fill`; `height_range` is unchanged).
  The limit is per text (`embroidery_fonts.text_metrics`), so a word of thin letters stays satin larger.
- These columns are sewn as split satin (`stitch_satin.split_rows`, 7 mm, staggered holes). With
  split on, every leg of the column, underlay included, is also divided at 6.85 mm (`split_long`):
  a 6.96 mm zigzag leg across an 11.6 mm stroke rounded to 7.01 mm on the machine grid.
- `embroidery_fonts.size_profile`: strokes from 8 mm wide get the double zigzag underlay.
- Fallback (`lettering_native.build`): font columns are traced at a fixed tolerance, so at several
  times the font's range some letters (Anton's O from about 25 mm) send stitches across a letter
  hole. When split-satin words fail any file check, they are generated again as tatami fill at
  the same stitched height (`small_lettering.generate(fill=True)`) and that is kept if it passes;
  the result has `wide_letters: 'fill'` and says so in its message.
- Fonts with `split_satin: False` (Alfa Slab One, Bowlby One: round letters trace badly larger,
  the stitches cross their counters) go to fill right above `max_scale` as before.
- Why 12 mm: wider split rows sew no better than fill and pull the letter in more, and pull
  compensation stays in mm (the release gate's envelope is the column plus its mm pull).

## Digitize for me: photos of one object, detail wishes (added 2026-10-25)

- `auto_digitize.classify`: with a plain background, the subject is judged alone (pixels more than
  40 away from the border colour). A colourful subject that is not flat colour (subject flatness
  under 0.9, over 20 % strongly coloured) is `object_photo`: the colour path, with
  2 x its colour families + 2 threads (at most 8). `hue_families` counts 30 degree hue bins
  holding 5 % of the strongly coloured pixels, neighbouring bins merged.
- Such a photo is cut out by shape (selection `grabcut` on the whole picture, edge -2), not by
  removing the background colour: a photo's edge blends into the background, and removing that
  colour left specks along the edge and in the highlights that blocked the stitches.
- Retries never go below one thread per colour family plus one (red and green are never merged
  into a brown). `parse_request` understands detail wishes ("all the details", "detailed",
  "keep it simple"): detail starts with one more colour and a 0.5 mm² floor, cuts alone are
  accepted, and retries first smooth edges and merge specks up to 2.5 mm², then drop one colour
  at a time down to that limit (two extra attempts). Photos and detail wishes under 150 mm get a
  size tip.
- `satin_font._dot`: a cut grazing a corner meets the shape at a single point; that no longer
  crashes satin areas.
- Known gap: the cut-out keeps a ring of background about 1 mm wide, sewn as a near-white thread.

## Align, space evenly, same size (added 2026-10-25)

- Piece commands `align` (`left`, `centre`, `right`, `top`, `middle`, `bottom`), `distribute`
  (`across`, `down`) and `match_size` (`width`, `height`, `both`), in `piece_arrange.py`. Each
  selected piece gets its own move or resize matrix on top of its saved one, as a position or
  width edit does, measured from its outline bounding box; stitches rebuild from the new outline.
- Align uses the edge or centre of the whole selection. Space evenly keeps the two outer pieces
  (by centre) where they are and moves the ones between so every gap is the same; it needs three.
- Same width / Same height scale each piece around its own centre to the first piece picked
  (the panel keeps the selection in click order), keeping its proportions; Same size gives every
  piece exactly that width and height. A straight line is refused when it has no width or height to match.
- Locked pieces refuse all three, like other edits. Pieces panel: a "Line up" row, enabled with
  two or more pieces selected (three for Space across / Space down).

## Mirror copy, circle layout and array (added 2026-10-25)

- Piece commands `mirror_copy` ('x' or 'y'), `circle` ({count, radius_mm, turn}) and `array`
  ({rows, columns, gap_mm}); the geometry is in `piece_patterns.py`, called from
  `piece_layout.change()`. Each copy is a Duplicate copy ({source, matrix, rotation, name}, plus a
  cut part's outline and the original's stitch type), so it moves, restyles and deletes on its own.
- The selection repeats as one group, measured by its outline bounding box. Mirror copy reflects
  across its right (x) or bottom (y) edge, so the copy touches it (half a drawing becomes whole).
  Circle: the selection stays at the top, `count` 2–36 includes it, the centre is `radius_mm`
  (1–500) below; with `turn` each copy rotates with the circle (a wreath) and its fill angle with it,
  without it the copies stay upright. Array: rows go down and columns right, one size plus `gap_mm`
  (0–100) apart, up to 20 × 20, the selection at the top left.
- Limits: the copies are counted before any is made against `MAX_COPIES` (100 per design) with a
  message naming how many are left; locked pieces refuse every repeat. Copies outside the hoop get the
  usual red audit and block generation until moved. The three commands rebuild stitches
  (preparation.py and `pieceEdit` lists); copies share their original's thread, so no colour change.
- Pieces panel: a Repeat group under Transform with Mirror copy ⇋ ⇅, Around / Radius mm / Turn /
  Circle and Rows / Columns / Gap mm / Array.

## Stitch edits: stops, cuts, single stitches (added 2026-10-25)

- `stitch_edits: [{kind: stop|trim|delete|move, x, y, n[, to]}]` (at most 200, in the order added),
  checked by `stitch_edits.choices`. x, y are the stitch's place in playback millimetres and n its
  place in the sewing order (the n-th sewn stitch); `to` is the new place of a moved stitch, at most
  3 mm away.
- `engine.py` applies them to the plan after the exact removal areas (`stitch_cuts`), in the order
  added, and they enter the cache key (and turn off colour-only reuse). Each edit is matched to the
  sewn stitch within 0.15 mm whose order is closest to n; if none is left (the design changed) it is
  left out and `playback.stitch_edits.dropped` says so in plain words. Piece layouts are matched in
  the shifted playback frame.
- Stop: a thread change to the same thread right after the stitch (after its cut, if any); the
  thread list repeats the thread and later puff threads move up one. PES reads it back as STOP, DST
  as a colour change. `playback.stitch_edits.stops` lists the thread numbers after each added stop;
  the worksheet notes "Machine stop you added" on that block and the colour strip in playback titles
  a same-thread block "Machine stop".
- Cut: a 0.6 mm tie-off along the run, TRIM, a jump back and a 0.6 mm tie-in on the next stitch (as
  `stitch_cuts` does). Refused where the thread is already cut or changes thread.
- Delete removes one stitch; move puts it (and the jump onto it, for a run's first stitch) at `to`.
  Both are refused with a plain message when a new stitch would be under 0.3 mm or over 7 mm, or
  would cross empty fabric (the release mask, `RemovedPixels`); a run's first stitch cannot be deleted.
  The written files still go through spacing and lock repair and the release gate like any other.
- Check stitches: `stitch-edits.js` under the playback controls: Add stop here, Add cut here, Delete
  this stitch, Move this stitch (then click the new place), at the last stitch playback has reached;
  a list of the edits (click to show it in playback, × to remove) and any left-out notes. Stitch
  edits move no piece, so the lock guard ignores them.

## Team names (added 2026-10-25)

- `team_names.py`: routes `/lettering/native/team/list` (check the list: one name per line, blank
  lines skipped, spaces collapsed, at most `MAX_NAMES` 50 names of `MAX_CHARS` 40 characters, and
  the file name each gets), `/team/name` (one name) and `/team/zip` (the files).
- Each name is `lettering_native.recipe()` of the Text page's settings with only `text` changed, built
  or reused by `lettering_native.make()`, the same cache, build and checks as Make stitches (`/check`
  now calls it too), under the same `BUSY` lock. The page asks for the names one after another, so it
  shows progress and only one name is built at a time.
- Every name keeps the one height chosen. A name wider than Max width is reported with its width and
  `fit_height_mm` (that height scaled by max width / width); the page offers the smallest of these as
  "Use … mm for all names". Nothing is resized automatically. A name the font cannot sew (missing
  letters, a height out of its range) or whose files fail a check is listed with the reason.
- The zip holds only names that passed, all with one identical recipe apart from the words, each bound
  to its own name (`recipe.text`); every file goes through `release_gate.converted_bytes` (the checked
  bytes for PES and DST, a re-checked readback for the other formats) as it is added. Any refusal
  blocks the whole zip with the name and reason. The format is the one chosen in Save and download.
- File names: accents dropped (NFKD), anything but letters, digits, `-` and `_` becomes `-`, Windows
  device names get `_`, an empty result is `name`, repeats get `-2`, `-3` (case-insensitive).
- `lettering_native.make()` renames a finished draft folder with a short retry: on Windows a virus
  scanner can briefly hold a file just written.

## Wave fill and offset fill (added 2026-10-26)

- Area style Wave (`fill_method="wave_fill"`, `stitch_fills.wave`): tatami rows that follow
  y + A·sin(2πx/λ) in the row frame, with A = `wave_amplitude_mm` (default 1.2, 0–5) and
  λ = `wave_length_mm` (default 10, 2–50). The wave uses the global grid, so neighbouring wave areas
  line up. Like Gradient, the area is bent so the wave becomes straight rows, filled as ordinary
  tatami (row turns, inside travel, holes), and every stitch is bent back after being cut into
  0.25 mm pieces; each run is then re-stitched along the curve (at most the max stitch length,
  within 0.05 mm of it). Rows sit the row spacing apart across the row direction, so they are up to
  about a fifth closer where the wave is steepest. Tatami underlay first (`fill_underlay`, on by
  default); rows along the area's long side, and the chosen stitch direction turns them.
- Area style Offset fill, the old Contour (`contour_fill`, `stitch_fills.contour`), already was a true
  offset fill: each ring is the area inset by one more row spacing, holes grow outward the same way
  and get their own rings, rings are sewn nearest-first and joined by inside steps (one run per
  connected area). New: open underlay rows along the long side first (`fill_underlay="true"` from
  the style; the engine default stays off), and the plain name and description in the style picker.
  The style id stays `contour`, so saved designs keep their choice.
- Style picker: Wave has its own sample (wavy rows); both are in `region_stitches.CATALOG`, so the
  area styles and Pieces panels list them.
- Tests: row geometry (inside the area, coverage, rows swing by twice the amplitude, holes kept
  empty, rings at row-spacing depths and around holes) and both styles through the release gate.

## Weld and smooth pieces (added 2026-10-26)

- `piece_weld.py`, piece commands `weld` (value `null`) and `smooth` (value `light` or `more`), routed
  from `piece_layout.change()`. Both rebuild stitches (preparation.py and `pieceEdit` lists).
- Weld: 2+ filled pieces, in the order picked, all of one thread (else refused: "different threads").
  Each piece must come within `TOUCH_MM` (0.2 mm) of the pieces joined so far, else "do not touch".
  The outlines (mm on the hoop, after each piece's transform) are united; a hair-thin gap between
  touching pieces is closed with a mitred grow-and-shrink of `TOUCH_MM`/2, and holes under
  `MIN_HOLE_MM2` (seam slivers) are dropped. Anything that still falls apart is refused.
- Smooth: Douglas–Peucker at max(0.15 mm, 1 pixel) for Light or max(0.35 mm, 1.5 pixels) for More
  removes pixel steps and wiggles; then corner cutting (1 or 2 passes) rounds bends gentler than
  `CORNER_DEG` (50°) while sharper corners stay exact; the result is scaled about its centre back to
  the original area. Holes are smoothed the same way. An outline that would move less than 0.03 mm
  is refused as "already smooth". Each selected piece is smoothed on its own.
- Storage is the knife's: a new part `{source, rings, matrix, rotation, name}` with the outline in
  the source piece's picture pixels before its transform, so it moves and resizes like any part. A
  picture piece or drawn shape that is replaced is marked `cut`; a copy or cut part is removed. The
  new part keeps the (first) piece's style, stitch direction, hole choice and outline. Locked pieces
  and stitched lines are refused; `MAX_COPIES` and `MAX_PART_POINTS` still apply through `edits()`.
- Pieces panel, next to Knife and Satin here: ⊕ Weld (2+ selected) and Smooth with a Light / More
  choice.

## Monogram ornaments (added 2026-10-26)

- Lettering setting `ornament`: `none` (default, left out of the recipe so saved lettering keeps
  its cache key), `crown`, `laurel`, `swirls` or `divider` (`monogram_ornaments.ORNAMENTS`); any
  other value is refused, and so is an ornament with 3D puff. Any words, classic or not, straight or
  curved, with or without a frame.
- `monogram_ornaments` draws them in code as satin columns: matched rails along a centre line with
  a width profile (`column`, sewn rung i to rung i, `satin_pairs="indexed"`), a point every 0.6 mm.
  Sizes follow the capital height; widths stay 0.8–3.5 mm (`MIN_WIDTH_MM`, `MAX_WIDTH_MM`).
  - Crown: five points on a band, each with a bead on top, above the words.
  - Laurel: two branches (stem, four leaf pairs, a top leaf) on an ellipse round the sides and
    bottom, drawn in as close as keeps the leaves clear of the letters and frame.
  - Swirls: one flourish each side, out from the words and curling up (curvature growing along it).
  - Divider: a pointed line under the words, widest in the middle.
- Placed round the letters' bounds, or the frame's when there is one, about a third of a capital
  clear; an ornament that would come within 0.5 mm of a letter or the frame, or whose rails would
  fold at a tight bend, is refused ("does not fit at this size" / "touches the letters"), and the
  Text page offers "No ornament".
- `embroidery_fonts.layout` sews it last (after the words and frame) in the thread colour, in its
  own `ornament` group: each piece's columns in order, the needle moved between them by travel
  inside the piece (as inside a letter), a cut after each piece. Columns are ordered so the travel
  runs where satin is sewn over it afterwards (crown points and laurel leaves before band and stem).
  A column with zigzag underlay ends back at its start (the satin returns), which the travel follows.
- Coverage and checks are unchanged: the ornament's satin columns enter the verifier's sewing
  envelope like letter columns, and the files go through the same release gate.
- Text page: "Ornament" select under Frame in "Monogram & frame"; the text helper can set it.
- Measured (Graduate, 14 mm words, classic JAM): every ornament passes all file checks with and
  without a circle frame, as do 5 mm and 40 mm words; stitches 0.40–3.8 mm (6.9 mm at 40 mm);
  one cut per ornament piece (two for laurel and swirls), none inside a piece.

## More motif patterns, backstitch and stemstitch stipple (added 2026-10-26)

- A choice under a style is stored with the style: `region_styles` values `motif:heart`, `motif:star`,
  `motif:scale`, `motif:circle`, `stipple:backstitch` and `stipple:stemstitch`
  (`region_stitches.VARIANTS`, first entry = default). The default is stored as the plain style
  (`motif`, `stipple`), and `motif:diamond` / `stipple:run` are refused, so saved designs keep their
  exact stitches. Copies, welds and cut parts carry the choice with the style.
  `split_style` splits it for `apply_style`.
- Motif (`motif_shapes`, our own simple shapes about 3.2 mm across on the 4 mm grid): diamonds as
  before (2 mm stitches); hearts (a 24-point heart curve), five-point stars, circles (16 points) and
  scales (half circles of 2 mm radius joined end to end along each row, every other row shifted half
  a repeat). Shapes are clipped to the area like the diamonds (holes kept empty, fragments under
  0.4 mm dropped, 400-cell and 1200-fragment limits). The new patterns are sewn with 1.2 mm stitches
  that keep their points (`running_stitch_tolerance_mm` 0.05); separate repeats are joined by
  inside travel (`travel_area`).
- Stipple (`stitch_fills.meander(stitch=...)`, attribute `stipple_stitch`): the same random
  meandering loop, sewn by `stitch_paths.backstitch` (1.2 mm forward, back over 45 %, so each back
  stitch is about 0.54 mm, above the 0.45 mm minimum) or `stitch_paths.stemstitch` (1.6 mm stitches
  across a 0.5 mm band, well inside the 1 mm between neighbouring lanes; a point that would land
  within 0.1 mm of the edge is pulled onto the area 0.1 mm inside it). Joins between loops stay
  plain inside travel.
- Style picker: under the chosen style a small select appears, "Pattern" for Motif and "Stitch"
  for Stipple (the region report carries `variants`); Stipple is now just "Stipple".
- Tests: patterns repeat inside the area with identical repeats and the hole empty, the saved
  diamond output is unchanged, backstitch and stemstitch turn back on themselves and stay inside,
  and every new choice through the release gate.

## Guides, grid and snap (added 2026-10-26)

- Preparation option `canvas_guides`: a list of up to 20 guides (`canvas_guides.MAX_GUIDES`),
  each `{axis, mm}`: axis `x` is a line down at X mm, `y` a line across at Y mm, measured from the
  hoop centre like piece positions (positive Y is down), within 500 mm, rounded to 0.1 mm. Anything
  else is refused (`canvas_guides.checked`), on the guides route and on `/artwork/<name>`.
- Guides are drawing aids and never reach the stitches. `preparation_key` and the saved-plan match
  (`saved_plans.equivalent`) leave them out, so a design with and without guides has the same
  prepared artwork name and the same machine files, and the stitch plan already made is kept. The
  lock guard ignores them and the design-review snapshot leaves them out.
- Saving: `POST /api/guides/<name>` `{guides}` writes only `canvas_guides` into the saved options
  (an empty list removes it) and returns the guides and the new piece revision. The studio calls it
  through `embroideryStudio.keepGuides`, which updates the options in the page without
  `apply`/`schedule`, so there is no new preview and the stitches stay current. While the studio is
  busy the save waits for the next preview.
- `static/canvas-guides.js`: "Guides and snap" in the Pieces panel: + Across / + Down, a position
  box per guide (mm or inches with the units setting), ✕ to remove. On the canvas a guide is dragged
  within 5 screen pixels of it; a new one is dragged in from the top or left edge (8 pixels); one
  dropped off the canvas is removed. Guides are thin magenta lines over the pieces.
- Snap (per browser, `needler.snap`) and Grid Off / 1 / 5 / 10 mm (`needler.grid`): with Snap on,
  drawn corners and points (not freehand) and drag-to-move lock within 6 screen pixels onto a guide,
  the hoop centre lines or the grid line nearest; a moved piece snaps by its left, centre or right
  and top, centre or bottom. `window.snapPoint` and `window.snapMove` are the hooks piece-panel.js
  uses. The grid is drawn faintly when its lines are at least 6 screen pixels apart.

## Text baselines: full circle, fixed length, custom line (added 2026-10-26)

- `embroidery_fonts.BASELINES` adds `circle` and `wave`; new lettering settings `circle_mm`
  (10–500, default 60), `wave_percent` (2–25, default 6) and `fit_length_mm` (5–1000), checked by
  `small_lettering.layout_options` and stored in the recipe only when used, so earlier saved
  lettering keeps its cache key. Letters stay rigid, placed and turned by one matrix each, as on arcs.
- Full circle (`_circle_matrices`): `circle_mm` is the size across inside the letters. The first
  line sits over the top, reading clockwise, letters standing outward; a second line (if any) runs
  along the bottom, reading left to right, letters standing inward, its baseline a capital further
  out so both lines share one ring. Three lines, words longer than 95% of their circle, and top and
  bottom words closer than a capital where they meet are refused. The height entered is the
  letters' height, as on one line (`small_lettering._measured`), not the two lines stacked.
- Wave (`_wave_matrices`), the custom line: one S-curve (up, down, back to the line) whose rise is
  `wave_percent` of the words' length and whose length along the curve is the words' length, so it
  looks the same for any words, as the Curve slider does for arcs. Chosen over a hand-drawn line
  because it reuses the arc placement (point plus tangent per letter) and needs no drawing tool on
  the Text page; a line drawn with control points is not there yet.
- Fixed length: one letter spacing between every two characters, worked out so the stitched line,
  satin edge included, is `fit_length_mm` long along its baseline (along the curve for arcs,
  circles and waves, so the width across differs). One line only; `letter_spacing_mm` is ignored.
  More than a capital's height between letters is refused with the longest length that reads as
  words; squeezing letters that are apart to within 0.3 mm, or pushing joined script letters into
  each other (overlap half as much again), is refused with the shortest workable length
  (`LengthError.nearest`, found by halving), offered by the advice check as a one-click fix.
- Bends: on a circle or wave, the same neighbour test (`_neighbour_gaps`, `_crowded`) compares
  every pair of letters with the straight line; letters that would touch on the inside of a tight
  bend are refused ("Make the circle larger" / "Choose a gentler wave"); advice offers a 40%
  larger circle or a gentler wave.
- Max width and the advice width use the laid-out letters (`laid_out_width`), so they follow the
  real circle and wave; the build's own width check is unchanged.
- Text page: Circle and Wave shape buttons; Circle size (mm), Wave slider (%) and Fixed length (mm,
  empty is off) under Shape; the instant preview draws the circle, the wave and the spacing. The
  text helper can set `circle`, `wave`, `circle_mm`, `wave_percent` and `fixed_length_mm`.
- Measured (Graduate, 8 mm): CHAMPIONS fixed at 80 mm stitches 80.0 mm wide and passes all file
  checks; TEAM SPIRIT / SINCE 1999 round a 70 mm circle is 73.2 x 85.8 mm and passes; CHAMPIONS on
  a 6% wave at 90 mm along the curve passes. Limits found: 10 mm Graduate CHAMPIONS takes up to a
  6% wave and a 30 mm circle; short words take only gentle waves (Waves at 8 mm: 3%), and joined
  script fonts less (Pacifico Riverside Bakery: 7%).

## Motif run (added 2026-10-27)
- `stitch_paths.motif_run`: a running line with a small motif every `outline_spacing_mm` (default
  2 mm) of line, spread evenly (a closed ring has no motif on its seam). `outline_motif`:
  `diamond` (centred on the line, `outline_width_mm` across; its lower side is sewn twice so the
  line carries on from the far point), `triangle` or `scallop` (standing `outline_width_mm` high
  on one side). On a closed ring one-sided motifs stand outside the shape, off its fill.
- Motifs are at least 1.5 mm along the line and stand square on the chord from their start to
  their end, so the small corners of a traced outline do not tilt them. Scallops get about 1 mm
  stitches with one at the top; the flattest, at the top, stays 0.5 mm or longer. Lines shorter than one
  motif plus a gap are plain running stitch. Stitches are split at 2 mm.
- Subject border: style Motif run (`border_style: motif`, `border_motif`), Motif menu shown only for
  it; the release band is twice the width, as for blanket.
- Measured on a 60 mm line, widths 0.5 to 6 mm, all three motifs: shortest stitch 0.52 mm, longest
  1.88 mm. Borders with each motif pass the file checks.

## Couching (added 2026-10-27)
- `stitch_paths.couching`: the look of a thick cord tied down. First a triple-stitch cord along the
  line (`running_stitch_length_mm`, 3 mm on borders), then a pass back along it with a tie
  `outline_width_mm` across the cord every `outline_spacing_mm` (default 3 mm). Between ties the
  needle travels along the cord, hidden under it; the line ends where it began.
- Ties are at least 1 mm across so each half stays above the 0.45 mm minimum stitch.
- Subject border: style Couching (`border_style: couching`); Width is the tie length.

## Hand-look runs (added 2026-10-27)
- `stitch_paths.blackwork_run`: out along the line and back through the same holes; every stitch
  is sewn twice and the line ends where it began. Border style Blackwork run, 2 mm stitches.
- `stitch_paths.hand_stitch`: dashes about `running_stitch_length_mm` long (3 mm on borders), each
  sewn three times, joined by single 1 mm links. Dash lengths vary by up to 12 % in a fixed
  pattern, so the same line always sews the same. Border style Hand stitch.
- `stitch_paths.candlewick`: a running line with a raised knot every `outline_spacing_mm`
  (default 3 mm), spread evenly; each knot is twelve spokes out from one hole and back,
  `outline_width_mm` across (0.6 mm spokes at least, 2.5 mm knots at most). Border style
  Candlewicking; Width is the knot size.
- Black lines only, Line weight Redwork (`ink_bean_repeats: 2`): `ink_lines.redwork_routes` sews
  every traced line exactly twice, once each way, as one closed route per connected drawing, so a
  drawing has no cuts inside it. Line ends within 3 px meet; a line end beside the middle of another
  line splits that line there. Routes are not simplified, so both passes share their holes.
- Measured: a 1200 px drawing of 400 crossing strokes, 2,265 traced lines, became 136 routes in
  3.7 s. All three borders and a Redwork drawing pass the file checks.

## Hand-look open fills (added 2026-10-27)
- Area styles `blackwork_fill`, `candlewick_fill` and `lacework` (`region_stitches.open_fill_shapes`),
  sewn like Motif and Cross stitch: running-stitch pieces clipped to the area, joined by travel
  inside it (`travel_area`).
- Blackwork: lines across and down every 4 mm through the cell centres, plus both diagonals through
  the cell edges' middles, so every cell holds a diamond. Long lines, so few pieces (a 32 mm disc: 38).
- Lacework: a honeycomb net with 2 mm sides, drawn as rows of half cells that share their flat
  sides with the next row (shared sides are sewn twice); 1.5 mm stitches.
- Candlewicking: knots 4 mm apart on rows shifted half a step each row; each knot is twelve 0.7 mm
  spokes out from one hole and back. Only whole knots inside the area are kept, and routes are not
  simplified so every spoke stays.
- Measured on the 60 mm test design: Blackwork 1,327 stitches, Candlewicking 3,050, Lacework 1,559,
  one cut each (Cross stitch: 979). All pass the file checks.

## Pattern run and sculpture run borders (added 2026-10-27)
- Border style `pattern` (`stitch_paths.pattern_run`, option `border_pattern` → `outline_pattern`):
  a pattern repeated end to end along the line, with no plain stitches between repeats. Wave (one
  sine period per 1.6 × width), Loops (a trochoid that closes a loop every 0.8 × width) and Key
  (square hooks on a 6 × 4 grid, 1.5 × width long). Repeats are stretched so a whole number fills
  the line, and each stands square on its chord like motif-run motifs. Curves are sewn in stitches
  of about 0.8 mm spaced along the curve (a multiple of four per wave, so crests get a hole).
  Width is held at 2 mm or more; below that the hooks and loops close up into short stitches.
- Border style `sculpture` (`stitch_paths.sculpture_run`): 2.5 mm stitches, each starting halfway
  back along the one before (two forward, one back), so the line is sewn three times by
  overlapping stitches and reads as a thick twisted cord. Lines under 3 half steps fall back to a
  triple line.
- Stitches stay 0.45–2 mm on lines and rings; both borders pass the file checks.

## Maze and star fills (added 2026-10-27)
- Area style `maze` (`fill_method="maze_fill"`, `stitch_fills.maze`): the stipple spanning-tree
  trace with `straight=.7` (the tree keeps its direction 70 % of the time, so corridors run long)
  and no rounding, so it reads as a labyrinth. Lanes 1 mm apart, 1.5 mm stitches, square corners
  kept (tolerance 0.05 mm). One line per connected area; no underlay.
- Area style `star` (`fill_method="star_fill"`, `stitch_fills.star`): one line spiralling out from
  the area's visual centre as a five-point star with a point straight up. Turns are 1.6 mm apart
  at the points and 0.8 mm at the inner corners (`STAR_INNER`). Clipped to the area; pieces joined
  by travel inside it, like Ripple. Straight sides split into 2 mm stitches, corners kept.
- Measured on a 30 mm disc: maze 490 stitches, star 947, one run each. Both pass the file checks.

## Florentine fill (added 2026-10-27)
- Area style `florentine` (`fill_method="florentine_fill"`, `stitch_fills.florentine`): tatami rows
  that copy the area's top edge in the row frame (rows along the long side, as Wave). The edge is
  sampled every 0.5 mm, averaged over 4 mm, scaled down until 95 % of it is no steeper than 0.7
  (`FLORENTINE_SLOPE`), then the steep ends left over are clamped, so a round top stays a smooth
  dome and lower rows keep their spacing. Areas under 2 mm across fall back to tatami.
- Wave and Florentine share `_bent_fill`: the area is bent so the curve becomes straight rows,
  filled as tatami with underlay and inside travel, and the stitches bent back.
- Passes the file checks on the standard test design.

## Elastic and sculptured fills (added 2026-10-27)
- Area style `elastic` (pattern choice as Motif: diamonds, hearts, stars, scales, circles;
  `region_stitches.elastic_parts`): the area's top and bottom edges in the row frame (rows along
  the long side) are sampled every 0.25 mm and averaged over 2 mm (`stitch_fills.stretch_map`).
  Motif repeats are laid on a flat strip of whole 4 mm rows, as many as fit the area's median
  height, and each point is placed the same share of the way from top edge to bottom edge, so
  repeats grow, shrink and bend with the shape. Repeats squeezed under 1.5 mm high are left out;
  the rest are clipped to the area and sewn as running stitch (1.2 mm, tolerance 0.05) with
  inside travel, like Motif.
- Area style `sculptured` (`fill_method="sculptured_fill"`, `stitch_fills.sculptured`): tatami
  whose rows have two needle holes per 4 mm repeat, one on each diagonal (`_row_points` takes a
  tuple of offsets per row), so the holes outline a diamond lattice. Holes closer than the
  minimum stitch are sewn as one; stitches stay at most 4 mm. Row spacing is rounded so a whole
  number of rows makes one repeat, with underlay.
- Both pass the file checks on the standard test design.

## Feathered fill (added 2026-10-27)
- Area style `feather` with choices One edge / Both edges / Textured edge (`fill_method="feathered_fill"`,
  `feather_edge` = `end` / `both` / `texture`, `stitch_fills.feathered`). Tatami rows run across the
  area (long-side angle + 90°) so their ends make the long edge.
- `tatami(..., ragged=(sides, depth))` pulls row ends in per sewn section (`_rag`): the two rows that
  meet at a turn are pulled in by the same amount, so each turn becomes one tip; a single row pulled
  alone is hidden by the turn stitch to its longer neighbour. Amount = depth × random², at most 40 %
  of the shorter row, seeded by row index (same area, same stitches). Depths 4 / 3 / 0.8 mm
  (`FEATHER_DEPTH_MM`). Underlay is kept depth + 0.3 mm inside the edge so it never shows between tips.
- Passes the file checks on the standard test design.

## Globe and hand stitch fills (added 2026-10-27)
- Area style `globe` (`fill_method="globe_fill"`, `stitch_fills.globe`): the area is stretched out
  from its centre in the row frame (`atanh`, per axis, over its bounding box) and filled as tatami
  with underlay; mapped back (`tanh`), row spacing and stitch length shrink by 1 − 0.35·t² at relative
  distance t (`GLOBE_SQUEEZE`). Rows open by 1/(1 − 0.35/2) so the thread used stays close to tatami:
  0.48 mm apart in the middle, 0.33 at the rim for 0.4 mm tatami. The minimum stitch asked of the
  stretched area is raised by 1/(1 − squeeze). Areas under 4 mm across fall back to tatami.
- Area style `hand` (`fill_method="hand_fill"`, `stitch_fills.hand`): open tatami rows 0.9 mm apart,
  no underlay, two needle holes per 5 mm repeat at seeded random places (`random.Random(7)`, 9 row
  patterns), so stitches run 0.75–4.25 mm and look hand sewn but repeat exactly.
- Both pass the file checks on the standard test design.

## Custom fabric settings (added 2026-10-27)
- `custom_fabrics.py`: a custom fabric is a listed fabric (`base`) with the user's own
  `row_spacing_mm` 0.25–1, `satin_spacing_mm` 0.25–0.8, `satin_pull_mm` 0–0.6,
  `max_stitch_length_mm` 2–7 and `fill_underlay`; up to 30 are kept in `work/fabrics.json`
  (`GET/POST /api/fabrics`, `DELETE /api/fabrics/<id>`; POST with a saved id replaces it).
- The chosen one is copied into the design settings as `fabric_custom` (with `fabric_preset` = its
  base), so a design sews the same after the saved fabric is changed or deleted.
  `generation_policy.preset_for` checks it and returns the base row with the custom values and name;
  the engine, `apply`, lettering (`fabric_pull_extra`) and the worksheet (name, base backing) read that.
- Choosing a listed fabric, or Claude/auto-digitize picking one, drops `fabric_custom`.

## Multi-hooping (added 2026-10-27)
- `multi_hooping.py` splits the checked PES pattern (never the plan) for a hoop field: a grid of
  parts each at most field − 2 × 5 mm (`EDGE_MM`), at most 12 hoopings. Each seam slides within the
  room the hoop allows, on a 0.5 mm grid, to where the fewest stitch segments cross it.
- A stitch crossing a seam is cut on it. When the same run comes back to the seam within 3 mm
  (`JOIN_MM`, fill rows turning) the part sews along the seam instead of cutting, unless that stitch
  crosses a removed area. Other cut ends get a 0.6 mm back-and-forth tie-off; stitches under 0.31 mm
  are merged; pieces under 1 mm are left out.
- Neighbours share two running-stitch crosses (3 mm arms) at ¼ and ¾ of their seam, in their own
  colour (#e5007e, "Alignment marks"): last in the earlier hooping, first in the later one.
- Each hooping is written centred on its hoop under `<design>/hoopings/<w>x<h>/hooping-<n>/` with
  its own release context: the design mask padded by (arm + edge)/scale pixels plus a square around
  each cross, origin moved by the hooping centre and the padding. Downloads go through the same
  `release_gate.download`, so every format is checked again. `plan.json` caches the split by source
  digest and `VERSION`.
- Routes: `GET /api/hoopings/<name>/<w>x<h>` (summary, `[]` when the stitches fit) and
  `GET /hooping/<name>/<w>x<h>/<n>/<format>`. The studio (`multi-hooping.js`) asks only for current
  stitches (visible export link) when the hoop fit note is red.

## Digitizer's handbook for Claude (added 2026-10-28)
- `knowledge/handbook.json` (loaded by `knowledge_store` like the other tables): one row per mode, area
  style (with its choices), border, `make_stitches` setting (`control`) and sewing concept, with
  `does` / `use` / `avoid` / `limits`. `auto_claude.handbook()` renders it as text and adds the fabric
  presets from `generation.json`, so a fabric change reaches Claude by itself.
- `auto_claude.run` sends it as a second system block with `cache_control`, so it is cached with the
  instructions across attempts and runs (about 5,200 tokens).
- `tests/test_claude_tools.py` fails when a mode, area style, choice, border or setting has no row.

## Style and direction per thread colour (added 2026-10-28)
- Options `colour_styles` (`{'#rrggbb': area style}`) and `colour_angles` (`{'#rrggbb': degrees}`),
  checked by `region_stitches.colour_choices`. The engine applies them to every area of that thread;
  the colour is matched exactly, else to the nearest thread within 36 (sum of RGB differences), as
  colour merges are, because the palette shifts slightly between runs.
- An area's own style or direction (`region_styles`, `area_angles`) wins. Parts the colour's style
  does not suit keep the automatic choice (`colour_style_fits`): satin only where satin forms, 3D
  satin only on straight bands, puff only as wide as the foam allows, every other style only on parts
  wider than `SMALL_SATIN_MM`; hairlines stay runs. Fills chosen this way still overlap the colours
  sewn after them, so no fabric shows between colours.
- Claude sets them with `make_stitches.colour_styles` (style enum from `catalog()['area_styles']`),
  and the border's `placement` and `line_inside` (`border_placement`, `border_inner`).

## Holes per thread colour; Claude's order, density and outlines (added 2026-10-28)
- Option `colour_holes` (`{'#rrggbb': 'all' or mm²}`), checked by `region_stitches.colour_hole_choices`:
  every area of that thread sews over all its holes, or only those up to the size; larger holes stay
  open. The colour is matched as `colour_styles` are. An area's own hole choice (`area_holes`) wins.
- Claude sets it with `make_stitches.colour_holes`, and the existing design-wide `sew_order`
  (colours / layers), `density` (lighter / normal / denser) and `outlines` + `outline_colour`
  (a thread or `auto`) with `make_stitches.sew_order`, `density` and `outlines`. Appliqué stays an
  area style in `colour_styles`.

## Feedback per colour; Claude's plan and the person's request (added 2026-10-28)
- The engine's playback payload has `areas`: one row per sewn area with its `thread`, `mm2`, widest part
  (`width_mm`) and the `style` it became (`running line`, `satin`, `tatami`, `tatami with satin tips`
  or the chosen style). When a colour's style was refused, the row also has `asked` and `refused`
  (the reason, from `region_stitches.colour_style_refusal`).
- `auto_claude.per_colour` sums them per thread for Claude after every attempt: areas, total and
  largest mm², widest part, styles used, and up to three `style_refused` reasons.
- The instructions put the person's request before every rule. `make_stitches.plan` (one line per
  colour: what it is, style, why) is logged as `Plan:` steps and carried on each attempt; `finish`
  adds `request` (how it was followed) and `tools_used`, shown in the Digitize-for-me result.

## Scripted Claude tests; border with a removed background (added 2026-10-28)
- `tests/test_auto_digitize.py` `_ScriptedClaude` plays a script of tool calls through the real job
  runner and engine: every new control in one run (plan, satin border with line inside, style and
  direction per colour, holes, outlines in auto colour, lighter density, layer order), a refused
  style and its reason, running out of attempts, a finish naming a missing attempt, a refusal and
  the spend cap (both fall back to the rules without calling Claude again).
- Colour removal (`colour_knockouts`) now treats the border's band as kept area in
  `knockout_routing.protect` / `verify`: a border on the design's edge used to fail with
  "Cannot secure a thread beside a removed area" whenever the background was left out.

## Appliqué pieces together (added 2026-10-28)
- `applique_layout.finish` runs after every colour pass has made its parts (`engine.py`), on all
  parts styled `applique`, with three design options (`applique_partial`, `applique_combine`,
  `applique_join`; on or off, anything else is refused).
- Partial: a piece grows up to 1.5 mm under the parts sewn after it, staying 0.8 mm inside their far
  edge (thin parts on top get no growth). That edge is written to the node as `applique_bare`
  (closed pixel paths); `stitch_engine._applique` gives it no satin cover. Hidden stretches under
  about 2.5 mm are covered anyway, and covers run 1 mm on under the part on top (`TUCK_MM`).
  Placement and tack-down still go all round. The cutting file has the grown shape.
- Join: an edge next to a later appliqué piece is bare too, so the later piece's cover alone sews
  the join; in partial mode a piece does not grow under a later appliqué piece.
- Combine: the pieces of one colour pass become one node, so placement for all, one stop,
  tack-down for all, one stop, covers for all. Pieces of one colour never touch.
- Release check: `applique_coverage(..., bare=)` uses the same geometry as the stitches.
- Colour mode only; the piece layout path keeps one piece per node. Claude sets them with
  `make_stitches.applique` (handbook row `concept:applique_pieces`).

## Basting and buttonholes (added 2026-10-28)
- `basting_buttonholes.apply` edits the engine plan after the stitch edits (`engine.py`), in
  playback millimetres like them. `basting`: `design` (box 5 mm outside every stitch, buttonholes
  included) or `hoop` (3 mm inside `piece_hoop_mm`, centred on the design); 5 mm stitches, no
  tie-offs, sewn first in its own thread `#ff8c1a` with a colour change after it. Puff thread
  indexes in the plan's extras move up by one.
- `buttonholes` (up to 40: x, y, length 8–40 mm, width 3–6 mm, angle, colour): tie-in, a run
  along both leg centres, satin up one leg, a bar tack across both legs, satin down the other,
  a closing bar tack, tie-off; 0.6 mm slit left between the legs. Sewn last, a cut before each,
  a colour change only when the thread differs from the one before.
- Both may reach outside the picture. `band` returns the pixels they sew on a canvas grown by
  `pad` pixels each side; the engine pads the release mask (and the knockout mask) by `pad`
  and moves the recorded origin by `pad*scale`, so every later check uses the larger canvas.
  A canvas over 16 million pixels is refused with a message. Thread recolour reuse is off
  when either is used; the cache key includes them.

## Lettering envelopes (added 2026-10-28)

- `embroidery_fonts.layout(..., envelope, envelope_percent)`; `ENVELOPES` = none, arch_top,
  arch_bottom, bulge, pinch, bend_up, grow, shrink. Straight baseline only (any number of lines);
  refused with arch, smile, circle, wave or a classic monogram. Strength 10–50%.
- `_envelope_warp`: measured on the straight words' outline bounds; each point keeps its x and
  moves between the shape's new top and bottom edges (sine bump or linear ramp), so letters
  stretch rather than move rigidly. Applied after placement, before the half-em move onto the page.
- `_bend_rails`: satin rails get points at most 0.6 mm apart first (matched pairs stay matched),
  then bend. Stroke width for underlay, walk and the puff range is measured on the bent rails.
  Fill letters, travel areas, frame and ornament bounds all use the bent outlines.
- Recipe keys `envelope`, `envelope_percent` (left out when none, so old cache keys hold).
  Text page: Envelope select + Strength slider in the Shape box (hidden off a straight line).
  Claude's text tools take `envelope` / `envelope_percent`.

## Eleven more fonts (added 2026-10-28)

- Bangers, Damion, Fjalla One, Francois One, Grand Hotel, Leckerli One, Lilita One, Patua One,
  Paytone One, Sniglet, Titan One (SIL OFL, github.com/google/fonts `ofl/`, licence beside each
  file). 30 fonts in all.
- Size range from stroke widths as before (thinnest 10% of strokes at least 0.34 mm, widest at most
  4.2 mm, 6 mm for puff). Then a sweep built every character, eight at a time, at the smallest,
  middle and largest satin height. Where it failed, the range was narrowed: Bangers 1.1–2.9,
  Leckerli One 1.1–2.4 (no `~`), Patua One to 2.4, Paytone One to 2.1, Titan One to 2.1; those
  five are fill above their range (`split_satin=False`).
- Tried and left out because ordinary letters failed checks at normal sizes: Black Ops One,
  Carter One, Changa One, Cookie, Courgette (its Z fails at scattered sizes), Lobster Two Bold,
  Norican, Squada One.

## Morphing, auto trace and magic wand (added 2026-10-29)

- Piece commands `morph` (`{kind, strength}`; pinch, punch, twirl, wave; 10–100%) and `auto_trace`
  (value `null`) on the selected pieces; both regenerate stitches like `smooth`; morph stores the new
  outline through `piece_weld.replace`, auto trace in place (see session 21), so style, direction,
  holes and part outline stay.
- `piece_morph`: edges get points at most 0.5 mm apart (finer on small selections), then every
  point moves around the selection's box centre. Pinch / punch raise the distance to the centre,
  as a share of the farthest point, to the power 1+1.5s or 1/(1+1.5s); twirl turns up to 180° at
  the centre, fading to nothing at 1.25× the farthest point; wave moves points up and down by up
  to 20% of the height, two waves across. Each map is one-to-one, so holes stay holes. A morph that
  moves the outline less than `ALREADY_MM` (a circle twirled) is refused.
- `piece_trace.traced`: each ring is resampled every half pixel; corners are bends over 50° seen
  1.5 and 3 pixels each side (pixel steps fail the second), the stretches between them are smoothed
  (Gaussian, about 1.2 px, at least 0.15 mm) and eased back to the corners; holes under 1 mm² are
  closed; the result is scaled back to the traced area. Pieces already clean are skipped; all clean
  is refused.
- `magic_wand` (`{point, tolerance}`, no ids): reads the artwork (`load_image`, before colour
  reduction; same pixel grid as the prepared image), compares Lab colours with the median around the
  click, keeps the 4-connected region, drops 1 px hairs, keeps its holes, traces it, and adds a drawn
  piece `Wand N` in the design's nearest thread (Lab), or the region's own colour when there is none.
  A region over 90% of the picture is refused.
- Pieces panel: Morph select, Strength % and Morph next to Smooth; a Trace box with the Magic wand,
  Tolerance, and Auto trace for Selected pieces, All threads or one thread (locked and hidden
  pieces are left out). Not a Claude tool: like weld and smooth, these edit pieces by hand.

## Multi-colour and open photo stitch (added 2026-10-29)

- `photo_lines.generate` takes `photo_style` `one_colour` or `multi_colour`, `photo_colours` (2–6,
  default 4) and `photo_open`. `engine.digitize` sends both styles there.
- `threads`: k-means in Lab (seeded, at most 20,000 samples) on the original upload inside the
  subject; colours ordered nearest the fabric first (white, or near black with light thread).
  Each pixel's share: its two nearest colours, split by where it falls on the line between them,
  so shares sum to 1. Open adds the fabric colour as an unsewn entry and keeps threads off it.
- Each thread: its share is blurred, sewn only where it is over 15%, as `rows` with its share as the
  darkness, at `photo_angle + i·180/n`. Rows join inside that thread's own area; otherwise tie-off,
  cut, jump. Lightest thread first; one colour change per thread.
- Open: one colour leaves tone under 0.18 unsewn; both modes cap the zigzag at 60% of the row.
- Same checks as one colour: the 0.1 mm grid tidy, PES/DST readback, every stitch 0.3–7 mm, the
  release context from the subject mask. Claude: mode `photo_colour`, `photo.colours`, `photo.open`.

## Recognize stitches (added 2026-10-29)

- `stitch_recognize.read`: `machine_files.read_pattern` (our DST cut convention), colour blocks from
  pyembroidery, split at cuts, colour changes, stops and jumps of 2 mm or more (shorter jumps are
  sewn through). Blocks of two points or fewer are dropped.
- `pieces`: each block drawn 0.4 mm wide on a 0.1 mm grid, gaps to 1 mm closed. Narrower than
  1.2 mm: a line (path with back-and-forth folded, simplified 0.1 mm; triple when the thread
  covers the path more than 2.2 times, so tie-offs do not count). Else opened by 0.8 mm (travel runs go), each outer contour with its holes
  (1 mm² or more) is a part: satin when half the holes turn back more than 150° and
  `satin_reason` allows it, else tatami with the length-weighted axial mean stitch direction.
  Over 100 parts is refused.
- `open_file`: the silhouette (grey, 700 px on the long side, 2 mm margin) is the new design's
  picture; its own pieces are cut (not listed, not sewn); every part is a drawn piece (rings in
  picture pixels) with `region_styles`, `area_angles` and `sew_sequence` in file order. The
  upload route takes machine files; the designs page has Open machine file. The machine file
  itself is not kept.
- Since session 21 a block holding several objects sewn without a cut is split into them (below).

## Thread charts, node reshaping, bottom join, batch convert (added 2026-10-29)

- Thread charts: `thread_matching.CHARTS` adds Pfaff PCM, the 16-colour palette pyembroidery keeps
  inside `PcmReader` (read by feeding the reader a file that uses every colour once; no colour
  values are copied). Six charts is every machine palette pyembroidery has; it has no thread-maker
  catalogues. `/lettering/native/thread?chart=` limits the Text page's thread names to one chart
  (the menu is remembered on the computer); `worksheet.summary(..., chart)` and `?chart=` on both
  worksheet pages name every thread from the picked chart, otherwise the closest chart overall.
- Node reshaping: piece command `reshape`, value = the piece's rings in mm on the hoop (same rings,
  in order; points moved, added or deleted). Stored in the piece's own picture pixels, before its
  matrix, as `rings` on its piece edit, so the id, name, style and transform stay; a picture piece
  may now carry `rings` too (copies made earlier keep the old outline). Refused: fewer than 3 points
  (2 for a line), a crossing outline, a hole outside the piece, under 1 mm², over 5000 points.
  Stitches rebuild after it. Pieces panel ◇ Points: handles on every point, 8 screen px reach.
- Bottom join: `embroidery_fonts.layout(..., join='bottom')`. `_bottom_entry` runs from the sewn
  area nearest the letter's foot (its left edge on its own baseline, turned and bent with it) to
  the first stroke's start, 0.15 mm inside the sewn columns, sewn first so the strokes cover it;
  skipped under 1 mm. Touching letters still join inside both, now ending at that entry. Satin
  letters only (puff and fill letters unchanged). Letters with fabric between them keep their
  cut: a thread along the baseline over bare fabric fails the release gate, which is unchanged.
  The letter's exit is not moved: a run to its bottom-right would lie on top of its satin.
  Recipe key `join` (left out when closest); Claude's text tools take `join`.
- Batch convert: `DesignLibrary.converted(ids, fmt)` finds each design's stitch folder
  (`saved_plans.matching_folder`, the folder `matching_plan` reads) and converts it with
  `converted_bytes`, the single download's gate. `POST /api/library/convert` returns a zip
  (`designs-<fmt>.zip`, team-names file naming), with `not-included.txt` for designs without stitches
  or failing a check; none converted is a 422 naming why. Up to 100 designs; trashed ones refused.

## Session 19 bugs: cut-out slivers, netted petals, leaves, white parts, Start, approval (added 2026-10-29)

- Cut-out subject failing the file check after a colour merge (a real AI run on a rose): the merge was
  not the cause. A sliver thinner than one fill row on the subject's edge (a one-pixel line of darker
  red along a petal) was tacked 0.5 mm always to the right, and a lock on a path shorter than the lock
  ran on past its end; next to the removed background both left the subject. `stitch_fills._tiny` now
  tacks along the part's own centre line, centred on it (its pass along a thin part no longer runs a
  quarter of its length past one end); `stitch_engine._with_locks` retraces any path a whole stitch
  (0.3 mm) long; `assemble` skips a block shorter than one stitch. The release gate is unchanged.
- Gaps between colours: a petal netted by darker shading is thin everywhere, so it was sewn as satin,
  and satin columns cannot follow a net (wedges and tips stayed bare). `engine.satin_gaps`: an area at
  least 2 mm wide and 30 mm² whose columns (`satin_font.area_columns`) cover under 90% of it is filled
  instead, with the usual overlap under later colours. On the rose: bare subject 2.7% to 1.5%.
- Flat leaves: `fill_shaping.leaf_halves` splits a leaf-shaped fill (principal axes at least 1.4:1,
  12% in from its tip under 0.6 of its widest, the other end under 0.8; at least 20 mm²) along its
  midrib; each side is its own fill node (same thread and settings), rows turned 40° from the midrib
  the opposite way, each reaching 0.35 mm under the other. Not for chosen styles or angles, limbs or
  colour removal. Ellipses, rectangles and circles are not leaves.
- White parts: `colour_knockout.remove_colour` marks an enclosed part `inside` when a ring around it
  (half its size wide, at least 1.5 mm) lies in the subject; a letter's counter is not. Digitize for me
  (`AutoDigitizer._keep_inside`) puts those parts in `restore_parts`. In `prepare`, a colour whose parts
  are kept is locked as one more colour (up to 8), so it never merges into a pale neighbour; it is not
  shown as a Preserve colour tick, and merging it stays allowed.
- Start over an earlier result (`auto-digitize.js`): Start clears the old result at once, waits for the
  page's own preparation instead of refusing, frees itself whenever the job is no longer running (also
  when a result cannot be shown), and stays disabled during a run although the studio re-enables
  inspector buttons after its previews. Tested in Node with a small stand-in page.
- A new thread colour from a swatch keeps "I approve" (`schedule(true)`); picking another swatch's exact
  colour or dropping one swatch on another is a merge and clears it, as every other change does.

## Session 20 bugs: cleanup choice, upload, script satin gaps, freezing (added 2026-10-29)

- Cleanup changes: one choice, `cleanup_choice` (`cleanup_review.cleanup_choice`), instead of a
  Keep it / Let it go pair per speck. `auto` (default) lets changes under `AUTO_DROP_MM` (0.8 mm,
  two thread widths) go and keeps larger ones as drawn; `keep` and `drop` cover every change;
  `review` (not offered in the studio) still asks about each one and blocks saving until decided.
  Per-detail `cleanup_decisions` still decide their own detail; a design saved with them and no
  choice maps to the nearest one (all keep, all drop, otherwise automatic). The report carries
  `cleanup_choice`; Detail & mask checks shows one Small cleanup changes menu.
- Upload: the subject model is warmed in a background thread, not inside `/upload` (a slow
  first load or a busy model kept the page on "Opening image editor…"). With
  `Accept: application/json` the route answers `{url}` or `{error}` (400), an unreadable picture
  included; the Library posts with fetch, a 2-minute limit and Try again, clears the file input
  so the same file can be picked again, and resets itself when Back restores the page.
- Script satin gaps: `satin_font._gap_columns` adds columns for parts of a glyph no column
  reaches (junction cuts, sharp-turn splits and trimmed twisted ends left a P's stem, an r's top,
  a u's foot unsewn), when wider than 0.3 of the typical stroke. Each gap is traced as its own
  shape (`area_columns(..., gaps=False)`), or along its long axis when compact, grown a little
  into its neighbours and cleaned against the outline. Gap columns are marked `closed=None`
  and count as the typical stroke width (size range, puff, underlay); layout leaves out those
  shorter than `GAP_MIN_MM` (1.5 mm) at the chosen size, where the thread hides the gap and the
  column is too short for needle points of its own. Pacifico at a 30 mm capital: the largest bare
  core in a letter went from 36 mm² to 3 mm² (most letters under 1 mm²). Area satin
  (`area_columns`) is unchanged unless called with `gaps=True`.
- Freezing: `ui-language.js` relabelled the whole page on every DOM change (playback updates its
  counter many times a second); it now relabels only added nodes, changed text and changed labels.
  The designs page keeps its cards between renders (search no longer rebuilds every card and
  fetches every picture again), previews are fetched by design revision and cached by the browser
  for a day (`no-store` without it or with `rebuild`), and JPEG originals decode reduced
  (`draft`) for the 600 px preview. Confirming the freeze is gone needs a browser.

## Gaps from sessions 16–18 (added 2026-10-29)

- Magic wand: `piece_trace.knock_out` cuts the new wand shape out of every visible, unlocked filled
  piece it covers (at least `COVERED_MM2`). What is left keeps its id, stored in place as the piece's
  own `rings` (picture pixels, before its matrix, as reshape stores them); further parts become cut
  parts (`source` + `rings`, style and per-piece choices copied); slivers under 1 mm² or narrower than
  0.5 mm (the wand's edge sits just inside the piece's) go; a piece covered completely is removed
  (`piece_weld.remove`). Undo restores the old options, so both come back.
- Auto trace stores each new outline in place (`rings` on the piece's own edit), so it never makes
  copies and the 100 copied-pieces limit does not apply; ids, names and choices stay. New outline
  points are budgeted against `MAX_PART_POINTS`: pieces that do not fit are left, the route returns
  `piece_notice` ("Traced N pieces; M left as they were …", never saved) and the Pieces panel shows it.
- Open machine file: the silhouette picture's own pieces are stored `cut`, so the Pieces panel lists
  only the recognized parts and nothing sews the silhouette. Designs opened earlier keep their
  hidden rows.
- Recognition on files structured like commercial ones (tested on our own synthetic files: objects
  of one thread joined by travel runs without trims, edge-run and crossing-row underlay under
  tatami, centre-walk, edge-walk and zigzag underlay under satin, tie-in/tie-off, jumps without
  trims, a 50 mm move in 1.5 mm jumps, one thread used twice; PES and DST):
  - `read`: jumps are measured from the last stitch, so a long move made of many short jumps starts
    a new block; a short move is sewn through as one stitch.
  - `pieces`: each connected area left after the 0.8 mm opening is one object; stitches within
    `REACH_MM` of it are its own. The stitches between areas (back-and-forth folded, so ties go) are
    split where they turn more than `TURN_DEG` (30°); a straight stretch (≤ 1.1× its chord) leaving or
    reaching an area is travel, a run from an area back into it is travel, the rest is a running or
    triple line. Objects keep the file's order.
  - `_top`: of 16 starts, the latest whose stitches alone (closed like the area) still cover 95% of
    the area; satin turns and stitch direction are read from there, so underlay is left out.
  - Limit: two objects of one thread that overlap or touch are still one area, so one piece.
- Multi-colour photo stitch: `thread_matching.matched_threads` turns the k-means colours into
  distinct threads of one chart (the chart with the smallest total CIEDE2000, the closest colour
  choosing first); the two-nearest mix is computed with those threads' Lab colours, so stitches,
  playback and machine files use real thread colours; `photo_lines.chart` and `thread_names` name
  them. The chart is not the remembered menu choice (that lives in the browser).
- Studio Colours panel: Compare thread suggestions has the thread chart menu (All charts or one),
  using `/lettering/native/thread?chart=` and the same remembered `needler.threadChart` as the
  Text page; it asks when the suggestions are opened or the chart changes.
