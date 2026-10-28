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
| Custom fabric settings | My own fabric under the Fabric menu (studio and lettering): a listed fabric with your own fill and satin spacing, pull, longest stitch and underlay; saved for every design, and each design keeps its own copy | ✅ 2026-10-27 | |
| Hoop list, show hoop, rotate hoop, saved hoops | Edit step "Hoop": sewing fields by machine brand plus common sizes, Turn 90°, a fit note (spare room or how much too big), Show on canvas, My own hoop (save / delete); the worksheet names the chosen hoop | ✅ 2026-10-25 | |
| Multi-hooping (add hoops, calculate, preview hoopings) | A design too big for the hoop is split into hoopings (up to 12): seams fall between objects where they can, cut thread ends are tied off, neighbours share pink alignment crosses; Show hoopings on the stitches; one checked machine file per hooping | ✅ 2026-10-27 | |
| Product visualizer, product/fabric colour | Fabric colour, PNG mockup | ◐ | P3 |
| Colourways (create, rename, switch) | Colours panel "Colourway": Save as new, Rename, Delete, and a menu to switch; each colourway keeps the thread colours (and border thread) per design, and the stitches and machine files follow the one in use | ✅ 2026-10-25 | |
| Thread charts (166), match to chart, colour wheel | `thread_matching.py` (pyembroidery charts, CIEDE2000) | ◐ fewer charts | P3 |
| Grid, rulers, guides, snap, measure | Ruler and measure; Pieces panel "Guides and snap": + Across / + Down guides (or drag one in from the canvas top or left edge), drag on the canvas or type the position in mm from the hoop centre, ✕ or drop off the canvas to remove, up to 20, saved with the design; Snap: moving and drawing pieces lock onto guides, the hoop centre lines and the grid; faint grid 1 / 5 / 10 mm. Guides never change stitches | ✅ 2026-10-26 | |

