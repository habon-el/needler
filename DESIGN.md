---
version: alpha
name: Embroiderly workbench
description: A canvas-first embroidery workbench with a quiet tool rail and task-based properties.
colors:
  primary: "#126957"
  ink: "#243538"
  muted: "#596a6d"
  surface: "#ffffff"
  background: "#edf1f2"
  danger: "#a53545"
typography:
  sans:
    fontFamily: "system-ui, sans-serif"
  display:
    fontFamily: "Trebuchet MS, system-ui, sans-serif"
  mono:
    fontFamily: "ui-monospace, monospace"
rounded:
  DEFAULT: "0.5rem"
spacing:
  unit: "0.5rem"
components:
  button:
    rounded: "0.5rem"
---

# Embroiderly design system

## Overview

A worktable for people preparing a first embroidery design, not a dashboard of engine internals.
English product UI; no market-specific claims. Desktop-first precision editing with a reflowing narrow layout.
The signature is the unobstructed artwork on a neutral cutting-mat-like canvas, surrounded by restrained tools.
Avoid marketing cards, decorative counters, unexplained glyphs and simultaneous walls of open instructions.

Runtime ownership: `src/embroiderly/static/workspace-ui.css` is canonical for the migrated artwork workspace.
This document mirrors its accepted values (model B). Existing routes remain on their styles until migrated.

## Colors

The six frontmatter colors map in order to `--ui-primary`, `--ui-ink`, `--ui-muted`, `--ui-surface`,
`--ui-background`, `--ui-danger`. Buttons, fields, task navigation and help consume these variables.
Selection teal is distinct from the red erase draft. Labels accompany both; color alone never commits anything.
Light and dark artwork-workspace themes; forced colors defer to platform colors.
settings.css is the canonical dark adapter for the same --ui-* tokens, not a second palette owner.
SettingsService owns persisted appearance choices. Match my computer follows live OS changes.
Legacy routes still await theme migration; this is not yet a whole-application theme guarantee.

## Typography

System sans: 14px body, 12px control captions, 1.5 body line height.
Trebuchet/system: restrained wordmark, 21px, 700 weight. No web-font dependency.
Monospace: zoom percentage and machine position. No headline typography competing with artwork.

## Layout

