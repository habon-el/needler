# Thread-surface renderer — 27 September 2026

Implemented and browser-tested, but **not fully accepted**: the software-GPU speed target is not met and physical sew-out comparisons have not been supplied. This is an appearance estimate, not a prediction of finished embroidery.

## What changed

- The workspace and landing demonstration use the shared WebGL2 renderer. It deposits tapered half-cylinder ridges in exported sew order, adds overlapping heights, retains the topmost direction/colour, and shades finite-difference normals with directional shine, subtle seeded twist/variation, crevice shading and a short fabric shadow.
- Fabric presets are procedural twill, piqué, knit, fleece and cap twill. They are illustrative textures, not measured fabric models.
- The workspace toolbar has one Realistic thread switch, Save PNG mockup, rendering status and conditional Retry. Plain-line inspection remains available. Rendering failure falls back to lines, never to an empty-success screen.
- Size & fabric owns preview width, session weight profiles, texture, neutral light, light angle and opt-in drag lighting. The angle range is the keyboard alternative. Appearance does not change generation settings or machine files.
- A bounded NumPy renderer produces PNG mockups. The compatibility `/finished/` route now uses the same written-file renderer instead of rendering saved plan JSON.
- Height/material buffers, fabric data, palette shading ramps and unchanged shaded frames are cached. Playback adds only newly sewn ridges; rewind clears future ridges. Lighting does not rebuild geometry. No stitches are discarded to claim speed.

The initial 0.375 mm width for 40-weight is **the brief's unverified visual assumption**, not a manufacturer-certified diameter. Weight profiles are session-only and apply one width to all displayed threads. Independent per-colour weight assignments and calibrated catalogue diameters are not provided.

## Machine-file boundary

The existing engine constructs workspace playback by reading its written PES; the renderer consumes those commands. Draft recolouring changes only displayed RGB on those paths until export is updated. PNG generation reads the PES directly, not `engine-plan.json` or playback geometry. Legacy DST needs an explicit ordered palette whose saved SHA-256 matches that exact file. Jumps, trims, colour changes, unknown non-sewing commands and zero-length stitches deposit no ridge. Needle endpoints stay fixed; seeded displacement affects the illustrated fibre only.

Mockups validate dimensions, width, light and fabric, bound file/command size, allow one CPU render at a time, and verify the export hash again before returning. A busy request receives 429; stale DST palette receives 400; an unreadable file receives an error, never a replacement design. Existing Trash protection remains in force.

## Verification against the brief

| Check | Result and limits |
| --- | --- |
| Real satin, tatami and layered sew-outs | **Pending photographs.** No physical resemblance or diagnostic accuracy is established by these tests. Photograph each sample flat, at the preview's scale and lighting, then document differences. |
| Adjacent 0° / 90° fills | Pass: brightness ordering reverses when the light rotates 90°, CPU and WebGL. |
| 1.5× density, same outer extent | Pass: rounded export spacing gives maximum illustrative height 0.1874 → 0.3227 and mean 0.0800 → 0.1180 in the test buffers. Left-edge RGB brightness decreases 0.5318 → 0.5220 under identical light. These are model values, not measured millimetres of a sewn sample. |
| Known gap and 9 mm stitch | Pass: 2 mm intentional gap stays empty and the complete 9 mm segment remains drawn. No display subdivision or gap-filling. Realistic defect PNG plus plain inspection available. |
| Determinism / rewind | Pass: exact repeat images within each rendering path, and rewind matches a fresh render of the same prefix. CPU and WebGL are numerically close, not byte-identical to each other. |
| 30,000 sewn segments, 1440 × 900, 2× samples | **Speed target not met on tested software graphics.** Latest run: median 294.4 ms, p95 360.0 ms, nine measured light-change frames after warm-up. Initial build + transfer + screenshot: 2674 ms. The browser uses ANGLE/SwiftShader, not a physical GPU. Hardware-accelerated validation remains pending. Unchanged cached frames fell below timer resolution; that is not a claim that changing light is instantaneous. |
| Export regression | Pass: all six original PES/DST fixtures byte-identical, and the photographic input hash unchanged. Only `web.py` and the two new preview Python modules differ from the prior module baseline. The baseline is re-recorded and committed separately; unrelated pre-existing source changes remain in the working tree. Digitizing, routing, segmentation and export modules are unchanged by this renderer pass. |
| Neutral palette colour | Pass on seven test colours: displayed fully-thread-covered pixels have CIE76 Delta-E ≤ 1.643 relative to the export RGB palette. Cloth/antialias mixtures are excluded. This is not CIEDE2000, a calibrated display test, or a measurement of physical catalogue thread. CPU tests also stay below 3. |
| CPU/WebGL equivalence | Mean absolute 8-bit RGB error 0.163 across the image, 0.339 on thread; p99 = 1 channel value at the high-resolution surface. GPU uses half-float buffers and a palette LUT; CPU uses float32. Final GPU linear 2× resolve and CPU Lanczos filtering also differ slightly. |

