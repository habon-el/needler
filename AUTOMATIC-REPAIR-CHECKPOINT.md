# Automatic repair checkpoint — NOT complete

Production engine.py now applies an explicit 0.45 mm minimum, the knowledge-table
twill row spacing (0.4 mm; previous implicit 0.25 recorded), collapse distance zero,
component cuts, and four-point custom retracing locks at 0.6 mm. Original images
are unchanged. The old generated files are in /tmp/pre-auto-repair-fzpx83l2/output.
Fabric rendering textures are not assumed to be sewing presets. Only twill is
defined. Existing decorative spacing remains explicit rather than overwritten.

The rule pipeline is connected to generated PES readback before final publication.
It protects command boundaries and the positional lock windows, proposes bounded
point deletion, and only writes automatic candidates with zero inspected issues.
Unresolved candidates are stored in repair-proposal.json, not automatically applied.
No corner/lock exceptions to the export checks were added.

The shared release gate now returns all path findings and their coordinates for
the first failing format. It still validates both files on success and requires
trim parity. Cross-format combined error reporting is not yet implemented.

## Exact named design, real production directory

prepared_eb53b7a9f4ff3d83fd7ce53d, 32 mm:

| Measure | Original | Current |
|---|---:|---:|
| Short consecutive sewn spans | 1,084 | 26 |
| Sewn spans crossing excluded pixels | 173 | 88 |
| STITCH commands | 7,518 | 4,451 |
| TRIM commands in PES and DST | not recounted | 108 each |

The candidate is NOT automatically approved. Current generated output includes
24 needle penetrations inside excluded pixels. Dropping short points or cutting
between components does not repair those needle positions. The exact DST route
remains blocked; this checkpoint does not satisfy the requested acceptance test.

Three production calls produced identical bytes: first regeneration 4.063 seconds,
then cache hits 0.175 and 0.137 seconds. This is mixed cold/warm repeatability,
not three independent cold generations. Original runtime was not recorded.

| File | Before SHA-256 | Current SHA-256 |
|---|---|---|
| design.pes | 66d0f2fcc21e0f807f75668bad779baa8d08ccc666db20e4903185f59a21cb01 | 1a8e47b650e0acaa518e1e1cb3b4ea19c6d783dd2c5a6fbe94018421578ced88 |
| design.dst | c37324076863b6f3fbcc4c340bc14a33d885efa6724bf36b4c5e3a56f887d73d | 07488c339b53ae35753311bf0fa97a8e360e6c74232bcb2c5003bd7c89f17c08 |

Changes are intentional source spacing, minimum-length filtering, locks and cuts.
No unsafe output was blessed as a new export fixture baseline.

## Verification

324 tests passed. Existing piece-resize test now expects 0.4 mm spacing before and
after resize, reflecting the approved preset change, not a weaker safety limit.
The new aggregate-report regression was executed against the previous HEAD gate:
it fails there because only one error is available. New generation-policy and
lock-preservation tests pass; they were not separately run against the old tree.

## Work still required

- Containment-aware routing and unsafe needle-placement exceptions.
- Reliable lock regeneration for the remaining short lock segments.
- Before/after exception UI and Apply/Keep actions, plus Show me locations.
- Future-covered travel optimization; currently cuts are conservative, not the
  requested nearest-point/future-colour classification.
- Big thanks, HELLO WORLD and Baby 0689 release evidence, overlays, approved
  fixture hashes and three independent cold-generation checks.
- Object/stitch-role tracking and per-object 5% rule (follow-ups).
- Physical sew-out: pending.