Existing editor shell: top actions, tool rail, collapsible Pieces list, central canvas, right properties and lower playback.
piece-panel.css extends canonical workspace tokens; it does not own another palette. Simple and Advanced
share property fields. Narrow screens place Pieces and properties beneath the canvas.
One topic of properties is visible at a time. Topic changes never change design values.
The UI-only workflow adapter shows Edit, Check stitches, then Save and download across the top.
Essential fields remain in the right inspector. A full-width AI assistant button precedes a
three-column toolbox: Background, New text, Colours, Stitch styles, Borders and Review details.
Icons retain short visible labels. Width/height and approval remain below these tools.
Only fabric/lighting, fine-tuning and longer explanations stay in Expert settings.
Native font settings that do not exist are not simulated with dummy inputs.
The canvas owns remaining desktop height; the inspector independently scrolls. Below 900px the inspector
follows the canvas in document flow. All topic choices and advanced controls remain reachable.
Studio layout (`studio-layout.css/js`, 2026-10-19, modelled on desktop digitizers such as Hatch):
one 52px top bar (brand · steps · actions) and one bottom status bar (status, thread order, stitch
total, size). The canvas column does not scroll; the canvas takes the remaining height. Pieces and
properties are docks: both collapse from toggles at the end of the view bar, properties resize from a
splitter (260–560px, arrow keys, double-click resets), and Focus (F) hides both. Pieces starts collapsed
below 1500px wide. Dock choices are per-browser conveniences in localStorage.
3D view (`thread-3d.js/css`): a "3D view" button beside Compare opens an orbit view over the canvas.
Each sewn stitch from the exported playback is an oval thread tube; a cell grid counts threads that
already passed, so crossings stack (with compression) while side-by-side satin and fill rows stay
flat. Jumps are dashed arcs, cuts are red dots, the needle marks the playback cursor (shared player).
Stitch review lists long stitches (>8 mm), thick spots (7+ layers on 2+ stitches) and repeated passes
(minor); clicking one flies the camera there and seeks playback. Appearance only: no machine-file change.
Digitize for me (`auto_digitize.py`, `auto-digitize.js/css`): a primary button above the AI assistant.
Rules only, no model: classify the picture (line art / ink / flat logo / photo), parse an optional
request (size, colours, kind), choose settings, then up to 4 attempts through the same /artwork route
as the buttons (approval, cleanup decisions, engine, release gate unchanged). Retries: merge small
details / smooth / fewer colours for logos; longer line-art retrace for cuts; rescale until the sewn
(not canvas) size matches the request. The best attempt is restored and saved; the person reviews in
3D and downloads. Steps stream live; the job report persists as `<name>.auto.json`.
"Let Claude decide" (`auto_claude.py`, optional `ai` extra): shown only when ANTHROPIC_API_KEY is set and
the SDK is installed. Claude Opus 5.5 sees the picture, calls `make_stitches` (same attempt path; result
numbers plus a drawing of the stitches come back) and `finish` (attempt to keep, summary, checks), at
most 5 attempts. Spend is capped per design ($0.40) and in total ($4.50, `claude-spend.json`), both
overridable by env. Any Claude failure falls back to the rules. The key is never stored or logged.
Fixed 2026-10-20 after a skeleton-samurai screenshot came out as loose outlines: (1) details the fill
converter cannot sew (hatching one pixel wide) blocked every colour attempt; each attempt now marks
exactly the cleanup items overlapping those blockers as `drop` and retries; (2) "keep the background"
(`keep_background`) forces colour mode, because line modes leave it as bare fabric; (3) Claude's
`make_stitches` takes `erase` boxes (fractions of the picture) that become ordinary erase edits, for
screenshot buttons, page dots and watermarks; (4) `area_columns` repairs self-touching outlines
instead of crashing with a GEOS TopologyException; (5) "keep the background" also clears a saved
subject cut-out (`selection` → full, `rect` dropped), in the rules and through Claude's `keep_background`;
(6) with the whole picture stitched, Claude's erase boxes are painted with the commonest colour on their
edge instead of cutting a bare hole; (7) unsewable specks that are not cleanup items get a paint edit
in the colour around them; (8) `classify` only calls dark pictures line art when they have no strongly
coloured areas (`colourful` < 3 %); (9) `satin_font._order` uses prepared shapes, an STRtree and one start
above 12 columns: hatching areas with 100+ columns took minutes per area (letters keep the exact search).
Mixed mode (`detail_lines.py`, option `line_details` off/light/all): thin lines the fills lose are found
in the original picture (top-hat / black-hat), given the nearest palette thread, and traced with the
line-art router as running stitches over the fills; Claude's `make_stitches` takes `line_details`, and
the rules turn on `light` for colour art on dark backgrounds.
Auto Fabric (2026-10-20, after Hatch's Auto Fabric): `fabric_preset` from `knowledge/generation.json`
(10 fabrics; Wilcom-guided starting values, not sew-out verified) sets fill density, satin pull, fill
underlay, fill stitch length and tie-off size; a Fabric menu under the size fields shows the stabilizer;
requests ("polo", "cap", "t-shirt"...) and Claude's `fabric` choose it.
Fill shaping (`fill_shaping.py`, 2026-10-20): plain tatami areas reach 0.35 mm under the colours sewn
after them (never into empty fabric or earlier colours), so pull-in leaves no gaps between colours; and
rows run along each area's long side (45 degrees for round or square areas). Region-style identities still
come from the unshaped contours.
Branching (`stitch_engine._branch`, metadata `branching`, on by default): between same-colour fill parts the
needle travels inside the part just sewn or under areas sewn later instead of cutting; it never crosses
fabric or areas already sewn. Claude's tools (2026-10-20): `merge_colours` (fold a scattered colour into
another; merges match the nearest palette colour), `border` (satin/running outline), `per_colour` cut
counts in each result, and `recent_sewouts` from the sew-out review history in its brief. On the samurai,
Claude folded scattered colours and cut the thread cuts from 568 to 322.
One-colour photo lines (`photo_lines.py`, option `photo_style: one_colour`, after Hatch's PhotoFlash): the
original photo's tone (CLAHE, 2-98 % stretch) sets the width of a zigzag in rows 1 mm apart (0.6-2 mm,
any angle, light-thread-on-dark inversion); rows snake into one continuous thread with tie-offs, so a
rectangular photo has no cuts. "Digitize for me" now sends photos here (before: 6-colour logo mode);
Claude's `mode: photo_lines` and `photo` settings; a "One-colour photo" box under the size fields.
Problems panel (`problems.py`, `problems-panel.js`, GET /api/problems/<prepared>): on Check stitches, only
when something is wrong: one plain line per problem (nearby findings grouped), Show (zooms the 2D views to
about 12 mm around it) and Fix (a paint edit with the surrounding colour, or an erase when the spot is
mostly bare; "Many thread cuts" merges small details), plus Fix all. Fixes go through acceptRefinement,
so stitches are rebuilt and re-checked; no AI. Kept deliberately minimal: no coordinates or codes.
Check stitches is otherwise clean: the panel sits under the heading and says "All checks passed" when there
is nothing to fix (or "Stitches need to be made again" when the checks cannot run); Design health shows only
when details cannot be stitched at all; route statistics live in the closed "Directions & jumps" section;
the "Check picture details" button is gone (the cleanup flow still opens that review when needed).
Edit panel (clean): size fields, ±10% and "About this size" stay together; below one divider, the design
options: Fabric (short stabilizer hint, full advice on hover), then "One-colour photo" and "3D puff" as
one-line switches whose settings and one-line note appear only when switched on (fabric-controls.js
groups them into `.design-options`).
Open (from the Hatch comparison): branching / travel under later fills instead of a cut after every
shape (`generation_policy` still forces `trim_after`), turning fills that follow the shape, colour
blending, appliqué, stitch shortening on tight curves, more fonts.
Spacing uses the 0.5rem unit. Section padding 2 units; controls at least 32px high.

