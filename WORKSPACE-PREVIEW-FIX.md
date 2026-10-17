# Preview navigation and new-upload verification

27 September 2026.

## Cause and correction

The link provided after the colour-knockout fix led to `/engine/<prepared>.png?view=1`.
That GET rendered the old `machine.html` interface. The current frontend had not
been reverted, but the shared link and Advanced playback link exposed the old one.

Prepared engine URLs now redirect to the current `/artwork` workspace with
`?view=stitched`. The prepared-to-original redirect retains that view. Stitches
opens immediately and restores only a plan matching current saved settings.
It does not generate, save, change colours or force an older plan into newer edits.
The existing link is now **View stitches**; ordinary/keyboard clicks stay inside
the current page, preserving unsaved edits. Automatic suggestions cannot interrupt
an explicit stitch-view deep link. No stylesheet, theme or layout was redesigned.

This is a bounded navigation correction. Legacy unprepared-image engine tooling
and POST compatibility still exist; their removal is not claimed.

## Is background removal specific to Big thanks?

No. `colour_knockout.py` and the upload/preparation/assistant flow are shared by
all uploads. There is no production filename or image-specific Big thanks branch.

Four independent synthetic designs, each with three enclosed openings, were sent
through upload → automatic proposal → explicit Apply/Save in isolated app instances:

| New upload | Result |
|---|---|
| Black shapes on white PNG | Background and enclosed white removed; ink retained |
| Dark shapes on off-white JPEG | Near-background colour removed, including holes |
| White shapes on black PNG | Black background removed; white foreground retained |
| Orange shapes on blue PNG | Blue background removed; orange foreground retained |

All four reported 0 mm² of the selected background colour remaining. Their three
enclosed openings stayed transparent and their uploaded source bytes were unchanged.
Proposal alone did not apply or save edits. These are controlled fixtures, not a
claim of testing every possible customer design or photographic background.

All future uploads have the colour-removal tool. Automatic proposals require flat
artwork and a sufficiently dominant border colour. Review and Apply remain required.
Photographs, gradients, ambiguous same-colour subjects/backgrounds, and intentional
white detail still require judgement, selection or tolerance/parts adjustment.
See COLOUR-KNOCKOUT.md for the existing mode and physical-sew-out limitations.

## Verification

- Full pytest suite: **264 passed**.
- New route/upload tests: **6 passed** (`tests/test_workspace_preview_links.py`).
- Real browser: old prepared link redirects to modern workspace; Stitches selected;
  icons and seven topics present; keyboard View stitches remains in the same page;
  options unchanged; Play advances; 390px layout has no horizontal document overflow.
- Screenshot: `outputs/colour-knockout/modern-workspace-preview.png`.
- JavaScript syntax: preparation, workspace and assistance pass.
- Strict static audit: exits 1 with 78 external-handler false positives, traced in
  `outputs/workspace-preview-static-triage.json`; no claim that the strict command passed.
- Existing legacy workspace scripts still depend on a user-trashed fixture; they
  do not provide passing coverage. The fixture was not restored. The dedicated
  browser test above uses a live owned test copy.
- No stitch algorithm or export setting changed in this correction. Physical
  sew-out, real screen-reader interaction and cross-browser certification remain untested.
