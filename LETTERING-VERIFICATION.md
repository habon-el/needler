# Text studio — 8 October 2026

Tools → Text opens a native modal using the existing settings drawer styling.
The installed catalogue has 35 families / 140 styles. Font sources are locally
allowlisted, with package copyright notices available from the tool. No font
binaries or third-party digitizing code were downloaded or bundled.

The dialog owns the draft text, font, height in mm, spacing in em, alignment and
colour. Preview is debounced and stale requests cannot replace newer previews.
Create saves a separate design, SVG outline master and editable lettering recipe;
it does not overwrite the current picture or its preparation settings. Reopening
Text on that design restores the recipe; creating again produces a new version.
Existing preparation controls remain the owner of subsequent embroidery settings.

Verification: 319 pytest tests passed, including 14 lettering cases. JavaScript
syntax passed. Isolated Chromium verified catalogue loading, transparent preview,
invalid text, Escape/focus return, retained drafts, create/reopen, unchanged source
settings and 390px layout. Screenshots are outputs/lettering-desktop.png and
outputs/lettering-mobile.png. The browser test caught and verified a fix to Escape.

Static audit reports 82 findings (78 pre-existing). Four new findings are detector
limitations: three buttons have JS handlers in lettering.js, and the textarea has
resize:none in lettering.css. The whole application is not claimed audit-clean.

Limitations: outline fonts are not pre-digitized embroidery alphabets. The existing
pipeline consumes a transparent raster (maximum 768px) made from the saved vector
master; tiny details still require review. No contextual shaping, kerning, on-canvas
text placement, inch entry or guaranteed sewability. Unsupported contextual scripts
are rejected instead of rendered incorrectly. Symbol fonts may reject ordinary
words when glyphs are unavailable. No physical sew-out was tested. Export safety
gates remain unchanged; this does not bypass thread-securing errors. Existing full
workspace browser suites were not rerun in this pass.
