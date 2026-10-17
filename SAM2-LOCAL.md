# Local subject-selection runtime

Installed with user permission on 2026-10-16. No Git repository was cloned or
pushed. The optional runtime and checkpoint are under ignored
`work/sam2-runtime/`; they are not committed. `work/deps` is unchanged.

The normal app command is unchanged:

```sh
PYTHONPATH=src:work/deps python3 -m embroiderly.web
```

If no explicit SAM2 checkpoint/config environment variables are provided, the
app detects this local runtime. A private, isolated Python subprocess holds one
CPU model and up to four image embeddings. No listening port, image upload,
API key inheritance, automatic download, CUDA build or package installation
occurs at app startup. Inference times out after 120 seconds. Existing manual
tools and the disclosed GrabCut fallback remain available on failure.

Set `EMBROIDERLY_SAM2_LOCAL=0` to disable automatic local detection. Explicit
`EMBROIDERLY_SAM2_CHECKPOINT` and `EMBROIDERLY_SAM2_CONFIG` retain the original
in-process installation path; they take precedence. Restart clears embeddings.

## Installed provenance

- Official SAM2 source archive, revision
  `2b90b9f5ceec907a1c18123530e92e794ad901a4`.
- PyTorch `2.7.1+cpu`, torchvision `0.22.1+cpu`, isolated Python 3.13.
- SAM-2 package `1.0`; checkpoint `sam2.1_hiera_tiny.pt`, matching
  `configs/sam2.1/sam2.1_hiera_t.yaml`.
- Checkpoint SHA-256:
  `7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69`.
- Checkpoint source:
  https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt
- Official installation reference:
  https://github.com/facebookresearch/sam2/blob/main/INSTALL.md
- Official licensing/reference: https://github.com/facebookresearch/sam2
  (SAM2 code/checkpoint Apache-2.0; installed package retains license metadata.)

Installation used a dedicated venv, the official PyTorch CPU index and the
pinned official SAM2 archive, with `SAM2_BUILD_CUDA=0`. `pip check` passed.
The CUDA hole/sprinkle postprocessor is disabled, not replaced by silent
hole-filling. This model is not proof of accurate subject extraction.

## Verification

`PYTHONPATH=src:work/deps python3 tests/sam2_smoke.py` runs the real local
model on the authorized Sasuke upload using fixed diagnostic hints. It checks
repeatability, warm embedding reuse and unchanged source bytes. Evidence is in
`.simple-ui-evidence/`, separate from saved designs. These fixed hints are a
test fixture, never an app special case or evidence of paid-AI localization.

Candidate ranking uses missed keep/remove hints before model confidence.
Remaining conflicts are reported; AI cannot clear them with an “acceptable”
review. Original-to-cutout and cutout-to-thread-plan findings remain separate.
Human preview/Apply and all stitch/export checks still apply.
