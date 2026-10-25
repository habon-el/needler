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
