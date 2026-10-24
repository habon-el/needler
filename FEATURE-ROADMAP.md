# Feature roadmap

Started 2026-10-24. This tracks the tools a professional embroidery digitizer expects, one by one,
against what Needler has, so none is skipped.

**Sources.** The tool list follows the menus and toolboxes of commercial digitizing software and
public digitizing guides. Every threshold Needler uses is our own choice, informed by published
digitizing guidance. No third-party code, text, fonts, motifs, pattern data or design files are used.

**Status.** ✅ done · ◐ partial · ✗ missing · — not planned (machine hardware, licensing, separate products).
**Priority.** P1 changes stitch quality on every design · P2 is a common digitizing tool · P3 is specialist.

## 1. Design setup
| Tool | Needler | Status | P |
|---|---|---|---|
| Fabric presets (about 25 fabrics, per-fabric density, pull, underlay, backing/topping) | Fabric menu in studio and lettering, 16 fabrics (other common fabrics map to these), satin spacing and pull, backing/topping | ✅ 2026-10-24 | |
| Custom fabric settings | — | ✗ | P3 |
| Hoop list, show hoop, rotate hoop, saved hoops | Sewing-area check, hoop size | ◐ no hoop picker by brand | P2 |
| Multi-hooping (add hoops, calculate, preview hoopings) | — | ✗ | P3 |
| Product visualizer, product/fabric colour | Fabric colour, PNG mockup | ◐ | P3 |
| Colourways (create, rename, switch) | Thread recolour variants (`thread_variants.py`) | ◐ no named colourways | P2 |
| Thread charts (166), match to chart, colour wheel | `thread_matching.py` (pyembroidery charts, CIEDE2000) | ◐ fewer charts | P3 |
| Grid, rulers, guides, snap, measure | Ruler, measure | ◐ no guides or snap | P3 |

## 2. Digitizing (manual)
| Tool | Needler | Status | P |
|---|---|---|---|
| Digitize closed / open shape, blocks, freehand | Area editing is picture-based; point editing in editor | ◐ no vector drawing tools | P2 |
| Digitize holes, fill holes, remove holes | — | ✗ | P2 |
| Add / remove stitch angles | Stitch direction review | ◐ | P2 |
| Reshape, knife, split curve, break apart | Split at point, select/move points | ◐ | P2 |
| Click to fill (with/without holes), turning fill, outline, centerline | Area styles, auto satin, line art | ◐ no click tool | P2 |
| Appliqué (placement, tack-down, cover, stops) and Export cutting | area style Appliqué: placement run, stop, zigzag tack-down, stop, 3 mm satin cover; cutting shapes SVG at actual size | ✅ 2026-10-24 | |
| Partial appliqué, combine appliqué, remove appliqué overlaps | — | ✗ | P3 |
| Buttonholes, basting stitch markers | — | ✗ | P3 |

