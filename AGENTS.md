# PROJECT

- Work only in this folder on this computer:
  /home/guyha/Documents/Codex/2026-09-04/files-mentioned-by-the-user-embroiderybuildprompt
- The user authorized publishing this project to their GitHub as `needler` on
  2026-10-16, then explicitly requested PUBLIC visibility. The approved destination
  is `habon-el/needler`. This replaces the earlier local-only/private restriction.
- Never publish API keys, credentials, customer uploads, downloaded models,
  installed libraries or generated output. Audit the contents and history of
  any branch before its first push.
- Public publication uses the clean `needler-public` branch mapped to remote `main`.
  Older development branches/history remain local; do not push them or use
  `--all` / `--mirror`. Preserve local customer data and generated reports.
- Start the app: `PYTHONPATH=src:work/deps python3 -m embroiderly.web`
  then open http://127.0.0.1:5050
- Don't read or edit `work/deps` (installed libraries), output folders, or
  leftover `*.orig` / `*.rej` files.
- If there's no AGENTS.md in the folder, create one containing this PROJECT
  section, so future sessions already know it.