Evidence lives in `outputs/thread-surface/verification.json`, the adjacent PES/PNG fixtures, `workspace-realistic.png`, and `embroiderly-thread-mockup.png`. Test fixture creation uses actual machine files, not hand-authored playback placeholders.

## Regression and UI checks

- `PYTHONPATH=src:work/deps python3 -m pytest -q`: **235 passed**, including 14 new renderer/route cases.
- `tests/browser_thread_surface.py`: exported fixture, angle, colour, determinism, rewind and parity checks pass; speed failure is explicitly recorded, not converted into a pass.
- `tests/browser_surface_workspace.py`: passes on a separately uploaded hello sample (2,843 stitches). Verified live light, pointer drag, keyboard range, native select, one-click lines, session weight validation/restoration, PNG download, duplicate blocking, injected 429 and retry, injected graphics failure and retry, unchanged generation options, and 390 px reflow. Screenshot visually reviewed.
- `tests/browser_landing.py`: passes demo steps, recolouring, actual playback, pause/scrub, reduced motion, keyboard FAQ, narrow layout, error/retry and studio link. No saved customer designs changed.
- Node syntax checks cover workspace, preparation, renderer, lighting controller, shared stitch layer and landing. `git diff --check` passes.
- The older manifest browser scripts depend on user designs now in Trash and return 410 before their intended assertions. **Those legacy runs cannot be counted as passing.** Do not restore customer Trash just to satisfy a fixture. New isolated renderer/workspace coverage does not claim to execute every legacy scenario.
- Strict static audit exits 1 with **73 literal-button findings**. Every finding is source-traced in `outputs/thread-surface-static-triage.json`; external/delegated handlers exist. This is a limitation of its literal-template action detector, not a clean audit exit or a claim that all old workflows were exercised. The new retry handler is exercised in the browser.
- No dedicated automated accessibility/localization suite is configured. English controls, labels, keyboard operation and narrow layout were checked; full screen-reader, real touch-device and cross-browser matrices remain untested.

## Capability gaps / acceptance work still open

1. Real foam puff digitizing (appropriate columns, end caps, perimeter/foam cut strategy) is absent. **No foam height is added.** Existing layered satin can accumulate real commanded layers; it is not represented as foam.
2. Photograph comparison for satin, tatami and layered samples remains pending user-provided sew-outs.
3. Full-window smooth lighting must be tested and, if needed, further optimized on supported hardware. The software-GPU result does not meet a 33.3 ms frame budget.
4. Catalogue-calibrated thread widths, persistent/per-colour weight profiles, physical tension/pull/fabric deformation and calibrated colour matching are not implemented.
5. Legacy browser fixtures should migrate to owned disposable test designs. User Trash is left untouched.

## Research and implementation ownership

Original project code; no third-party embroidery renderer was copied or downloaded. WebGL floating framebuffer support follows the [Khronos extension specification](https://registry.khronos.org/webgl/extensions/EXT_color_buffer_float/). Direction-dependent fibre highlights are informed by the published [NVIDIA hair-rendering course](https://developer.download.nvidia.com/presentations/2010/SIGGRAPH/HairCourse_SIGGRAPH2010.pdf), adapted as a bounded illustrative model rather than a physical validation claim.

The frontend-design skills kept this change within the existing canvas-first shell, runtime tokens and native controls, with a single appearance owner and explicit failure states. No separate workspace, icon library, UI framework or new digitizing workflow was introduced.
