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
| Product visualizer, product/fabric colour | Fabric colour; Save PNG mockup on a product (T-shirt, polo, hoodie, cap, tote bag, towel) in the fabric colour, with a placement per product (left/right/centre chest, cap front, towel border or corner); the design is shown at real size, with a note when it is bigger than usual for that spot | ✅ 2026-10-28 | |
| Colourways (create, rename, switch) | Colours panel "Colourway": Save as new, Rename, Delete, and a menu to switch; each colourway keeps the thread colours (and border thread) per design, and the stitches and machine files follow the one in use | ✅ 2026-10-25 | |
| Thread charts (166), match to chart, colour wheel | `thread_matching.py` (CIEDE2000): six machine charts, all pyembroidery ships (Brother, Janome, Janome SEW, Husqvarna Viking, Pfaff, Pfaff PCM); no open thread-maker charts exist to add without inventing colours. Pick a chart under the Text page thread names and in the studio Colours panel's Compare thread suggestions (one remembered choice), and on the worksheet (default: the closest chart overall) | ✅ 2026-10-29 | |
| Grid, rulers, guides, snap, measure | Ruler and measure; Pieces panel "Guides and snap": + Across / + Down guides (or drag one in from the canvas top or left edge), drag on the canvas or type the position in mm from the hoop centre, ✕ or drop off the canvas to remove, up to 20, saved with the design; Snap: moving and drawing pieces lock onto guides, the hoop centre lines and the grid; faint grid 1 / 5 / 10 mm. Guides never change stitches | ✅ 2026-10-26 | |