## 2. Digitizing (manual)
| Tool | Needler | Status | P |
|---|---|---|---|
| Digitize closed / open shape, blocks, freehand | Draw a shape: rectangle, ellipse, polygon (click corners) and freehand become new pieces in a chosen thread colour; Line (click points) and Freehand line are open stitched lines, running or triple stitch; all move, copy and delete like any piece | ✅ 2026-10-25 | |
| Digitize holes, fill holes, remove holes | cut a hole: Erase area; remove / fill holes: "Sew over holes in this area" (stitches run across, an empty hole is filled) | ✅ 2026-10-24 | |
| Add / remove stitch angles | "Stitch direction °" per area in the style panel (empty = automatic) | ✅ 2026-10-24 | |
| Reshape, knife, split curve, break apart | Knife: drag a line across a piece to cut it into parts (each part its own piece); split at point, move points | ◐ no node reshaping of pieces | P3 |
| Click to fill (with/without holes), turning fill, outline, centerline | Pieces panel "Click to fill": click an empty space closed by the artwork; it fills up to and 0.3 mm under the lines (gaps up to ~0.8 mm bridged), sewn first; Keep holes on/off. Auto satin, line art | ✅ 2026-10-25 | |
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
| Contour fill | Offset fill | ✅ | |
| Radial fill | `stitch_fills.radial`, area style Radial (tatami where rays can't reach) | ✅ 2026-10-24 | |
| Gradient fill (spacing ramps across the area) | `stitch_fills.gradient`, area style Gradient | ✅ 2026-10-24 | |
| Wave / Ripple fill | area style Wave: tatami rows that rise and fall along a smooth wave (10 mm long, 1.2 mm high, lined up across areas), underlay, around holes; Ripple: circular | ✅ 2026-10-26 | |
| Offset fill | area style Offset fill (was Contour): each row an inset of the outline by one more row spacing, rings around holes, joined into one run by inside steps, with underlay | ✅ 2026-10-26 | |
| Pattern fill / Motif fill | area style Motif with a Pattern choice: diamonds (default), hearts, stars, scales (rows of half circles) or circles, repeated every 4 mm and clipped to the area, around holes | ✅ 2026-10-26 | |
| Blackwork, candlewicking, lacework fills | area styles Blackwork (lattice of long lines with a diamond in every cell), Candlewicking (raised knots on staggered rows), Lacework (honeycomb net); open fills, travel inside the area | ✅ 2026-10-27 | |
| Cross-stitch fill | cross | ✅ | |
| Stipple run / backstitch / stemstitch fill | area style Stipple with a Stitch choice: single run (default), backstitch (each stitch partly sewn back over) or stemstitch (short slanted stitches, rope look) along the same meandering line | ✅ 2026-10-26 | |
| Maze, star fill, elastic embossed, sculptured fancy | area styles Maze (one line winding like a labyrinth, square corners) and Star (star-shaped spiral from the centre); Elastic: the Motif patterns stretched over the shape, a whole number of rows from its top edge to its bottom edge, so repeats grow, shrink and bend with it; Sculptured: tatami whose needle holes run along both diagonals every 4 mm, a raised diamond lattice; embossed (diamond overlay) | ✅ 2026-10-27 | |
| Florentine effect, colour blending | area style Florentine: tatami rows that copy the curve of the area's top edge (smoothed, kept gentle, so round tops sew as a dome); area style Shaded: a darker shade fades across the fill | ✅ 2026-10-27 | |
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
| Motif run, pattern run, sculpture run | border styles Motif run (diamonds, triangles or scallops along the line), Pattern run (wave, loops or key repeated end to end), Sculpture run (two stitches forward, one back: a raised cord) | ✅ 2026-10-27 | |
| Blackwork run, candlewicking, redwork, hand stitch | border styles Blackwork run (sewn twice through the same holes), Hand stitch (bold dashes, fine links), Candlewicking (raised knots); black lines: Redwork, every line twice as one route per drawing with no cuts | ✅ 2026-10-27 | |
| Couching / laydown | `stitch_paths.couching`, border style Couching: triple-stitch cord with ties across it | ✅ 2026-10-27 | |

## 5. Stitch effects and quality
| Tool | Needler | Status | P |
|---|---|---|---|
| Underlay types (centre, edge, zigzag, double zigzag, tatami) | centre walk, edge run, zigzag, double zigzag (auto from 8 mm), tatami underlay | ✅ 2026-10-24 | |
| Auto underlay by column width / lettering height | `stitch_satin.auto_underlay`, `embroidery_fonts.size_profile` | ✅ 2026-10-24 | |
| Pull compensation (fixed, %, auto) | mm + `pull_compensation_percent`; auto by fabric | ✅ 2026-10-24 | |
| Satin auto spacing by column width | `stitch_satin.auto_spacing` (auto satin; `satin_auto_spacing` on columns) | ✅ 2026-10-24 | |
| Satin Auto Split (random needle holes) | `stitch_satin.split_rows`, staggered, 7 mm (`satin_split_mm`) | ✅ 2026-10-24 | |
| Automatic corners, shortening | shortening on tight curves; mitre corners, capped when sharper than about 60° (satin borders, appliqué cover) | ✅ 2026-10-24 | |
| Textured edge, feather edge | area style Feathered: rows across the area stop short at random, on One edge (up to 4 mm), Both edges (3 mm) or a Textured edge (0.8 mm); the two rows of each turn form one tip | ✅ 2026-10-27 | |
| 3D globe effect, hand stitch effect | area styles Globe (tatami whose rows and stitches crowd towards the edges, so it looks domed) and Hand stitch (open rows of uneven stitches, 0.75–4.25 mm); hand stitch border | ✅ 2026-10-27 | |
| Tie-in / tie-off, trims, "Always tie-off & trim" | locks, trims | ✅ | |
| Auto start and end, closest join | areas nearest-first, and each fill starts at the corner nearest the previous stitch; branching | ✅ 2026-10-24 | |
| Remove small stitches, minimum stitch | min-stitch filter | ✅ | |
| Adjust stitch spacing (scale density) | Density: Lighter / Normal / Denser next to Fabric | ✅ 2026-10-24 | |

## 6. Arranging and editing
| Tool | Needler | Status | P |
|---|---|---|---|
| Select, group, lock, hide, duplicate (with offset) | Piece panel: select, name, group, lock, hide, Duplicate (5 mm offset), Delete copy | ✅ 2026-10-24 | |
| Mirror X/Y, rotate (15°/45°), skew, resize ±10% | Mirror ⇋ ⇅, rotate ↺15° ↻15° ↻45° or any angle, Skew °, size ±10% | ✅ 2026-10-24 | |
| Align / space evenly / same size | Pieces panel Line up, 2+ selected: align left / centre / right / top / middle / bottom; space evenly across or down (3+); same width / height (proportions kept) or same size as the first piece picked | ✅ 2026-10-25 | |
| Mirror-copy, wreath, circle layout, array, reflect | Pieces panel Repeat: Mirror copy ⇋ ⇅ (reflected, touching the edge), Circle (2–36 around a radius, Turn on for a wreath), Array (rows × columns with a gap in mm); each copy is its own piece | ✅ 2026-10-25 | |
| Create outlines and offsets, outline design, create border | Outer-silhouette border (`borders.py`); Pieces panel Outline per part: Running, Triple or Satin, on the edge or a gap up to 6 mm outward, own thread colour, sewn after all fills | ✅ 2026-10-25 | |
| Smooth shapes, weld | Pieces panel: ⊕ Weld joins 2+ touching or overlapping pieces of one thread into one (the first picked keeps its style); Smooth (Light / More) takes out pixel steps and small wiggles, keeping sharp corners and the size (`piece_weld.py`) | ✅ 2026-10-26 | |
| Remove overlaps | Colour knockout; areas never stack | ✅ | |
| Stitch edit, insert stop/trim, convert to manual | Remove stitches by area; Check stitches: Add stop here, Add cut here (tie-off and tie-in), Delete this stitch, Move this stitch (up to 3 mm) at the playback position, saved with the design and checked against 0.3–7 mm and empty fabric. Converting a whole part to hand-placed stitches is not offered | ✅ 2026-10-25 | |
| Recognize stitches (machine file → objects) | — | ✗ | P3 |
| Morphing (pinch, punch, twirl, wave) | — | ✗ | P3 |

## 7. Sequencing
| Tool | Needler | Status | P |
|---|---|---|---|
| Sequence by colour / by selection / move up-down | Pieces panel "Sewing order": Sew earlier / Sew later, Sew in the order I picked (Ctrl-click order), Automatic order; both stitch paths follow it | ✅ 2026-10-25 | |
| Apply closest join | `engine.closest_join` | ✅ 2026-10-24 | |
| Optimize colour changes | one block per colour, also for edited pieces, copies and cut parts | ✅ 2026-10-24 | |
| Branching, auto-sequence outlines | Outlines of one thread sewn together, nearest first; a ring begins where it meets the next line, and the thread travels up to 12 mm along its own sewn lines instead of cutting; round and slanted colour outlines no longer break into pieces (`_branch`, line-art Euler routes) | ✅ 2026-10-25 | |
| Travel by stitch / colour / object (Stitch Player) | Playback | ✅ | |

## 8. Lettering and monograms
| Tool | Needler | Status | P |
|---|---|---|---|
| Large embroidery font library | 18 own fonts | ◐ | P3 |
| TrueType conversion | own satin conversion (`satin_font.py`) | ✅ | |
| Size-dependent underlay, density and pull | `size_profile` + fabric pull | ✅ 2026-10-24 | |
| Auto split for wide lettering columns | big letters stay satin, sewn as split satin (staggered stitches of at most 6.85 mm, double zigzag under strokes from 8 mm) up to 12 mm wide strokes; only wider strokes, words whose satin fails a file check, and the two fonts that trace badly larger, switch to fill | ✅ 2026-10-25 | |
| Letter / line spacing, kerning | GPOS kerning + letter spacing (mm) and line spacing (%) in Layout | ✅ 2026-10-24 | |
| Joins: closest / bottom / as digitized | letters that touch are joined inside both (script fonts); separate letters keep their cut, since an uncut thread over fabric fails the file checks | ◐ no bottom join | P3 |
| Letter sequence (centre-out for caps, line by line) | left to right, centre out | ✅ 2026-10-24 | |
| Baselines: arc, circle, custom line, fixed length | Shape buttons Straight / Arch / Smile / Circle / Wave; Curve slider in degrees for arch and smile (the circle follows the words' length); Full circle of a chosen size, the first line over the top reading clockwise and an optional second line along the bottom reading left to right; Wave (one S-curve) with a strength slider as the custom line; Fixed length (mm) spreads or squeezes the letter spacing so the stitched line is exactly that long along its baseline, refused with the shortest or longest workable length when letters would overlap or end up more than a letter's height apart; letters stay rigid, and a bend that makes letters touch is refused | ✅ 2026-10-26 | |
| Lettering envelopes, elastic lettering | — | ✗ | P3 |
| Monogramming (templates, ornaments, borders) | Text page "Monogram & frame": classic layout (middle initial bigger), satin frames (circle, oval, square, diamond, hexagon, shield, heart) and an Ornament: crown above, laurel round the sides and bottom, swirls left and right, or a line below; satin drawn in code, scaled to the letters, placed round the words and frame, in the thread colour, sewn last | ✅ 2026-10-26 | |
| Team names | Text page "Team names": one name per line (up to 50, 40 letters each), the same font, height, shape and colour for all; Make all names builds and checks one file per name in turn, lists each width and stitches, and names any too wide or failing a check with the reason (too wide: offers one smaller height for all, never resizes); Download all (zip) in the chosen machine format | ✅ 2026-10-25 | |

## 9. Auto-digitizing
| Tool | Needler | Status | P |
|---|---|---|---|
| Auto-digitize instant | Digitize for me | ✅ | |
| Prepare artwork: colour reduction, merge, details slider | `preparation.py`; Detail slider in Digitize for me (smallest area kept 8 to 0.25 mm²) | ✅ 2026-10-24 | |
| Colour roles fill / detail / omit, omit background | plain background left out automatically ("keep the background" sews it); details get satin or run by width and sew last (largest colour first) | ✅ 2026-10-24 | |
| Fill vs satin vs run by width | run under 0.45 mm and for pixel-thin lines ≥ 1 mm long; satin ≤ 4.5 mm; else tatami; thin limbs split off as satin automatically; Pieces panel "Satin here": drag a line where a thin part starts, that side becomes satin over the rest's fill | ✅ 2026-10-25 | |
| Add outlines | `engine.colour_outlines`: one branched run on every colour edge, sewn last; checkbox or "outline" in the request | ✅ 2026-10-24 | |
| Multi-colour photo stitch, open photo stitch | photo stitch (experimental) | ◐ | P3 |
| One-colour photo stitch | photo lines | ✅ | |
| Auto trace to vectors, magic wand | — | ✗ | P3 |

## 10. Output and management
| Tool | Needler | Status | P |
|---|---|---|---|
| Export machine file (many formats) | DST, PES, JEF, EXP, XXX, U01, PEC | ✅ | |
| Print / worksheet / PDF | "Print worksheet" on Save and download (pictures and text): size, stitches, thread changes, cuts, sewing time, smallest standard hoop, fabric, backing/topping, the sewing sequence with closest threads from one chart, stops, a tick column, and the design at actual size with centre and start marks; the browser prints or saves it as PDF | ✅ 2026-10-25 | |
| Design information, overview | Design health | ✅ | |
| Realistic 3D preview | 3D view | ✅ | |
| Embroidery library, find designs, convert designs | Library | ◐ no batch convert | P3 |
| Templates, save as template | — | ✗ | P3 |
| Send to machine (wireless / USB) | — | — | |
| Cross Stitch, Quilter, cutwork, trapunto, stumpwork, bling, sequins | — | — (separate products) | |

## 8b. Text page — ease of use (found while making a curved 3D puff design, 2026-10-25)
| Item | Needler | Status | P |
|---|---|---|---|
| 1. Curving text reachable | Shape row under the font: Straight / Arch / Smile, Curve slider | ✅ 2026-10-25 | |
| 2. AI help on the Text page | "Ask AI" box: Claude sets the text settings, checking each try with the advice check, then the stitches are made (`text_ai.py`) | ✅ 2026-10-25 | |
| 3. Spacing and letter order visible | "Spacing & letter order" section; Fabric choice shown too | ✅ 2026-10-25 | |
| 4. Puff-ready helper | with 3D puff on, the font list marks which fonts can puff; height fix button | ✅ 2026-10-25 | |
| 5. Clear width box | "Max width (mm)", default 100 mm, fix buttons to widen or shrink | ✅ 2026-10-25 | |
| 6. Product presets on the Text page | "For": cap front, left chest, sleeve, jacket back (max width; caps also get cap fabric and centre-out order) | ✅ 2026-10-25 | |
| 7. Preview shows the curve | instant preview draws the arch or smile before stitching | ✅ 2026-10-25 | |
| 8. All problems at once | live list under Make stitches (`/lettering/native/advice`) | ✅ 2026-10-25 | |
| 9. Messages say what to change | every problem has a one-click fix; too-wide message names Max width | ✅ 2026-10-25 | |
| 10. Arc size checked against the words | curve in degrees, so the circle always fits the words; exact width from the laid-out letters | ✅ 2026-10-25 | |
| 11. Clearer section names | "About the height", "About these stitches" | ✅ 2026-10-25 | |
| 12. Thread names for the text colour | closest three machine threads under the colour; click one to use it | ✅ 2026-10-25 | |

## 8c. Lessons from professional designs (2026-10-25)
Studied the bundled sample designs: a bird picture and 96 monogram templates (previews and design summaries).
| Lesson | Needler | Status | P |
|---|---|---|---|
| 1. Thin parts as satin that follows and tapers | thin limbs of thick areas split off as satin (overlap 0.4 mm); long bands up to 6.5 mm wide are satin; the Satin style follows any shape up to 8 mm wide | ✅ 2026-10-25 | |
| 2. Sewn back to front in layers | Sewing order: Fewest colour changes / Best look (back to front, a thread may repeat) | ✅ 2026-10-25 | |
| 3. Dark details and two-shade depth | Outline colour Auto (a darker shade of each part's thread, on the part on top); area style Shaded | ✅ 2026-10-25 | |
| 4. Decorative line inside borders | border "Line inside": triple stitch, 1.2 mm inside the border | ✅ 2026-10-25 | |
| 5. Monograms with frames | classic monogram + 7 satin frames + 4 ornaments (crown, laurel, swirls, line below) on the Text page | ✅ 2026-10-26 | |

## AI digitizer: every tool, the person's own words (next, before the rest of P3)
Claude inside Needler (`auto_claude.py`) can reach only about 15 settings; the area styles, most borders,
sewing order, density, outline colour, all fabrics, the hoop and multi-hooping are out of its reach, and its
instructions are typed by hand, so they fall behind every new feature.

| Step | What | Status |
|---|---|---|
| 1 | Claude's tool choices built from Needler's own lists (area styles and their choices, borders, fabrics incl. the person's own, hoops); a test fails when a feature reaches the app but not Claude | ✓ 2026-10-27: fabrics (all 16 + the person's own), every border kind with motif/pattern, every hoop (+ own) offered and wired; area styles listed in the catalog, offered with step 3 |
| 2 | Digitizer's handbook in `knowledge/`: per tool what it does, when to use it, when not, its limits; cached with the instructions | ✓ 2026-10-28: `knowledge/handbook.json` (modes, every area style and its choices, every border, every make_stitches setting, how Needler sews) plus the fabric presets, sent as a cached system block; a test fails when a tool has no handbook row |
| 3 | New controls: style per colour (choice, direction), every border kind, line inside, placement, sewing order, density, outline colour, fabric, hoop, appliqué, holes | part 1 ✓ 2026-10-28: style and direction per thread colour (`colour_styles`; parts a style does not suit keep the automatic choice), border placement and line inside. part 2 ✓ 2026-10-28: holes sewn over per thread colour (all or up to a size), sewing order, density, outlines and their colour; appliqué through the style per colour |
| 4 | Feedback per colour after each attempt: area sizes, widest part, style used, why a style was refused | ✓ 2026-10-28: the engine records what every area became (size, widest part, style, the style asked for and why it was refused); per_colour sums it per thread for Claude |
| 5 | The person's request leads: Claude shows a short plan (what each colour is, the style and why), follows the request, and says which tools it used | ✓ 2026-10-28: the request comes before every rule in the instructions; the plan (one line per colour) shows in the steps and the result; finish says how the request was followed and the tools used |
| 6 | Scripted tests with a fake Claude (free), then real runs on the person's own pictures within a $2 test budget | part 1 ✓ 2026-10-28: scripted runs through the real engine (every control, refusals, limits); a satin border with the background left out no longer fails. Real run ✓ 2026-10-28 on the rose only (to save credit; $0.19): request followed, plan and tools shown, feedback per colour used (holes sewn over, specks merged). Found: merging a colour on a cut-out subject fails the file check (stitches cross the removed background), so the fewer-cuts version could not be kept |

## Session plan (read this first each session; tick the row when it is pushed)

| Session | Work | Status |
|---|---|---|
| 7 | AI digitizer step 1 (Claude's choices from Needler's lists); "remove the background" fix | ✓ 2026-10-27 |
| 8 | AI digitizer step 2 (handbook) | ✓ 2026-10-28 |
| 9 | AI digitizer step 3, part 1: style and direction per colour; every border option (placement, line inside) | ✓ 2026-10-28 |
| 10 | AI digitizer step 3, part 2: sewing order, density, outline colour, appliqué, holes | ✓ 2026-10-28 |
| 11 | AI digitizer steps 4 and 5: feedback per colour; the person's request leads with a plan | ✓ 2026-10-28 |
| 12 | AI digitizer step 6: fake-Claude tests, then real runs on the person's pictures ($2 budget) | ✓ 2026-10-28 |
| 13 | P3: templates / save as template; product colour and mockup | ✗ |
| 14 | P3: partial, combined and overlap-free appliqué; buttonholes and basting markers | ✗ |
| 15 | P3: lettering envelopes and elastic lettering; more fonts | ✗ |
| 16 | P3: morphing (pinch, punch, twirl, wave); auto trace to vectors and magic wand | ✗ |
| 17 | P3: multi-colour and open photo stitch; recognize stitches (machine file to objects) | ✗ |
| 18–19 | Parked bugs (parallel agents): merging a colour on a cut-out subject fails the file check; rose gaps and flat leaves; Start does nothing over an old result; white parts dropped and white merging with pale sky; colour change unticks "I approve"; ~30 edge-speck cleanup choices; stuck on "Opening image editor…"; big script satin gaps; designs page and studio freezing Chrome | ✗ |

Sessions after 12 are estimates; if a row runs long, it moves to the next session and the rows below shift.

## Build order

1. **P1 engine — done 2026-10-24.** Satin auto split with staggered holes; satin spacing by column width; underlay chosen by width; underlay chosen by letter height; percentage pull compensation; closest join between same-colour areas; fabric settings reaching lettering.
2. **P2 stitch types — done 2026-10-24 (mitre/cap corners still open).** Backstitch, stemstitch, blanket, zigzag outline, step fill, radial fill, gradient fill, smart corners.
3. **P2 digitizing and layout.** Lettering arcs, spacing, joins and letter order done 2026-10-24; wide letters as split satin 2026-10-25. Next: auto-digitize colour roles, outlines and details slider; appliqué; holes; mirror, rotate, align.
4. **P3.** Everything else above, as separate rounds.
