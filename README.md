# Needler

An experimental AI-assisted embroidery digitizer, developed locally under the
application/package name **Embroiderly**. This repository is named **needler**;
the existing Python package and application commands are unchanged.

## What is included

- Artwork preparation, subject selection and colour editing (PNG, JPG, BMP,
  WebP and SVG vector logos).
- Needler's own stitch engine (no external embroidery program): tatami fill
  with underlay and edge-following travel, contour, spiral ripple, meander
  stipple, motif, cross stitch, satin columns with underlays and pull
  compensation, running and bean stitch, path-following lock stitches, trims
  and colour changes.
- Satin embroidery fonts generated automatically from bundled open-licence
  TrueType fonts (DejaVu, Lato), with kerning, multi-line layout and alignment.
- Stitch preview/playback and thread suggestions from built-in Brother, Janome,
  Husqvarna Viking and Pfaff thread charts.
- Optional AI-assisted proposals and review, with explicit approval and budgets.
- Machine files checked by one release gate: DST, PES, JEF, EXP, XXX, U01 and
  PEC. Every format is read back and re-checked before download.

## Run it

Requires Python 3.11 or newer. Works on Windows, macOS and Linux.

- **Windows:** double-click `start-needler.bat`.
- **macOS / Linux:** run `sh start-needler.sh`.

The first start creates a private Python environment (`.venv`) and installs the
dependencies; later starts are immediate. Then open http://127.0.0.1:5050.
This is a local development server, not a production hosting service.

Manual start from the project folder:

```sh
python -m venv .venv && .venv/bin/python -m pip install -e ".[dev]"   # Windows: .venv\Scripts\python
PYTHONPATH=src .venv/bin/python -X utf8 -m embroiderly.web
```

SAM2 model weights and the AI provider key are optional and not bundled; see
`SAM2-LOCAL.md`. Without them the AI features are switched off and everything
else works.

## Tests

```sh
PYTHONPATH=src .venv/bin/python -X utf8 -m pytest -q
```

## Status and limitations

This is work in progress. Small text, fine artwork details and some stitch
generation cases still require investigation. A preview or successful file check
does not guarantee a safe or accurate physical sew-out. Review the design and
test it with the intended machine, fabric, needle and thread.

See `UX-CONTRACT.md` for current verification evidence and known gaps. Historical
checkpoint reports describe their own dates, not a guarantee of current support.

## Publication and privacy

The initial public commit is a clean snapshot of project code, tests, documentation
and application assets. Older development history remains local. Customer uploads,
API keys, generated output, downloaded models and installed dependencies are
excluded. Keep credentials in local environment variables, never in commits.

Optional AI actions can send artwork to the configured provider after consent.
Never put a provider key in browser JavaScript or share it in an issue.

Third-party dependencies and separately installed assets retain their own
licensing terms; they are not relicensed by this repository. Bundled fonts:
DejaVu (Bitstream Vera / DejaVu licence) and Lato (SIL Open Font License 1.1),
with licence texts in `src/embroiderly/fonts/*/LICENSE`. Machine-file reading
and writing uses pyembroidery (MIT).
