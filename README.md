# Needler

An experimental AI-assisted embroidery digitizer, developed locally under the
application/package name **Embroiderly**. This repository is named **needler**;
the existing Python package and application commands are unchanged.

## What is included

- Artwork preparation, subject selection and colour editing.
- Editable embroidery lettering and stitch preview/playback.
- Optional AI-assisted proposals and review, with explicit approval and budgets.
- DST/PES export checks, regression tests and development documentation.

## Run on the existing development computer

From the project folder:

```sh
PYTHONPATH=src:work/deps python3 -m embroiderly.web
```

Open http://127.0.0.1:5050. This starts a local development server, not a
production hosting service.

Python dependencies are declared in `pyproject.toml`. Installed libraries,
Ink/Stitch installations/fonts, SAM2 model weights and local configuration are
not bundled. A fresh machine needs those optional runtimes configured separately;
see `SAM2-LOCAL.md` and the relevant feature documentation.

## Tests

```sh
PYTHONPATH=src:work/deps python3 -m pytest -q
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
licensing terms; they are not relicensed by this repository.