## 2. Digitizing (manual)
| Tool | Needler | Status | P |
|---|---|---|---|
| Digitize closed / open shape, blocks, freehand | Draw a shape: rectangle, ellipse, polygon (click corners) and freehand become new pieces in a chosen thread colour; Line (click points) and Freehand line are open stitched lines, running or triple stitch; all move, copy and delete like any piece | ✅ 2026-10-25 | |
| Digitize holes, fill holes, remove holes | cut a hole: Erase area; remove / fill holes: "Sew over holes in this area" (stitches run across, an empty hole is filled) | ✅ 2026-10-24 | |
| Add / remove stitch angles | "Stitch direction °" per area in the style panel (empty = automatic) | ✅ 2026-10-24 | |
| Reshape, knife, split curve, break apart | Knife: drag a line across a piece to cut it into parts (each part its own piece); split at point; Pieces panel ◇ Points: drag an outline point (snaps like drawing), click an edge to add a point, click a point and press Delete to remove it; lines too; a crossing outline or a hole outside is refused; the piece keeps its name, style and place and its stitches rebuild | ✅ 2026-10-29 | |
| Click to fill (with/without holes), turning fill, outline, centerline | Pieces panel "Click to fill": click an empty space closed by the artwork; it fills up to and 0.3 mm under the lines (gaps up to ~0.8 mm bridged), sewn first; Keep holes on/off. Auto satin, line art | ✅ 2026-10-25 | |
| Appliqué (placement, tack-down, cover, stops) and Export cutting | area style Appliqué: placement run, stop, zigzag tack-down, stop, 3 mm satin cover; cutting shapes SVG at actual size | ✅ 2026-10-24 | |
| Partial appliqué, combine appliqué, remove appliqué overlaps | Appliqué box in the design panel (shown when the design has appliqué): Tuck under parts on top (fabric runs 1.5 mm under later parts, no satin there), Share stops (one colour's pieces: 2 stops in all), Cover joins once; Claude sets them too | ✅ 2026-10-28 | |
| Buttonholes, basting stitch markers | Basting menu (off, around the design, around the hoop; sewn first in its own thread, no tie-offs); Buttonholes list (position, length, angle, thread; two satin legs, bar tacks, slit left open; sewn last) | ✅ 2026-10-28 | |

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
| Recognize stitches (machine file → objects) | Designs page "Open machine file" (DST, PES, PEC, JEF, EXP, VP3, XXX, U01, HUS, VIP, SEW): the stitches are split at every colour change, cut and jump (many short jumps count as one move); a block sewn without cuts is split into its objects, the runs between them are travel or lines; each object becomes a piece read from how the needle moves (underlay, covered by the top stitching, and tie stitches left out): a narrow band is a line (running, or triple when it goes back and forth), stitches turning back at almost every hole are satin, the rest is tatami with the file's stitch direction; fills and satins get the outline their thread covers (holes kept); thread colours and the file's sewing order are kept; up to 100 parts; the file's silhouette picture is not listed. Needler sews them again, so they move, copy, cut and restyle like any piece | ✅ 2026-10-29 | |
| Morphing (pinch, punch, twirl, wave) | Pieces panel Morph: Pinch (sides cave in, corners stay), Punch (sides bulge out), Twirl (the middle turns, fading to the edge), Wave (two waves across), Strength 10–100%; several pieces morph together around one centre, holes stay, style and direction kept, stitches made again from the new outline (`piece_morph.py`) | ✅ 2026-10-29 | |

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
| Large embroidery font library | 30 own fonts (11 added 2026-10-28: Bangers, Damion, Fjalla One, Francois One, Grand Hotel, Leckerli One, Lilita One, Patua One, Paytone One, Sniglet, Titan One); each new font sewn as every character at its smallest, middle and largest size with no file-check failure | ✅ 2026-10-28 | |
| TrueType conversion | own satin conversion (`satin_font.py`) | ✅ | |
| Size-dependent underlay, density and pull | `size_profile` + fabric pull | ✅ 2026-10-24 | |
| Auto split for wide lettering columns | big letters stay satin, sewn as split satin (staggered stitches of at most 6.85 mm, double zigzag under strokes from 8 mm) up to 12 mm wide strokes; only wider strokes, words whose satin fails a file check, and the two fonts that trace badly larger, switch to fill | ✅ 2026-10-25 | |
| Letter / line spacing, kerning | GPOS kerning + letter spacing (mm) and line spacing (%) in Layout | ✅ 2026-10-24 | |
| Joins: closest / bottom / as digitized | letters that touch are joined inside both (script fonts); Joins: Closest / Bottom under Spacing & letter order: Bottom starts each satin letter at its baseline on the left, the thread running there under the letter's own stitches; separate letters keep their cut, since an uncut thread over fabric fails the file checks | ✅ 2026-10-29 | |
| Letter sequence (centre-out for caps, line by line) | left to right, centre out | ✅ 2026-10-24 | |
| Baselines: arc, circle, custom line, fixed length | Shape buttons Straight / Arch / Smile / Circle / Wave; Curve slider in degrees for arch and smile (the circle follows the words' length); Full circle of a chosen size, the first line over the top reading clockwise and an optional second line along the bottom reading left to right; Wave (one S-curve) with a strength slider as the custom line; Fixed length (mm) spreads or squeezes the letter spacing so the stitched line is exactly that long along its baseline, refused with the shortest or longest workable length when letters would overlap or end up more than a letter's height apart; letters stay rigid, and a bend that makes letters touch is refused | ✅ 2026-10-26 | |
| Lettering envelopes, elastic lettering | Envelope under Shape (straight words, any number of lines): Arch top, Arch bottom, Bulge, Pinch, Bend up, Grow to the right, Shrink to the right, with a Strength slider (10–50% of the words' height); the letters stretch and bend with the shape (satin rails bent point by point, stroke widths measured after bending), not just moved | ✅ 2026-10-28 | |
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
| Multi-colour photo stitch, open photo stitch | Photo stitch: Threads 1–6; with several, the colours picked from the photo become real threads of one chart and each pixel is a mix of its two nearest threads; each thread sews its own zigzag rows at its own angle, as wide as its share, so crossing rows mix the colours. Open (fabric shows): light areas get no stitches and zigzags fill at most 60% of the row; every stitch 0.3–7 mm, checked in PES and DST. The older experimental portrait stitch stays | ✅ 2026-10-29 | |
| One-colour photo stitch | photo lines | ✅ | |
| Auto trace to vectors, magic wand | Pieces panel Trace: 🪄 Magic wand: click the artwork, the connected area of similar colour (Tolerance 1–60, in the Lab colours preparation uses) becomes a new piece in the nearest thread of the design, cut out of the pieces under it so it sews once; Auto trace: the selected pieces, all threads or one thread become clean curves fitted to their pixel outlines, corners kept sharp, specks of holes closed, area kept, in place (no copied-pieces limit) (`piece_trace.py`) | ✅ 2026-10-29 | |

## 10. Output and management
| Tool | Needler | Status | P |
|---|---|---|---|
| Export machine file (many formats) | DST, PES, JEF, EXP, XXX, U01, PEC | ✅ | |
| Print / worksheet / PDF | "Print worksheet" on Save and download (pictures and text): size, stitches, thread changes, cuts, sewing time, smallest standard hoop, fabric, backing/topping, the sewing sequence with closest threads from one chart, stops, a tick column, and the design at actual size with centre and start marks; the browser prints or saves it as PDF | ✅ 2026-10-25 | |
| Design information, overview | Design health | ✅ | |
| Realistic 3D preview | 3D view | ✅ | |
| Embroidery library, find designs, convert designs | Library; select designs, pick a machine format, Download as zip: each design's saved stitches converted and checked like a single download; designs without stitches or failing a check are listed in not-included.txt | ✅ 2026-10-29 | |
| Templates, save as template | Library "Save as template" keeps a frozen copy (picture, size, fabric, hoop, styles, colours); a Templates tab lists them; "Use template" opens a new design from one, and editing it never changes the template; Edit, Rename, Delete template | ✅ 2026-10-28 | |
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
| 6 | Scripted tests with a fake Claude (free), then real runs on the person's own pictures within a $2 test budget | part 1 ✓ 2026-10-28: scripted runs through the real engine (every control, refusals, limits); a satin border with the background left out no longer fails. Real run ✓ 2026-10-28 on the rose only (to save credit; $0.19): request followed, plan and tools shown, feedback per colour used (holes sewn over, specks merged). Found: merging a colour on a cut-out subject fails the file check (stitches cross the removed background), so the fewer-cuts version could not be kept (fixed in session 19: slivers on the subject's edge, not the merge) |

## Session plan (read this first each session; tick the row when it is pushed)

| Session | Work | Status |
|---|---|---|
| 7 | AI digitizer step 1 (Claude's choices from Needler's lists); "remove the background" fix | ✓ 2026-10-27 |
| 8 | AI digitizer step 2 (handbook) | ✓ 2026-10-28 |
| 9 | AI digitizer step 3, part 1: style and direction per colour; every border option (placement, line inside) | ✓ 2026-10-28 |
| 10 | AI digitizer step 3, part 2: sewing order, density, outline colour, appliqué, holes | ✓ 2026-10-28 |
| 11 | AI digitizer steps 4 and 5: feedback per colour; the person's request leads with a plan | ✓ 2026-10-28 |
| 12 | AI digitizer step 6: fake-Claude tests, then real runs on the person's pictures ($2 budget) | ✓ 2026-10-28 |
| 13 | P3: templates / save as template; product colour and mockup | ✓ 2026-10-28 |
| 14 | P3: partial, combined and overlap-free appliqué; buttonholes and basting markers | ✓ 2026-10-28 |
| 15 | P3: lettering envelopes and elastic lettering; more fonts | ✓ 2026-10-28 |
| 16 | P3: morphing (pinch, punch, twirl, wave); auto trace to vectors and magic wand | ✓ 2026-10-29 |
| 17 | P3: multi-colour and open photo stitch; recognize stitches (machine file to objects) | ✓ 2026-10-29 |
| 18 | P3: thread charts, node reshaping, bottom join, batch convert | ✓ 2026-10-29 |
| 19 | Bugs: cut-out colour merge, rose gaps and flat leaves, Start over old result, white parts, colour change unticks approval | ✓ 2026-10-29 |
| 20 | Bugs: edge-speck choices, stuck image editor, big script satin gaps, Chrome freezing | ✓ 2026-10-29 |
| 21 | Gaps from 16–18: wand overlap, auto trace limit, File outline rows, recognition on real-world structure, photo stitch threads, Colours panel chart | ✓ 2026-10-29 |
| 22 | Coverage: satin joins widened over bare fabric, gap columns on picture satin, bare-patch check for lettering (reported, not blocking); small text keeps gaps wider than 0.4 mm; Compare stitches without the stale typing preview | ✓ 2026-10-29 |
| 23 | Round 3, AI messages: see "Session 23 notes" below | ✓ 2026-10-30: requests up to 1000 characters, warned past that; Claude's notes, plan and summary cut at a sentence end; 3D review note worded from the export result (checks passed / download blocked); colour art with black outlines no longer called an ink drawing; the plan lists only the colours sewn; source picture untinted in Compare and Review; the result names who chose the settings (Claude and its model, or the built-in rules) |
| 24 | Round 4, export proof: see "Session 24 notes" below | ✓ 2026-10-30: written DST and PES read back after every generation and measured against the design (size, stitches over empty fabric, bare parts of filled areas, real fill row spacing), sewn size against canvas and asked size said when they differ; area satin kept inside thin outlines (a copy of the flaming basketball now passes the file check; the original picture was not available); block-font bare corners stay reported (corner wedges too narrow to tie off; needs square column ends) |
| 25 | Easy Digitize for me: tap choices (what it goes on, size, look) instead of a blank box; a plain brief of what will be made, shown before Start; example wishes to tap | ✓ 2026-10-30: three taps (what it goes on: 7 garments or not sure, sets the fabric preset; size small 70 / medium 100 / large 200 mm wide; look simple / balanced / detailed, with dark outline and 3D puff chips) replace the blank box and the Detail slider; typed words win over a tap; a "What you will get" line read from the picture updates with each tap (rules, no Claude cost); the box moved under "Anything else?" with four example wishes |
| 26 | Change it by typing or speaking: a prompt box with a microphone before Start and under every result; Needler says what it understood and shows it (background to leave out as a checkerboard) before anything is made, then makes only that change | ✓ 2026-10-30: "Change it" under a result with ready-made changes, a round send button and Speak; "Here is what I will change" in plain sentences with Do it / Not that; "remove the white background, keep only the ball on fire" leaves out the white touching the edge and keeps white inside the subject; later changes win over earlier words and taps, the rest is kept; "bigger" / "smaller" scale the last sewn width; anything the rules do not cover goes to Claude when it is on. Panel checked in a hidden browser on a test picture |
| 27 | Digitize for me never shows a broken result: a part one pixel wide that cannot sew is painted over and the run retried, not failed 4 times | ✓ 2026-10-30: the automatic paint missed a one-pixel speck at odd x and y (brush centre rounded to the even pixel); it now covers the part's exact pixels with the sewn colour around it (a lone dot is left out), the result says what was cleaned, and a part that still cannot sew is named by colour, size and place in plain words |
| 28 | Pick from 2–3 versions (cleaner, balanced, more detail); the pick guides the next try (costs 2–3× Claude credit with Claude on) || ✓ 2026-10-30: "Show me 3 versions to pick from" (on with the built-in rules; off and priced at about 3× when Claude is on) makes Cleaner, Balanced and More detail one after another with the same attempts and file checks (plan's look over the run's own settings); each shows a small stitch picture with size, stitches, colours and cuts; a version that fails the checks is named and not offered, one that sews the same stitches as another is shown once; a click keeps a version (made again, about a second from the engine cache), and its look wins for later changes. Panel checked in a hidden browser on a test badge |
| 29 | Open from 24: block-font square column ends, then the bare-patch check blocks; export read-back for lettering and photo stitch | part 1 ✓ 2026-10-30: satin follows the outline at square corners, inner corners and ends (letters with bare parts at 20 mm: Anton 26 → 10, Bungee 45 → 11, Sniglet 41 → 18; most fonts clean at 4–8 mm); a changed column is kept only when no new stitch line leaves the letter. Still open: diagonal strokes (M, V, W, Z) and split-satin numerals at 20 mm, so the check still reports; export read-back for lettering and photo stitch |

### Session 23 notes (AI messages; found testing a flaming basketball, 2026-10-29)
- The request is cut at 300 characters with no warning: `static/auto-digitize.js` textarea `maxlength="300"` and `auto_digitize.py` `request_text[:300]`. Raise the limit and warn the person when it is still too long.
- Claude's explanations end mid-sentence: `auto_claude.py` cuts plan items to 80 characters (`[:80]`, the plan loop) and notes and errors to 240. Cut at a sentence end, or let the schema limit the length instead.
- `static/auto-digitize.js` (3D review note) always says the marked places "passed the file checks", even when the download is blocked. Word it from the real export result: preview ready / look at these places / file checks passed / download blocked.
- `auto_digitize.classify` calls a colour picture with black outlines on white an ink drawing: the ink test checks bright and dark pixels but not how colourful the rest is. Add a colourful-pixels limit.
- The final explanation listed the planned 5 colours while 4 were sewn: report the colours actually sewn.
- Show the source picture without the green selection tint when comparing colours; name the AI provider in use.

### Session 24 notes (export proof)
- Read the written DST and PES back from disk and check those stitches against the design's shapes (coverage, crossings, size), not only the preview.
- Compare the requested sewn size with the actual sewn size and say so when they differ.
- Re-check the basketball crossing (5 stitches over empty fabric, first at command 2246, x 14.2 mm, y −27.8 mm).
- Fine spaces between fill rows: measure real row spacing in the stitches, apart from the preview's thread width and lighting.
- Open from session 22: block fonts (anton, bungee, alfa_slab_one, bowlby_one, sniglet) still show bare square corners, so the bare-patch check only reports; decide whether to fix them and then make it block. A 0.46 mm wedge in Damion "m" at 15.8 mm may stay bare (no room for its ties).

### Session 25 notes (easy Digitize for me; asked 2026-10-30)
- Goal: someone who has never digitized and cannot write a good request gets the same result as an expert. Needler reads the picture first; the person answers a few taps; the text box is optional.
- Taps: what it goes on (sets the fabric preset: underlay, density, pull), size (small, medium, large), look (simple, balanced, detailed) and two extras (dark outline, 3D puff).
- The brief: one plain line built from the picture and the taps ("A logo, 4 colours, background left out, about 90 mm wide, for a T-shirt"), updated as the taps change, sent to Claude with the request. Built by rules, so it costs no Claude credit.
- Example wishes add a sentence to the box with one tap.

Sessions after 12 are estimates; if a row runs long, it moves to the next session and the rows below shift.

## Build order

1. **P1 engine — done 2026-10-24.** Satin auto split with staggered holes; satin spacing by column width; underlay chosen by width; underlay chosen by letter height; percentage pull compensation; closest join between same-colour areas; fabric settings reaching lettering.
2. **P2 stitch types — done 2026-10-24 (mitre/cap corners still open).** Backstitch, stemstitch, blanket, zigzag outline, step fill, radial fill, gradient fill, smart corners.
3. **P2 digitizing and layout.** Lettering arcs, spacing, joins and letter order done 2026-10-24; wide letters as split satin 2026-10-25. Next: auto-digitize colour roles, outlines and details slider; appliqué; holes; mirror, rotate, align.
4. **P3.** Everything else above, as separate rounds.
