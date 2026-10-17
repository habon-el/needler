# Export origin correction — 8 October 2026

Reproduced prepared_c2e4e9501c414699c7ee2111: PES command 1 and DST
command 2 reported a removed-area penetration at (22.50, 3.40) mm.
engine.py inferred origin from source bounds; the generator defaults to the
generated stitch-plan bounds instead. They are not interchangeable. This case
shifted by approximately 0.97 mm in X before machine-grid rounding.

Generator contract inspected (reference only, no copied implementation):
https://github.com/inkstitch/inkstitch/blob/main/lib/output.py
https://github.com/inkstitch/inkstitch/blob/main/lib/commands.py
Actual behavior tested against installed v3.2.2.

The SVG now explicitly declares the origin used by mask checks and playback.
Transformed pieces use their local mask origin before the existing translation.
Recolour matching compares the document origin exactly. Engine integration hash
and SVG geometry invalidate prior caches. This changes machine placement where
the old assumed and actual origins differed; it does not scale stitch paths.

The exact case was regenerated in temporary storage: its first stitch now maps
correctly at (21.60, 3.40) mm. Export remains correctly blocked at command 3 by
a 0.10 mm stitch, below the existing 0.3 mm policy. The design is 10 mm tall.
No guarantee that enlargement alone fixes all issues. No automatic resizing,
corner cutting, removed-area allowance increase or safety-gate bypass was made.

Regression test demonstrates the old implicit centering and verifies the new
explicit source frame with the real installed generator. Another test prevents
recolour reuse across different origins. Physical sew-out remains untested.