## 3. Stitch types — fills
| Tool | Needler | Status | P |
|---|---|---|---|
| Tatami | `stitch_fills.tatami` | ✅ | |
| Satin fill | `satin`, `auto_satin` | ✅ | |
| Turning satin (follows the shape) | `auto_satin` (font machinery) | ✅ | |
| Step fill (patterned tatami) | `stitch_fills.step_fill`, area style Step fill | ✅ 2026-10-24 | |
| Raised satin | 3D satin | ✅ | |
| Contour fill | contour | ✅ | |
| Radial fill | `stitch_fills.radial`, area style Radial (tatami where rays can't reach) | ✅ 2026-10-24 | |
| Gradient fill (spacing ramps across the area) | `stitch_fills.gradient`, area style Gradient | ✅ 2026-10-24 | |
| Wave / Ripple fill | ripple (circular) | ◐ no wave | P3 |
| Offset fill | contour | ◐ | P3 |
| Pattern fill / Motif fill | motif (diamond) | ◐ one pattern | P3 |
| Blackwork, candlewicking, lacework fills | — | ✗ | P3 |
| Cross-stitch fill | cross | ✅ | |
| Stipple run / backstitch / stemstitch fill | stipple run | ◐ run only | P3 |
| Maze, star fill, elastic embossed, sculptured fancy | embossed (diamond overlay) | ◐ | P3 |
| Florentine effect, colour blending | — | ✗ | P3 |
| 3D puff | puff | ✅ | |

## 4. Stitch types — outlines
| Tool | Needler | Status | P |
|---|---|---|---|
| Single run | running | ✅ | |
| Triple run | bean | ✅ | |
| Backstitch | `stitch_paths.backstitch`, border style | ✅ 2026-10-24 | |
| Stemstitch | `stitch_paths.stemstitch`, border style | ✅ 2026-10-24 | |
| Blanket (E-stitch) | `stitch_paths.blanket` (spikes inward), border style | ✅ 2026-10-24 | |
| Zigzag outline | `stitch_paths.zigzag_outline`, border style | ✅ 2026-10-24 | |
| Satin outline / raised satin outline | satin border | ✅ | |
| Motif run, pattern run, sculpture run | — | ✗ | P3 |
| Blackwork run, candlewicking, redwork, hand stitch | — | ✗ | P3 |
| Couching / laydown | — | ✗ | P3 |

## 5. Stitch effects and quality
| Tool | Needler | Status | P |
|---|---|---|---|
| Underlay types (centre, edge, zigzag, double zigzag, tatami) | centre walk, edge run, zigzag, tatami underlay | ◐ no double zigzag | P2 |
| Auto underlay by column width / lettering height | `stitch_satin.auto_underlay`, `embroidery_fonts.size_profile` | ✅ 2026-10-24 | |
| Pull compensation (fixed, %, auto) | mm + `pull_compensation_percent`; auto by fabric | ✅ 2026-10-24 | |
| Satin auto spacing by column width | `stitch_satin.auto_spacing` (auto satin; `satin_auto_spacing` on columns) | ✅ 2026-10-24 | |
| Satin Auto Split (random needle holes) | `stitch_satin.split_rows`, staggered, 7 mm (`satin_split_mm`) | ✅ 2026-10-24 | |
| Automatic corners, shortening | `stitch_satin.shorten_inner` on auto satin (`satin_shortening` on columns); no mitre/cap corners yet | ◐ | P2 |
| Textured edge, feather edge | — | ✗ | P3 |
| 3D globe effect, hand stitch effect | — | ✗ | P3 |
| Tie-in / tie-off, trims, "Always tie-off & trim" | locks, trims | ✅ | |
| Auto start and end, closest join | `engine.closest_join` (areas nearest-first) + branching | ◐ entry/exit points not yet chosen per area | P2 |
| Remove small stitches, minimum stitch | min-stitch filter | ✅ | |
| Adjust stitch spacing (scale density) | — | ✗ | P2 |

## 6. Arranging and editing
| Tool | Needler | Status | P |
|---|---|---|---|
| Select, group, lock, hide, duplicate (with offset) | Piece panel: select, lock | ◐ | P2 |
| Mirror X/Y, rotate (15°/45°), skew, resize ±10% | Size ±10%, piece transforms | ◐ | P2 |
| Align / space evenly / same size | — | ✗ | P3 |
| Mirror-copy, wreath, circle layout, array, reflect | — | ✗ | P3 |
| Create outlines and offsets, outline design, create border | Outer-silhouette border (`borders.py`) | ◐ no offsets per object | P2 |
| Smooth shapes, weld | — | ✗ | P3 |
| Remove overlaps | Colour knockout; areas never stack | ✅ | |
| Stitch edit, insert stop/trim, convert to manual | Remove stitches by area | ◐ | P3 |
| Recognize stitches (machine file → objects) | — | ✗ | P3 |
| Morphing (pinch, punch, twirl, wave) | — | ✗ | P3 |

## 7. Sequencing
| Tool | Needler | Status | P |
|---|---|---|---|
| Sequence by colour / by selection / move up-down | Sew earlier / later | ◐ | P2 |
| Apply closest join | `engine.closest_join` | ✅ 2026-10-24 | |
| Optimize colour changes | largest-colour-first | ◐ | P2 |
| Branching, auto-sequence outlines | `_branch`, line-art Euler routes | ◐ | P2 |
| Travel by stitch / colour / object (Stitch Player) | Playback | ✅ | |

## 8. Lettering and monograms
| Tool | Needler | Status | P |
|---|---|---|---|
| Large embroidery font library | 18 own fonts | ◐ | P3 |
| TrueType conversion | own satin conversion (`satin_font.py`) | ✅ | |
| Size-dependent underlay, density and pull | `size_profile` + fabric pull | ✅ 2026-10-24 | |
| Auto split for wide lettering columns | satin split on all flat columns; fonts still switch to fill above ~15 mm | ◐ | P2 |
| Letter / line spacing, kerning | GPOS kerning + letter spacing (mm) and line spacing (%) in Layout | ✅ 2026-10-24 | |
| Joins: closest / bottom / as digitized | letters that touch are joined inside both (script fonts); separate letters keep their cut, since an uncut thread over fabric fails the file checks | ◐ no bottom join | P3 |
| Letter sequence (centre-out for caps, line by line) | left to right, centre out | ✅ 2026-10-24 | |
| Baselines: arc, circle, custom line, fixed length | straight, arc over, arc under (radius); letters stay rigid | ◐ no full circle, custom line or fixed length | P3 |
| Lettering envelopes, elastic lettering | — | ✗ | P3 |
| Monogramming (templates, ornaments, borders) | — | ✗ | P3 |
| Team names | — | ✗ | P3 |

## 9. Auto-digitizing
| Tool | Needler | Status | P |
|---|---|---|---|
| Auto-digitize instant | Digitize for me | ✅ | |
| Prepare artwork: colour reduction, merge, details slider | `preparation.py`; Detail slider in Digitize for me (smallest area kept 8 to 0.25 mm²) | ✅ 2026-10-24 | |
| Colour roles fill / detail / omit, omit background | plain background left out automatically ("keep the background" sews it); details get satin or run by width and sew last (largest colour first) | ✅ 2026-10-24 | |
| Fill vs satin vs run by width | run under 0.45 mm and for pixel-thin lines ≥ 1 mm long; satin ≤ 4.5 mm; else tatami | ◐ one area is still one type (no satin/fill split) | P2 |
| Add outlines | `engine.colour_outlines`: one branched run on every colour edge, sewn last; checkbox or "outline" in the request | ✅ 2026-10-24 | |
| Multi-colour photo stitch, open photo stitch | photo stitch (experimental) | ◐ | P3 |
| One-colour photo stitch | photo lines | ✅ | |
| Auto trace to vectors, magic wand | — | ✗ | P3 |

## 10. Output and management
| Tool | Needler | Status | P |
|---|---|---|---|
| Export machine file (many formats) | DST, PES, JEF, EXP, XXX, U01, PEC | ✅ | |
| Print / worksheet / PDF | Check stitches report | ◐ no printable worksheet | P2 |
| Design information, overview | Design health | ✅ | |
| Realistic 3D preview | 3D view | ✅ | |
| Embroidery library, find designs, convert designs | Library | ◐ no batch convert | P3 |
| Templates, save as template | — | ✗ | P3 |
| Send to machine (wireless / USB) | — | — | |
| Cross Stitch, Quilter, cutwork, trapunto, stumpwork, bling, sequins | — | — (separate products) | |

## Build order

1. **P1 engine — done 2026-10-24.** Satin auto split with staggered holes; satin spacing by column width; underlay chosen by width; underlay chosen by letter height; percentage pull compensation; closest join between same-colour areas; fabric settings reaching lettering.
2. **P2 stitch types — done 2026-10-24 (mitre/cap corners still open).** Backstitch, stemstitch, blanket, zigzag outline, step fill, radial fill, gradient fill, smart corners.
3. **P2 digitizing and layout.** Lettering arcs, spacing, joins and letter order done 2026-10-24. Next: auto-digitize colour roles, outlines and details slider; appliqué; holes; mirror, rotate, align.
4. **P3.** Everything else above, as separate rounds.
