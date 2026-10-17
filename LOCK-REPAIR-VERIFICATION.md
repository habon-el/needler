# End-lock repair — 9 October 2026

Exact design: prepared_9e89ead6d98a18fccc4a0f9c.
Before: HTTP 422, 16 short stitches. After: HTTP 200, attachment design.dst,
28,226 bytes. Both written PES and DST pass the unchanged release checks and
decode to 87 trims each. Fifteen end locks rebuilt; no design resizing.
Largest finishing-endpoint change: 0.4243 mm (not a claim about every lock needle
point's displacement). Original generated files: /tmp/before-lock-fix-_4pnu1fi/output.

The repair only handles our explicitly configured four-point end-lock style.
It retraces a contained segment, or retains the original finishing location if
moving it would exceed 0.45 mm. It preserves four lock penetrations and the trim.
A coincident penetration can remain; no zero-length thread span is invented.
Candidates are applied only when the complete existing release inspection passes.
Cache policy includes the new repair module so old unrepaired plans are not reused.

Scope: this exact download is now verified. This does not certify all earlier
designs, cap fit, physical locking performance, or unresolved crossing cases.
Physical sew-out is pending. Existing dimensions were preserved, not certified
for a particular hat. Regression tests cover both machine formats, repeat repair
stability and rejection of locks across empty areas.
