# Native stitch engine and embroidery fonts

Updated 2026-10-18. Needler no longer needs Ink/Stitch or Inkscape. The engine
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
| `vector_raster.py` | SVG rendering for typed lettering and SVG uploads (replaces Inkscape). |

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
- Revised 2026-10-20 after Wilcom's puff guide, so the foam stays tight:
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
