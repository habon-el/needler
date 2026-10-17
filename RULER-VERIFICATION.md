# Ruler and resize discovery — 7 October 2026

## Drag extension

Ruler now uses a dotted line. Drag on empty artwork to create A/B, drag either endpoint to adjust, or drag the line to translate both endpoints. Screen-space hit targets remain consistent at different zoom levels. Translation clamps both endpoints together at image edges, preserving length. Distance updates during movement. Escape, pointer cancellation and window blur restore the pre-drag measurement; no design data is changed.

The native Adjust with arrows selector provides New point / Point A / Point B / Whole ruler keyboard targets. Browser regressions cover drag creation (20 mm), B adjustment (30 mm), A adjustment (20 mm), whole-line movement with unchanged length, Escape rollback, and a 0.2 mm keyboard endpoint adjustment. Existing ruler and isolated workspace suites passed. Full suite: 305 passed in 48.46 seconds. Static audit retains 78 existing findings. Screenshots show the dotted line and retained workspace styling. Physical touch-device testing was not performed.

Existing global size owner: preparation options `height_mm`, edited only in
Edit design → Size & fabric → Canvas height (mm). It scales the source canvas
proportionally, including its empty margins; it is not subject bounding height.
Existing piece sizes remain in the Pieces properties editor. No duplicate size
fields or machine-generation capability were added.

Added Tools → Ruler, a read-only two-click A/B line across Original, Subject,
Thread plan, Stitches and comparison canvases. Distance is image-space Euclidean
length times configured canvas height / source pixel height, independent of zoom
and pan. Settings units apply to the readout. It represents planned dimensions,
not measured fabric shrinkage. The white/ink double stroke stays visible against
light and dark artwork; all toolbar styling uses the existing workspace owner.
Measurements are transient and never enter options, history or exports.

Arrow keys move a cursor by one source pixel (Shift: ten); Enter sets an endpoint;
Escape or Clear measurement clears it. A third point starts another measurement.
Edit size reveals and focuses the existing canvas-height field. Guidance explains
proportional shrinking, re-approval and stitch regeneration. Piece selection does
not intercept ruler clicks. Space/middle-drag retains existing navigation.

Verification:
- `tests/browser_ruler.py`: real Chromium on disposable artwork; horizontal and
  diagonal 20 mm, zoom and pan invariance, 0.787 inch conversion, three canvases,
  keyboard and Escape, exact options unchanged by measurement, height 100→50
  yields ruler 20→10 mm, old playback invalidated, Undo restores 20 mm.
- Existing isolated workspace suites pass editing/Undo, error and timeout/retry,
  real saved stitch playback, keyboard, narrow view and light/dark error contrast.
- Full pytest suite: 305 passed in 50.08 seconds. Changed JS syntax checks pass.
- Static premium audit: 78 existing findings; not a whole-app compliance claim.
- Desktop and 390px screenshots: outputs/ruler-desktop.png, ruler-mobile.png.
  Visual review caught a shrinking tool hint; flex-shrink is now disabled for it.

No export/generation backend was changed for this feature. Export fixture byte
comparison and physical sew-out were not rerun. Existing short-corner release
blockers and the paused geometry-repair decision are unchanged.
