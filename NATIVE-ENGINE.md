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
