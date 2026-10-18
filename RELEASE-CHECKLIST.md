# Public-release checklist

Updated 2026-10-07. Not a declaration of production readiness.
Work one confirmed blocker at a time. Reuse evidence; do not rebuild completed fixes.

| # | Requirement | Current evidence / next acceptance |
|---|---|---|
| 1 | Background removal | Original 13-word batch passed; OUTPUT-SAFETY-CLOSURE.md. Retest only affected cases when code changes; broader artwork coverage pending. |
| 2 | Preserve details | Counter/cleanup review regressions passed. Semantic recognition and arbitrary-artwork fidelity not proven. |
| 3 | Reliable generation | Isolated blank/error/retry and playback suites pass. HELLO knockout machine-grid crossing fixed; bird decorative-boundary preview fixed. Short-stitch refusals remain. |
| 4 | Export safety | Shared gate intact; ten-pair trim parity and knockout warm/cold equality verified. Straight-run repair reduces short spans; genuine short corners remain blocked. See RELEASE-SPACING-FIX.md; 305 tests pass. |
| 5 | Physical testing | Blocked on real sew-outs and machine evidence; rendered previews are not certification. |
| 6 | Hoop validation | Confirmed gap: reference rectangle only. Verify supported machine profiles before implementing profile constraints. |
| 7 | Editing consistency | Piece checkpoint has 292 passing unit tests plus browser evidence. Portrait/ink-only transforms and decorative rotation remain limited. |
| 8 | Performance / jobs | Needs measured workload baseline; no blanket speed claim. Queue/cancellation and resource limits require audit. |
| 9 | Customer isolation / security | Public multi-customer deployment not verified. Audit authentication, ownership, upload/storage boundaries before hosting. |
| 10 | Production deployment | Local development server only. HTTPS, production server, monitoring and tested backup restore are launch gates. |
| 11 | Billing / costs | AI spend gating implemented previously; payment/subscription readiness unverified. Do not introduce paid calls or billing without configuration. |
| 12 | Claims / licences | Unsupported puff controls removed. Ink/Stitch (GPL) and Inkscape dependencies removed 2026-10-18; native engine and fonts documented in NATIVE-ENGINE.md. Whole dependency/licence and launch-copy review pending. |
| 13 | Layer ordering | Confirmed missing sew-order editing; omit from launch promise unless implemented and tested. |
| 14 | Advanced stitch settings | Confirmed missing per-piece controls documented in PIECE-PANEL-VERIFICATION.md. Scope out or implement separately. |
| 15 | Customer workflows | Restore reproducible browser checks first. Real novice/accessibility/cross-browser testing remains pending. |

## Working rule

For each change: reproduce, add or repair a regression, make a minimal patch, run focused checks, record evidence and commit. Run the full suite at code milestones. Never equate an unverified requirement with a confirmed bug. No customer files, credentials or models in commits.
