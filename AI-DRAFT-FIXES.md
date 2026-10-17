# AI selection fixes — 16 October 2026

Local restore point: `18e19bf`. No push, new repository, API-key change,
spending-cap change, or stitch/export-check relaxation.

## Fixed in this pass

1. SAM2 was absent, not merely slow: missing runtime, checkpoint and configuration.
   Installed an isolated CPU runtime with user approval; the usual app command
   detects it after restart. See `SAM2-LOCAL.md` for provenance and disable switch.
2. The model's highest-confidence mask could ignore keep/remove hints. Candidate
   ranking now minimizes hint conflicts first. Remaining conflicts are reported
   and cannot receive an automatic “acceptable” status from AI.
3. AI's fallback used to force all border pixels to background, removing cropped
   hair/clothes. Only the AI cutout path now treats those pixels as uncertain;
   legacy rectangle tools keep their previous margin policy.
4. The AI review can supply corrective hints for at most two further cutouts.
   Maximum four paid responses; identical cutouts are not reviewed again.
   Existing budgets, consent, cancellation and preview/Apply remain mandatory.
5. Cutout defects are separate from colour/detail loss in the prepared thread
   plan. The latter do not trigger incorrect selection repairs. Transparency is
   rendered on a checkerboard for review so black hair is not confused with it.
6. Failed/uncertain reviews cannot enable “Use & make stitches.” The user can
   still explicitly choose “Use & keep editing.” Existing controls, warnings,
   Undo, playback and generation owner remain. No new settings panel.
7. Expensive preparation validation runs in the bounded job, before any paid
   request, rather than delaying the initial HTTP submission.

## Evidence and remaining limits

- Full suite: **502 passed in 97.72 seconds**, up from 485 at the previous
  checkpoint. No tests skipped to hide installation failures. Fallback-specific
  tests now explicitly disable the optional local model. Runtime and credential
  isolation, timeout recovery, review-stage separation and bounded corrections
  have regression coverage. Syntax and `git diff --check` passed.
- Frontend-design guidance kept UI edits in the existing review panel and its
  established approval/Undo owner, without adding a new panel or visual theme.

- The priority regression was run against restore-point code and failed there.
  It passes on the fix. Border preservation is compared directly against the
  old border policy in its regression test.
- Real SAM2 + fixed diagnostic hints on Sasuke: retained pixels
  **149,996 → 206,516**, all nine hints respected after ranking. Repeated masks
  match; original file SHA-256 unchanged. Final smoke run: **6.55 seconds cold,
  96 ms warm decoder**. This is not the duration of paid AI review or stitching.
- Visual review: eyes and mouth preserved much better; holes/rough edges remain
  near clothing and outer hair. More retained pixels alone is not accuracy.
  No labelled ground-truth mask or quantitative semantic score is claimed.
- Browser tests passed using synthetic AI: keyboard, consent, loading, review,
  escaped model text, explicit Apply, exact Undo, cache, stale edits, cancellation,
  offline prompt retention, generation delegation, 390px dark/reduced-motion,
  and uncertain-review generation lockout. Screenshots are in ignored
  `.simple-ui-evidence/`; they are QA scenes, not live AI results.
- Strict UI audit still reports **89 pre-existing findings**, identical to the
  previous audit. They are not resolved by this pass. Legacy browser wrappers
  that write excluded output folders were not run; scoped tests were used.
- No stitching/export implementation files changed. No new machine-file or
  physical sew-out quality claim. Saved designs and original uploads unchanged.

## Pending live acceptance

The running server still reports the old AI-draft endpoint without the new
`subject-draft-v2` version. A restart was requested from the user's key-bearing
terminal. No key was read or copied and no paid calls were made in this fix pass.
The last real GPT review (before these fixes) failed Sasuke cutout acceptance;
that result remains in `AI-DRAFT-STATUS.json`, not overwritten with a test double.

After restart: verify endpoint version, run the same Sasuke prompt with the
existing budget policy, show actual model/usage/rounds and cutout, inspect remaining
hair/clothing defects, then obtain approval before generating stitches. Native
text creation, automatic thread-plan detail repair, export validation for an
approved draft and physical sew-out are still follow-ups.