## Elevation & Depth

Flat white panels, soft-grey workspace, thin borders. No floating decorative cards or blur.
Status messages retain a stable position. Canvas content does not shrink to fit paragraphs.

## Shapes

0.5rem control radius. SVG line icons: 24-unit viewBox, 1.7-unit rounded strokes, no emoji.

## Components

Buttons have visible labels, hover, focus-visible rings, selected borders and actual disabled states.
Native selects are intentional; OS popup geometry and keyboard behavior are accepted.
Native details expose secondary explanations. Critical errors and experimental limitations remain visible.
The canvas result banner distinguishes artwork, generation, completed playback and blockers using
text as well as color. preparation.js owns its state; workflow.js only presents it. Compare in
Check uses actual stitch paths, while Compare in Edit uses prepared artwork. Saved matching
plans reopen at Check; automatic artwork suggestions cannot replace a completed result.
Tool labels remain beside/below icons. A topic navigator owns only disclosure state, never artwork settings.
No animated entrance; reduced-motion disables optional transitions. Root scrollbars are tokenized.

## Do's and Don'ts

- Do keep the selected subject and machine playback in the same canvas region.
- Do distinguish model-assisted background hints from exact erase edits.
- Do preview an outlined erasure before explicit apply; preserve Undo and original uploads.
- Don't imply professional sewability from a rendered preview.
- Don't claim all legacy routes have been consolidated in this incremental slice.
