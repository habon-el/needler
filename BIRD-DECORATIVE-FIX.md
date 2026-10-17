# Bird stitch-generation correction — 7 October 2026

User case: bird-raised-satin-trial-20260923.jpg. Its saved settings actually assign Embossed to 11 regions, not foam puff. Reproduced self-intersection/ring-self-intersection failures in all 11 contours. The screenshot's white error panel also inherited light text from the dark theme.

Fix: decorative clipping decomposes touching pixel-contour linework into valid polygon components, preserving all polygonal components rather than choosing the largest or using buffer(0). The subject mask, colours, original base-fill paths and saved assignments are unchanged. Embossed is a base fill plus texture: if no repeat fits, keep the base and report a stitch-style notice before generation and in Design health. Pure Motif/Cross still refuse when no stitchable pattern fits; no silent switch to another style. Empty SVG texture paths are not emitted.

The existing error/confirmation surfaces and health text now consume workspace theme tokens. Repeated identical style notices are grouped with their count. No new state owner, dialog, palette or redesign.

Verification:

- Two new tests failed before the fix and pass after (touching lobes; tiny Embossed base retention).
- Full suite: 299 passed in 41.05 seconds; JavaScript syntax and diff whitespace checks passed.
- Real generation of a temporary bird copy: 12,106 stitches; no contour error.
- Actual application POST: HTTP 200, 12,106 stitches, 10 texture-size notices; saved settings remain byte-identical. This was a generation request, not a change to the user's selection or colours.
- Real Chromium on the running app: saved plan restores, error panel hidden, Play advances; screenshot outputs/bird-repaired-preview.png.
- Isolated browser suites pass editing/Undo, loading/error/retry, playback, keyboard/native select and 390px reflow. Error and confirmation text exceed 4.5:1 contrast in light and dark themes.
- Strict static audit: 78 pre-existing findings, unchanged; not claimed clean. Browser automation through the desktop surface was unavailable due to its sandbox; independent Chromium checks were used.

This fixes preview generation, not all output-safety blockers or physical sewability. No foam-puff capability is claimed. The software-GPU browser used the honest line-renderer fallback, not a certified realistic thread render. The release gate is unchanged.
