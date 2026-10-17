# Knockout machine-grid correction — 7 October 2026

Reproduced original HELLO knockout: engine.py:147 rejected PES readback as a removed-area crossing. The floating-point segment near (-46.447, -1.353) mm was safe before serialization, but its rounded endpoint (-46.4, -1.4) mm made the sewn segment cross the removed mask. Routing had tested floats, while the files stored a 0.1 mm grid.

Correction: knockout_routing.protect quantizes routing coordinates before deciding cuts. Lock retraces are also quantized and checked; impossible locks still fail closed. No mask tolerance was increased and no command-equality guard was removed.

Regression test test_knockout_machine_grid.py failed on the original code, then passed. Existing five knockout routing tests also passed. Full suite at this checkpoint: 293 passed in 47.00 seconds.

Original audit fixture run: /tmp/output-safety-final-nst9hwe1/results.json. All 18 previously produced machine files remain byte-identical to OUTPUT-SAFETY-RESULTS.json. HELLO knockout now produces a new PES/DST pair with removed-area verification passing. Warm/cold circles remain byte-identical in both formats. This is not export approval: HELLO still contains a 0.20 mm segment and the unmodified 0.3–7 mm release policy refuses it. Normal circles/Tatami retain their existing short-segment refusals. Real-machine testing remains pending.
