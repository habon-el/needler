# Direct small-text foundation — 13 October 2026

Local checkpoint 960d53a saved prior work. Git status was clean afterward; no
GitHub remote, network push or new font downloads were used.

small_lettering.py calls the installed engine's batch-lettering entry point with
existing digitized fonts, keeps multiline input in one SVG, trims per glyph and
rejects unsupported glyphs rather than substituting spaces. It does not call
image tracing, palette quantization, area cleanup or thin-line conversion.
Font licences stay in the installed font directories. This backend is not yet
connected to Tools → Text and does not expose an approved machine-file download.

## Readback results

Installed Ink/Stitch Small Font; nominal font heights, not yet measured capital
heights. Measurements are identical in PES and DST. Values below are stitch
length tests only: holes, visible travel, density and mark counts are not certified.

| Text | Nominal mm | Short stitches | Minimum mm | Maximum mm |
|---|---:|---:|---:|---:|
| Hello World | 4 | 1 | 0.224 | 2.200 |
| Hello World | 5 | 0 | 0.300 | 2.500 |
| Hello World | 6 | 0 | 0.400 | 2.500 |
| tiny | 4 | 0 | 0.300 | 2.102 |
| tiny | 5 | 0 | 0.300 | 2.470 |
| tiny | 6 | 0 | 0.300 | 2.200 |

The initial unrounded 4 mm test passed, but file readback caught the short segment.
This is why the backend returns release_approved=False. Below 4 mm is not enabled.
The installed fonts' documented nominal size is not misrepresented as exact cap
height. Physical sew-out is pending.

## Confirmed blockers in the old picture route (inventory incomplete)

- lettering.py:85: entire text-block height restricted to 10–350 mm.
- lettering.py creation: raster output limited to 768 px in its larger dimension.
- preparation.py:22: input thumbnail limited to 768 × 768 px.
- preparation.py:133–136: default 1 mm² area/hole cleanup and minimum 10 mm height.
- preparation.py:214: design height limited to 10–400 mm.
- preparation.py:242–306: smoothing, simplification and area threshold can alter shapes.
- release_gate.py:21: 0.3 mm minimum remains active; it must not be bypassed.

Remaining: complete blocker inventory; real capital-height measurement; integrate
the vector source into Text without raster digitization; fit UI; safe 4 mm repair;
the verse at 100/110 mm; density/mark/travel checks and user-approved exceptions.
No claim that the requested small-text feature is finished or generally usable.
