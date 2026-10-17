# Remaining short-span decision — 7 October 2026

Read-only inspection of the decoded PES files in
`/tmp/output-safety-final-kxl_b3ul` confirms remaining consecutive-STITCH
short spans: circles 13, HELLO normal 413, Tatami 39.

Concrete Tatami example, zero-based command 75 (coordinates in 0.1 mm):
`[-5,-95] -> [-20,-95] -> [-20,-93] -> [2,-93]`.
The middle leg is a 0.20 mm fill-row connector. It is a genuine corner,
not a redundant collinear point. Circles command 51 similarly joins
`[30,0] -> [50,0] -> [50,2] -> [37,2]`.

`stitch_spacing.repair` deliberately preserves these turns. Removing a
corner creates a diagonal and changes local coverage; changing row spacing
changes density; adding detours adds thread. None is an exact-path repair.
This observation explains these examples, not every remaining short span.

Recommended next scope: an explicit preview-and-approve local connector
repair, retaining original paths for Undo, measuring path deviations, checking
source-mask containment and showing changed coverage before approval.
Do not automatically apply shape changes or relax the 0.3–7 mm gate.
Request user direction on this additional editing workflow before implementing.

No application code or customer designs changed in this investigation.
Latest full-suite evidence remains 305 passing; not rerun for this report.
Other launch audits remain open; pausing this ordered geometry-first continuation
does not mean the entire project is externally blocked or complete.
