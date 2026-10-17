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
