# UX contract

## Digitization result visibility (2026-10-16)

Authority: user reports that finishing digitization does not display its result
and asks for missing-result checks. This change is presentation and asynchronous
view ownership only; segmentation, stitch generation and export checks are unchanged.

- preparation.js exposes read-only resultInfo and deduplicated stitch-state events.
  Only real playback earns “Stitch preview ready”; preparation, no plan, blocked
  details and failures have distinct visible text. This does not certify exports.
- Matching saved plans reopen at Check stitches. Successful generation shows the
  completed paths. The same player retains Play, pause, seeking and Show full design.
- Compare artwork in Edit uses original/prepared; Compare stitches in Check uses
  original/actual stitched canvas. No second renderer or player was introduced.
- Automatic suggestions are skipped for existing playback and invalidated when
  generation starts. Late proposals cannot replace a result with the same options.
  Explicit user requests, consent, Apply, Undo and export guards are unchanged.
- Warning paragraphs use the existing foreground token in both themes. Empty
  canvases have a short, theme-aware placeholder that fits narrow screens.

### Evidence and remaining gaps

- Actual current Sasuke page: saved matching playback absent. Read-only preparation
  returned 1,702 regions, eight colours and 1,574 missing-boundary blockers, with no
  pending cleanup decisions. First blocker: one pixel, 0.2299 × 0.2299 mm. This is
  a converter limitation, not a finished digitization hidden by the UI. Nothing
  was deleted to obtain a successful status. Fixing this geometry remains open.
- New tests/browser_digitization_results.py failed on old code at “Compare hides
  actual stitches”. After correction it passes actual isolated rectangle generation
  (234 stitches, zero trims), Compare by keyboard, playback, saved reload, edit
  invalidation, error/retry, a real single-pixel boundary blocker, delayed suggestion
  rejection, light/dark, narrow layout and reduced motion. Late suggestion and HTTP
  error cases explicitly use response doubles; successful generation is real.
- PYTHONPATH=src:work/deps python3 -m pytest -q: 502 passed, 95.30 seconds.
- tests/browser_toolbox.py: passed, including native-text navigation and unchanged
  options. It also emitted the existing intermittent SAM2 shutdown AttributeError;
  that teardown race is still open and is not claimed fixed.
- tests/browser_ai_draft.py: passed, nine synthetic provider calls, zero paid calls.
- node --check for the three changed scripts and git diff --check pass.
- Strict UI audit remains at 89 pre-existing findings before/after. Not a clean
  whole-application accessibility certification; broader audit triage remains open.
- Live port 5050 serves the updated three scripts (HTTP 200). No restart required
  for these static changes; refresh the page. Customer design/options not edited.
- Browser evidence: .simple-ui-evidence/result-{empty,generated,compare,saved,
  generating,error,blocked,narrow-dark}.png. Desktop browser automation was unavailable,
  so verification used a separate isolated Chromium and disposable app, not the
  user's tabs. No physical sew-out, full export parity study, or whole-product
  capability inventory was performed in this display-fix pass.

## Feature-map-inspired toolbox (2026-10-16)

Authority: the user's supplied Hatch Embroidery 4 feature-map PDF and request for
clearer buttons and AI-friendly operation. The PDF is an inventory inferred from
binary names, not a verified specification of algorithms. No Hatch code, fonts,
icons, machine writers, licensing or proprietary assets were imported.

workflow.js keeps its original value/action owners. AI assistant plus six labelled
icon buttons expose Background, New text, Colours, Stitch styles, Borders and
Review details. Duplicate topic buttons are hidden in Expert settings; only size/
fabric and fine-tuning remain there. New text is the SAME textTool node moved from
the left rail, still creating a separate lettering design, not adding text to the
current picture. Native text workspaces retain their original controls.

Opening a tool changes no artwork or stitch settings. Keyboard activation focuses
the topic; All tools returns focus to its button. Native text dialog focus stays
with lettering.js. Styling consumes existing tokens, including dark-mode approval
contrast; no new theme or icon family. Playback and all safety notices remain.

ask-ai.js owns three editable starters: Remove background, Keep fine details,
Review details. The first two select draft mode; the last selects read-only advice.
None sends a request or checks consent. Existing paid-call caps, cancellation,
before/after preview, explicit Apply and Undo remain authoritative. AI is not
given control of font creation, arbitrary stitch settings, export or machine code.

### Reference-to-product boundary

| Reference concept | Available owner / button | Limitation |
|---|---|---|
| Artwork selection / segmentation | Background; existing SAM2 adapter and colour removal | AI cutouts still need visual approval |
| Lettering | New text; lettering-native.js | Installed supported embroidery fonts, not the PDF's proprietary font collection |
| Colour management | Colours; existing preparation options | No new commercial thread catalogue or colourway engine |
| Object stitch styles | Stitch styles; region-styles.js | Existing geometry eligibility and experimental style warnings still apply |
| Subject borders | Borders; existing border editor | Not a new appliqué, sequin or foam-puff engine |
| Dimensions | Width/height; design-size.js | Canvas including margins; no new machine/hoop compatibility catalogue |
| Review and simulation | Review details; Check stitches; existing player | Appearance/file checks are not a physical sew-out guarantee |
| Machine files | Save and download; existing DST/PES path | No new formats, USB-machine transfer or .EMB editing |

Specialty tools from the map (rhinestones, monogram/team-name batch production,
scanner/Corel integration, commercial-format parity) were NOT implemented or
advertised as available. This pass does not certify existing experimental styles.

### Verification

Clean local starting revision: c1857b6; no remote operations. No generation,
selection, export, machine policy or backend source changed.
- Full test suite: 502 passed (117.39 s).
- tests/browser_toolbox.py: isolated synthetic artwork, no paid calls; keyboard
  navigation/focus, single setting/control owners, unchanged design snapshot,
  Text dialog, AI prompt-only behavior, narrow/dark and native-text sibling.
  New seven-button regression was checked failing on the previous UI.
- tests/browser_ai_draft.py: synthetic provider, nine test calls, zero paid;
  approval/Undo, stale/cancel/offline and uncertain-selection behavior pass.
- tests/browser_ask_ai.py: question consent, history, IME, offline/cancel/stale,
  credential rejection, keyboard and narrow/dark/reduced-motion checks pass.
- Screenshots: .simple-ui-evidence/toolbox-before-edit.png and toolbox-after-*.png.
  These show a synthetic test design, not a newly digitized customer image.
- Strict frontend audit: 89 existing findings before and after, identical.
  Not a clean whole-app audit; legacy handler detection and styles remain debt.
- Existing isolated-app shutdown intermittently reports a sam2_local.close
  cleanup race. Not caused or repaired by this presentation-only change.
- No fresh paid-model quality test, physical sew-out or new export comparison is
  claimed. Tests exercise controller behavior, not semantic cutout accuracy.

Click-path length from Edit (not usability): Stitch styles 2 → 1; Borders 2 → 1;
Background 1 → 1; Colours 1 → 1; Review details 1 → 1; AI 1 → 1; New text 1 → 1.
These count tool-opening clicks only; they do not count completion of the task.


## Beginner editor simplification (2026-10-14)

The existing workflow.js owns disclosure: size is the default; Background,
Thread colours and Picture details open the same topic nodes directly, with
Back to size. Expert settings retains all other topics. Width and height are
the existing proportional canvas-size fields, including empty margins. No
second dimensions, preset or machine settings store is created.

The existing read-only review now shows paired crops before descriptions.
Optional AI help and older detail tools open manually, independently of the
global explanation preference; safety blockers remain in the existing health
panel. No repair or Keep action is invented for read-only AI suggestions.

Image download UI fetches the existing checked export link, displaying all
server issues in-page. Native downloads still use their original controller.
No generation, approval, release checks or files are rewritten by the adapter.

## Read-only artwork review (2026-10-14)

The existing detail panel owns Check my design. It compares selected subject
pixels with prepared artwork, showing paired crops and measured locations.
It does not assess stitches, unselected details, physical sewability or native
typed text. Explicit painting, erasure and accepted colour removal are intent.
Palette differences are candidates for review, not proof of defects.

Optional GPT-5.4 mini explanations require per-request image-sharing consent.
provider_budget remains the sole network/spend owner; no keys, limits or model
rates are enabled by this pass. Results are suggestions, never operations.
Stale results are discarded. A bounded process-local cache avoids duplicate
charges within one process; multi-worker deduplication remains a deployment gap.
Only the read-only review endpoint bypasses mutation serialization so a network
wait cannot block editing. All existing mutation and export guards remain intact.

## Practical resizing and cleanup review (2026-10-14 follow-up)

Authority: the current user requests easier resizing, smaller lettering and fewer
editing obstacles. This is an explicitly functional follow-up, not the earlier
layout-only pass. Existing workspace tokens and visual identity remain unchanged.

preparation.js owns image size/history; design-size.js adds proportional ±10%
actions through that owner. lettering-native.js owns nominal text size and its
±10% actions; these trigger normal invalidation and native regeneration, never
machine-coordinate scaling. small_lettering.size_limits reads the installed font
author's range; the enabled font currently permits 3.6–15.2 mm inputs. This is a
nominal setting, not a measured capital-height or sewability guarantee.
Available width is still an explicit fit constraint, not auto-shrinking.

detail-loss.js keeps pending cleanup choices together through one studio.apply
history entry. Prior Keep/Drop choices remain unchanged; only the currently
previewed pending IDs are accepted. Stale/busy actions do nothing. Decisions
remain size/geometry-specific. Thirty entries render initially; every remaining
entry is available through Show more and the full downloaded report.
The preparation API returns a structured review with images, without saving or
generating files. workflow.js opens that same existing review, never a duplicate
settings owner. Keyboard focus, Undo, stale actions and narrow reflow are tested.

Native lettering may try one explicit SVG securing-stitch pattern when the
original written pair fails only short-stitch checks. Letter paths, font, size,
spacing and source verification envelope do not change. The candidate is rebuilt
and both files are checked; only a fully passing candidate replaces the draft.
Unknown/crossing failures are not repaired by this rule. Passing initial builds
are not changed. The visible result reports the adjustment before explicit Save.
The helper follows the documented custom SVG lock contract:
https://inkstitch.org/docs/stitches/lock-stitches/

Unresolved: larger-text routing cases, tiny raster contour conversion, density,
cold-run repeatability, physical sew-out and full historical UI audit.
See SIZE-EDITING-STATUS.json for the measured results; not universal readiness.


## UI-only three-step consolidation (2026-10-14)

Authority: the latest local-only UI CLEAN-UP request. No generation, writer,
release policy, font settings or saved embroidery values change in this pass.
Restore point: local commit 51527e1; no remote operations.

workflow.js owns transient Edit / Check stitches / Save and download disclosure.
preparation.js and lettering-native.js remain the only action/value owners.
The same DOM fields are moved, never cloned. The image save owner emits a
success notification for the header's Saved echo; click/failure never implies
success. Existing download/approval handlers remain authoritative. Native
spacing, placement and per-letter fixes are not invented.

Native /text/new is an empty view of the existing editor, with no generation
or save on GET. Native font size is explicitly nominal, not measured capital
height. The displayed width/height comes from the existing checked-file report.
Colour-coded size advice is not a new sewability check.

The single visible primary action is Check stitches (Update stitches only after
an edit to an existing plan), then Save and download, then Download selected
format. Save design remains in the header. Hidden legacy action nodes are kept
solely as controller targets. Native file and route warnings are not collapsed.
Long explanations and existing image topics sit under closed disclosures.
Native OS selects, English labels, token colours and keyboard semantics remain.

Library rename now edits in the card using the existing revision-checked API.
Cancel/Escape makes no API request. Missing original filenames are not invented:
generated labels display an explicit date-based image fallback without changing
stored names. Native immutable text projects are still absent from DesignLibrary;
a unified text/image index requires a separate approved metadata integration.
No new trash/deletion behaviour is introduced.

Verification: ui_cleanup_verify.py compares downloaded DST/PES commands for a
text, an image and small text; ui_cleanup_interactions.py covers the new flow,
validation, save/download state, stale replies, inline rename and reflow.
Existing tests remain required. The static auditor cannot resolve external
vanilla-JS handlers; its findings are recorded separately, not called a clean gate.

## Editable lettering workspace integration (2026-10-14)

The current user approves lettering integration only; image preparation remains
out of scope. Native projects use /text/<recipe-id> and the existing workbench
canvas/playback. lettering-native.js remains the only owner of words, font,
nominal size, alignment, thread colour and available-width validation.
lettering-workspace.js adapts those same controls and check/save actions to the
inspector and main toolbar; it does not create a second setting store.
lettering_workspace.py supplies source-outline SVG for display and reads the
checked DST snapshot for playback. Neither is sent to image preparation.

Changing any text setting invalidates approval and main download buttons.
Update stitches rebuilds font vectors; Save design explicitly approves the
checked immutable recipe. Resizing does not scale machine coordinates.
Undo restores the prior recipe fields and requires rechecking. A saved URL
reopens its exact version; an edited version never overwrites the original.
Available width remains a fit constraint, not a request to auto-shrink.

Old native_text bookmarks redirect into this workspace, not an underlying PNG.
Known legacy picture-based typed designs now offer an explicit embroidery-font
rebuild when Update stitches is pressed; the server rejects attempts to re-enter
image digitizing for those saved text recipes. The original chosen font/image is
not replaced. Ordinary outline fonts remain a labelled legacy artwork option;
they are not promised to work as native embroidery fonts.

Native text hides picture selection/cleanup/style controls and rejects picture
mutation through the shared studio interface. Pan, ruler, Compare and stitch
playback reuse existing owners. Download errors remain in-page. Native selects,
English copy, workspace tokens and field validation are retained. No new colour
palette or visual design. No automated change to font, words or line breaks.

Only installed Small Font nominal 4–6 mm is enabled. Additional fonts, density,
exact cap-height sizing, cold-run generator determinism, cap-specific ordering
and physical sew-out remain unverified. A successful file check is not a needle-
safety or readability guarantee. Native projects are reopened by their saved
link; inclusion in the image-only Recent designs library is not yet implemented.

## Native typed lettering rebuild (2026-10-13)

The user's text-rebuild request introduces a separate, explicit satin-text path
inside the existing Text dialog. Words/alignment/colour remain shared dialog
inputs; native font/nominal size/available width belong to lettering-native.js.
Available width is a fit constraint, never an instruction to scale stitches.
Artwork-font controls remain in a labelled disclosure; existing PNG designs,
recipes, selection, raster generation and toolbar exports are not converted.
The old read-only trial endpoint is compatibility-only, not the primary UI.

lettering_native.py owns immutable local draft/check/save receipts. Source/font/
engine/code fingerprints bind the cache. Fit-only edits reuse geometry, but need
a fresh explicit approval. Download rechecks both written files through the
shared release gate. Changed settings/close invalidate pending results and links.
Failures stay in the dialog; no raw JSON tab is opened by its download buttons.
Native selects, existing tokens/modal focus/English locale remain canonical.
No new theme, cloud storage or auth policy. Density, cold-generator determinism,
additional fonts and physical sew-out remain explicit limitations, not success
claims. Below-4 mm text is not enabled. See SMALL-TEXT-TRIAL-CHECKPOINT.md.

## Rectangle selection recovery (2026-10-13)

preparation.js owns the rectangle draft independently of preparation options.
Click/zero-area gestures, Escape, blur and pointer cancel preserve selection,
history and playback; only a valid released rectangle commits through existing Undo.
preparation.py uses existing transparency as the cutout within that rectangle,
preserving letters and counters instead of inferring them again from RGB.
Opaque images retain colour-based selection and need background evidence.
This does not remove intentional opaque white or approve stitch exports.

## Width-first size clarification (2026-10-13)

design-size.js adapts the existing preparation.options.height_mm to an editable
canvas width; it stores no second dimension. Both fields explicitly use mm,
matching the existing canvas-height owner (piece transforms still use Settings
units). Proportions remain locked. Enter/blur commits through studio.apply;
Escape/invalid input preserves state, Undo restores it, and exports invalidate.
Stitches require explicit regeneration. Canvas includes margins, not just ink.
lettering_size.py measures reference capital H from the saved outline-font recipe;
this is an estimate before stitches, not a physical quality or glyph audit.
Typed designs get a lettering review heading even when tiny-area flags are absent.
The read-only embroidery trial measures available-width fit without shrinking,
cropping or reflowing words. A fit result never approves machine export.
Original uploads, recipes, default generation and release limits are unchanged.

## Small-lettering trial (2026-10-13)

The existing Text dialog owns words and alignment. lettering-trial.js owns only
transient trial font/nominal-height inputs and the explicit read-only rebuild action.
Native selects, dialog focus and workspace tokens remain canonical. Edits/close
invalidate outstanding results. lettering_trial.py measures saved DST/PES files
in temporary storage; no design mutation or export URL is permitted. Length checks
do not approve release: hole containment, density, glyph completeness and sew-out remain pending.

## Read-only ruler (2026-10-07)

The ruler additionally supports drag creation, endpoint adjustment and whole-line translation with live distance. Escape/cancel/blur restores the pre-drag measurement. Native keyboard-target selection accepts an OS-owned popup; arrow adjustments provide non-drag alternatives. All ruler operations remain transient, outside design history and exports.

design-ruler.js owns transient A/B points only; preparation.js owns image coordinates, pan/zoom and height_mm. SettingsService owns units. Ruler never edits artwork or generates stitches. Edit size navigates to the existing single canvas-height editor; piece sizing retains its existing owner. Click-click and keyboard alternatives, Clear/Escape and visible distance are documented and tested in RULER-VERIFICATION.md. Existing workspace tokens and icons are reused; no new palette or settings owner.

## Piece editing checkpoint (2026-10-07)

Preparation options own piece_edits; piece_layout.py owns geometry and lock validation.
piece-panel.js presents the single selection and property editor; existing region_styles owns stitch type.
SettingsService owns units. Mutations use preparation.js history and revision-checked requests.
Resize regenerates stitches; failures retain prior saved options. No duplicate density editor is introduced.
See PIECE-PANEL-VERIFICATION.md for measurements, settings ownership and explicit capability gaps.

## Output-safety corrections (2026-10-04)

The six explicitly approved September 30 audit fixes supersede earlier unchanged-
export promises for this pass. release_gate.py owns every PES/DST download check;
a render is not release approval. Missing verification context requires regeneration.
Preparation options/history remain the single owner of cleanup_decisions.
detail-loss.js presents real-size Keep it / Let it go choices before save or generation.
colour-knockout.js presents tentative hole-shape hints and explicit Fill this speck /
Keep hole open choices; small holes are not silently filled. Existing Undo applies.
Legacy design.html no longer offers foam-puff controls. No visual tokens or layout
owners change. Physical sew-out validation and participant usability remain pending.


## Phase 1A closure safeguards (2026-09-22)

User closure instructions supersede earlier checkpoint limitations: paid assistance requires explicit
per-design and monthly USD budgets, verified exact-model rates, preflight input-token counting,
and an atomic maximum-cost reservation. provider_budget.py is the sole network owner for both
assistant adapters. No caps or rates are supplied on the user’s behalf. This is not invoice reconciliation.
Legacy POST forms use form-validation.js as their validation owner; existing constraints and server
validation remain. No native validation bubbles. Sew-out output is assistance, not assessment;
three sample photos demonstrate a pipeline only, not diagnostic accuracy.

## Advisory intelligence (2026-09-21)

The attached advisory brief owns the phase ordering and no-silent-edits policy. advisors.py owns pure
reasoning; knowledge_store.py owns table loading; sewout_review.py owns optional vision and local reports.
The existing Check design topic hosts sewout-review.js. It never calls studio.apply. Unsupported remedies
have no Apply action. Photo reports persist separately; photos do not. Model requests require per-request consent.

## Settings and library checkpoint (2026-09-19)

The attached settings brief authorizes local persistence and recoverable deletion without confirmation.
SettingsService owns appearance; settings.js is its only editor. settings.css adapts canonical tokens.
Native dialog owns modal focus, Escape, inert background and restoration. Native selects remain intentional.
Keyboard events stay in the dialog. Revision conflicts require reload, not overwrite. No authentication ships.
DesignLibrary owns recent names, visibility and trash; originals and their saved edits remain in place.
Library query/sort/view persist in the URL; selection is transient and reset on filtering or loading.
Permanent deletion and 30-day purge remain disabled pending shared-asset verification. No files are deleted by Trash.

## Product context and sources

English, first-time embroidery users; desktop precision editing, narrow-screen review.
Accessibility target WCAG 2.2 AA, not yet certified. The latest user request authorizes safer outlined erase
in addition to frontend simplification. Earlier consolidation inventory is in `outputs/consolidation-checkpoints.md`.
`preparation.py` owns reversible artwork preparation; `engine.py` owns generation; export policy is unchanged.
No new authentication, billing, retention, cloud consent or license policy is introduced.
Original uploads are not edited; a preparation operation changes options, with explicit Save.

## Visual contract

See DESIGN.md. Runtime canonical tokens: workspace-ui.css; vanilla JS/Jinja, no UI framework or locale provider.
English only. OS-native select popups intentionally retained. No date/time inputs in this slice.

## Canonical UI Map

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
|---|---|---|---|---|
| Select/Listbox | Native select | Existing controls and this contract | OS popup | Browser keyboard |
| Form | preparation.js options + existing handlers | Preparation API | Inline edits, explicit save | pytest + browser |
| Scrollbar | workspace-ui.css root | DESIGN.md | Inspector geometry | Computed style |
| Toast | preparation.js status() / #status | Existing status live region | Pending, success, failure | Browser |
| CRUD | preparation.js | Existing preparation API | Preview, save; no hard delete | Browser + tests |
| Direct manipulation | preparation.js | Image-space coordinates | Outline, brush, pan | Browser + pixel tests |
| Topic disclosure | workspace-ui.js | Transient topic state | Selection, colour, border, size, detail, review, assistant | Browser |

Table selection/date are not applicable. Topic navigation does not duplicate field values or submit work.
Every existing field DOM node is moved, not cloned. Stored keys remain unchanged.

## Interaction and flow ledger

| Operation | Trigger | Pending / success | Failure / cancel |
|---|---|---|---|
| Switch topic | Labeled icon button | Immediate, same design | No data mutation |
| Outline subject | Click points, Keep outline | Existing preview request | Cancel drops draft only |
| Erase area | Click points, Erase area | Red draft, explicit commit, Subject preview | Esc/Cancel changes nothing; Undo restores options |
| Brush erase | More selection tools | Visible footprint, apply on pointer-up | Pointer-cancel restores pre-gesture options and history |
| Edit colours | Existing colour input | Existing live preview, exports invalidated | Existing retry; no new async owner |
| Generate / save | Existing toolbar | Busy guard and status | Inline error, retry, retain inputs |

## Navigation, responsive and feedback

Task navigation uses ordinary buttons with aria-pressed, not incomplete ARIA tabs. It is transient UI state;
refresh defaults to Selection. No URL or generation changes. All topics remain keyboard reachable.
Existing route titles and paths remain. Legacy prepare is a sibling reference, not a template to clone.
No modal is needed for reversible outline drafts: explicit apply/cancel and Undo are canonical.
Critical errors stay in the status area; static instructions move into native disclosure.
No claims of durable unsaved draft recovery or multi-tab conflict protection (existing gaps).
All new shortcuts ignore text input and IME composition. Space/middle-drag continues to pan.

## Scope and migration

This slice improves the main /artwork workspace. It is not completion of the earlier 11-to-1 target.
Do not delete legacy routes in the layout commit. Do not change generation/export in this slice.
The new polygon erase edit is a specifically requested behavior change, isolated from the UI commit.
Existing brush edits retain their stored shape and semantics; polygons opt in with shape=polygon.

## Verification

Run pytest, JavaScript syntax checks, screenshot/browser gestures, narrow layout, keyboard navigation,
cancel/Undo, exact erased-pixel coverage, export fixture byte comparison and the premium strict audit.
Static audit covers the migrated surface, not a certification of legacy screens. Human novice testing remains pending participant.

## Explicit black-line correction (2026-09-23)

The user's cartoon bug report authorizes an opt-in black-lines-only behavior change, not a global removal of white. `options.ink_only` is owned by preparation options and edited once in the existing Colours section. Undo, save, preview and stale-plan checks use the existing workflow. Normal mode retains intentional white. Ink-only mode bypasses destructive cleanup without overwriting the user's saved cleanup choices; conflicting border/portrait/recovery modes report an error. Palette changes and inactive cleanup controls are disabled while this intent applies. Subject is the source selection; Thread plan is what receives stitches. The new running-path branch is opt-in and uses the existing file readback. Browser coverage: tests/browser_black_ink.py. Physical sewability is not inferred from pixel retention or a render.

## Line weight and thread appearance (2026-09-23)

Current user request authorizes opt-in stitch-generation changes for black-line drawings.
Preparation options own ink_length_mm (existing 2 mm default) and ink_bean_repeats (existing zero default).
Colours contains their only editors; disabled outside Black lines only. The server rejects invalid ranges.
Reinforced bean adds forward/back/forward passes to traced running paths; isolated dots remain fills.
It does not specify physical line width. Changes invalidate playback and require explicit Generate stitches.
Size & fabric owns transient visual strand width and raised lighting. These redraw only the shared StitchLayer,
never update preparation options, machine paths, stitch counts or exports. This is not a thread-gauge selector.
Thread plan stays the colour/coverage artwork; Stitches is the actual generated path view. No fabricated
thickened thread-plan pixels are presented as new machine stitches. True 3D foam and per-object satin
conversion are not implemented. Existing satin borders retain their existing owner and constraints.
Native selects/ranges, existing status/undo/save, tokens and navigation are reused. No identity redesign.

## Visual stitch chooser (2026-09-23)

stitch-chooser.js progressively replaces the line-weight and border-style dropdowns with illustrated native
radio cards in their existing panels. Original selects are hidden handler adapters, not second visible editors.
Preparation options remain the only state owner; cards dispatch the existing input/change handlers, follow
Undo and saved options, and become disabled while busy. Border choices are unavailable in ink-only mode,
with an explicit reason. These examples illustrate Running, Reinforced bean, and outer Satin; they are not
new fill algorithms, textile photos, physical gauges or 3D puff. Existing spacing and width fields are reused.
Keyboard arrow keys, labels, radio state, focus rings and 390px reflow are covered by browser tests.

## Per-area stitch styles and safe speed improvements (2026-09-23)

The latest explicit user request authorizes a seventh Stitch styles topic and opt-in per-area generation.
This supersedes the earlier gap notes above for the bounded implementations now tested. Black-line settings
move (not copy) from Colours into this topic. Colour selection and border controls retain their owners.
region_stitches.py owns shared contour identities, eligibility, validation and pattern geometry.
options.region_styles maps geometry hashes to style IDs; colour changes alone preserve IDs, shape changes
produce visibly unmatched assignments and generation refuses stale targets. region-styles.js owns the only
area/style editor and uses embroideryStudio.apply for Undo, dirty state, explicit Save and Generate.
A native area selector and highlighted Thread plan identify the target. No universal machine compatibility
or physical correctness is inferred. Defaults without assignments retain existing generation.

Tatami, contour, circular ripple and meander use the installed engine's existing fill modes. Motif and Cross
use our bounded clipped line patterns. Embossed is explicitly a diamond running overlay on Tatami, not a
commercial carving/stamp library. 3D satin is explicitly three-layer raised satin, not foam. Satin requires
simple narrow convex hole-free geometry (app guardrail 0.8–6 mm across). Invalid geometry is rejected,
never silently changed to another style. These implementations require sew-out validation.

Saved-plan exact hits return before historical scanning; geometry candidates are checked before expensive
artifact validation on colour-only changes. Matching candidates still require complete artifact hashes.
No spacing, pixel detail, stitch count, segmentation or routing is reduced to claim speed.

## Explicit stitch-style targets (2026-09-23)

User-requested colour grouping extends the sole region-styles.js editor, not the colour-value editor.
The native target select starts empty and offers all areas of a colour or one area. Navigation and target
selection never mutate options. Mixed styles show no checked radio. Choosing a style updates exactly the
selected IDs in one Undoable operation; actual stitch generation remains explicit. Satin is disabled if any
target is ineligible, with counts; never silently skip targets. Green highlights all target rings in Thread plan
and is explicitly not thread colour. Target selection is transient; saved per-area styles remain authoritative.

## Written-file thread surface (2026-09-27)

The Stitches toolbar owns the single realistic/plain switch and PNG/retry actions. Size & fabric owns
all editable transient appearance: one session thread-weight width profile, texture, light angle, neutral
light and opt-in drag. Native angle input is the drag alternative. preview-lighting.js owns those events;
preparation.js remains the only owner of design options. No machine setting is duplicated or changed.

ThreadSurface is a shared WebGL2 component behind StitchLayer; CPU thread_surface.py reads written
PES/DST for PNGs. Existing workspace playback is PES readback. Graphics failure is a visible plain-line
fallback with retry; unavailable playback disables PNG saving. Mockup errors preserve the design.
Preview height and fabric are illustrative, not foam or a sew-out guarantee. Session weight profiles are
not calibrated catalogue assignments. See THREAD-RENDERING.md for measured results and open acceptance
gates: software-GPU performance, hardware validation and real sew-out photographs.
## Explicit colour knockout (2026-09-27)

The lettering/line-art bug brief authorizes deterministic colour removal, not a
global reinterpretation of white as background. preparation.js options/history
own colour_knockouts; colour-knockout.js owns only the transient proposal UI in
Subject / Select & approve. Original-image sampling or the native colour input
chooses the target; the native scope select intentionally uses an OS-owned popup.
CIELab tolerance and cited unverified physical cleanup seeds have one editor here.

Flat-art classification proposes only. The existing canvas displays a labelled
before/after wipe; keyboard range input is the non-drag alternative. Apply commits
via studio.apply, Cancel discards, Undo restores, Save persists. Enclosed parts are
unticked by default and recoverable; cleanup-only Undo is independent of removal.
Generic cleanup controls are disabled with an explanation while removal overrides
them; their stored values do not change. Original uploads are immutable.

The existing assistant request owner provides busy, timeout, cancellation and
stale-snapshot rejection. Local white-removal commands bypass providers even when
the cloud-consent checkbox was ticked. Failed/stale proposals cannot be applied.
No new model, consent, billing or permission policy is introduced.

For explicitly accepted knockout only, engine.py invokes knockout_routing.py,
cuts exposed connectors and verifies staged PES/DST readback before replacing
machine files. Unsupported portrait/recovery combinations and unresolved unsafe
paths fail explicitly. Details, tests and limitations: COLOUR-KNOCKOUT.md.
## Prepared-preview navigation correction (2026-09-27)

The user reported the old interface after following a generated preview link.
Prepared /engine URLs now redirect to /artwork with view=stitched; the prepared-to-
source redirect preserves that allow-listed view. No generation or save occurs
during this navigation. /artwork without the parameter keeps its existing default.
An explicit stitch deep link suppresses automatic artwork proposals so they cannot
replace the requested stitch view. Missing current stitches use the existing empty
state and require explicit generation; no unrelated older plan is substituted.

View stitches is the existing toolbar link, renamed from Advanced playback. Its
ordinary/keyboard activation selects the existing canvas without leaving the page
or discarding unsaved edits. Modified-click navigation uses a normal workspace URL.
Machine/export identifiers in backend payloads are unchanged. Unprepared legacy
engine tooling and POST compatibility remain; this is not a whole-route migration.
Visual tokens, layout, controls and stitch-generation logic are unchanged.

## Digitizer repair: missing selected detail (2026-10-14)

The preparation controller owns generation_blockers: original pixel bounds and
physical dimensions for selected colour components the fill converter would omit.
The existing health panel renders them before approval and focuses the comparison
canvas on request. workflow.js moves that same panel outside the hidden steps when
blocked; there is no copied warning state or extra settings owner. Keyboard focus
and 390px reflow are covered by tests/browser_missing_detail.py.

The server checks the same condition before generation or cached-plan reuse.
No tiny pixel component is silently expanded, substituted, or treated as sewn.
This is a fail-closed guard, not a new converter for such details. A higher-resolution
original or an explicit edit is still required. Existing safety checks remain.









## Persistent stitch playback (2026-10-14)

The user requested restoration of the missing preview and player. This supersedes
step-specific hiding of the transport: the same existing Play, Pause, rewind,
step, timeline, speed and thread status controls stay visible in Edit, Check and
Download. preparation.js remains the only playback/cursor owner; its existing
handlers select the stitched canvas. workflow.js adds only a heading and an
available/empty explanation. No autoplay, copied player or generation change.
After edits, the existing invalidation disables playback until stitches are
current again. The UI promises a path preview, not a physical safety assessment.
Browser regression covers both image and native text, keyboard activation,
pause/resume without reset, seeking, invalidation, empty state and narrow/dark UI.

## Ask AI questions (2026-10-15)

The user requested a visible prompt area for the uploaded-artwork workspace.
Ask AI is a basic topic beside Picture details, using the existing inspector,
workspace-ui.js topic navigation and workflow.js basic-panel disclosure.
ask-ai.js is the sole prompt/history owner. It uses native labelled controls,
the existing tokens and inline role=status feedback; no modal or new palette.
Native lettering is not routed through this raster comparison feature.

design_review.py owns read-only mode=ask. It builds the selected-original and
prepared images server-side from current options, labels them explicitly, and
uses provider_budget.py with the same verified model and spending caps.
Consent is required per send and states that the question, last three exchanges
and both artwork images go to OpenAI. No request fires on typing or opening.
No keys are accepted by this UI. Obvious API credentials in a question are rejected.

Replies are plain text (never HTML, commands, settings or geometry). The route
validates the actual returned model and answer schema. No stitch generation,
export, safety gate or design state changes. Existing suggested edits retain
their separate preview/Apply owner in Expert settings.

A bounded process-local result cache avoids repeated identical calls; in-flight
duplicates are rejected. This is not distributed deduplication. The conversation
is page-local, bounded to three exchanges, cleared on design changes/reload,
and never written to design files or browser storage. Timeout/cancel warns that
a sent request may still cost money. Draft text survives failures/design changes,
and beforeunload protects a nonempty draft. Late replies cannot overwrite a
changed design. All model advice is fallible and cannot certify machine safety.


## AI-operated subject drafts (2026-10-16)

The basic image workspace now leads with a labelled AI-assistant icon/card.
One prompt owner (ask-ai.js) offers Make a draft or Ask a question. The original
advice route is retained; no paid call fires from typing or opening the page.
Long help stays under How it works. A completed draft replaces only the canvas
tools with large Original / Proposed cutout images and a Thread plan toggle.
The inspector then shows findings and explicit actions, not the prompt form.
Playback and existing warnings remain available; a draft is never called stitches.
Frontend-design-premium guided reuse of the existing tokens, controls and owner
map, with scoped keyboard, narrow/dark, failure and asynchronous-state checks.

ai_draft.py owns strict model-plan validation and bounded process-local jobs.
The first budgeted call locates the subject with normalized seed points/box.
The existing subject_model.py executor makes the actual mask (SAM2 if configured;
otherwise explicitly labelled GrabCut). Existing preparation produces artwork.
The second budgeted call compares original, cutout and artwork. Review failure
is visible and does not manufacture an AI pass. No changes to model rates/caps.

The only model-selected actions are subject selection and explicitly requested
subject width. Unsupported tasks clarify; AI cannot run code, write arbitrary
settings, generate text, change stitch policy, approve warnings, or export.
Saved native lettering, locked objects and manually edited pieces are excluded
from this selection operation to preserve their existing owners.
Consent states images/prompt are shared and up to four calls may be billed:
localization, review and at most two correction re-reviews. Identical cutouts
reuse their review, and budget failures never produce a false approval.
Requests are foreground, bounded and cancellable between calls. In-flight
provider charges cannot be undone. Drafts expire after 30 minutes/server restart.

Use & keep editing delegates one patch to preparation.js apply/Undo. Use & make
stitches delegates the same patch to acceptRefinement, including its existing
approval, generation, invalidation and safety gates. It does not promise generation
will succeed. Server-side approval validates original/options identity and locks;
the browser rejects stale replies. No original or design is written by the draft
endpoint. Exact repeats reuse memory results, including after Undo. Two active
workers and sixteen retained jobs limit resource use; this is single-process,
not a hosted multi-user authentication or distributed job system.

Tests with synthetic providers are labelled as such and are not live-model
quality evidence. Machine sew-out, corrections beyond the bounded two-round
selection loop, editable text creation from prompts and hosted job/account
isolation remain follow-ups.

### Selection correction checkpoint (2026-10-16)

The existing assistant owner and review panel are retained; no new panel or
visual tokens. SAM2 runtime detection uses an isolated local CPU worker, never
work/deps. Candidate ranking honors keep/remove hints before model confidence.
AI-driven GrabCut does not force image borders to background; legacy rectangle
selection retains its margin behavior. Review images explicitly show transparency.
Selection problems and thread-plan detail loss have separate findings. Only
selection problems receive corrective hints; no colour/detail or stitch changes
are applied by this loop. Uncertain, conflicting or failed reviews disable
Use & make stitches, but allow explicit Use & keep editing. Undo, cancellation,
stale-result rejection, budget gates and all warnings stay with existing owners.
Physical output and semantic accuracy still require independent verification.

## Automatic picture reviews and guided corrections (2026-10-18)

Owner: ai-workflow.js presents one compact review surface below the existing
stitch player. ask-ai.js remains the only prompt owner; preparation.js remains
the only apply/undo/playback owner. No stitch generator, renderer, export policy
or numerical safety threshold changed in this pass.

Consent update: the earlier per-request-only rule still applies to drafts and
questions. A separate, initially OFF, labelled Auto-review opt-in now remembers
permission in this browser to send new pictures and finished stitch previews
to OpenAI. The adjacent wording discloses paid sharing and existing caps.
Switching it off prevents future automatic requests, not charges already sent.
Native lettering is excluded; no picture rules are applied to native text.

ai_workflow.py uses the existing BudgetedProvider and exact configured model.
Upload review sees the original image. Finished review requires a matching
saved plan and sees original, approved prepared image, and actual saved paths
rendered by the existing renderer. It does not regenerate or export stitches.
Rendering is independently fitted, so the model must compare semantic details,
not infer pixel alignment, physical stitch quality or machine safety.

Strict responses contain a summary and at most eight uncertain/possible source
detail boxes. Small original-image thumbnails and Show me locate these details.
Keep / Remove prepare a request in the existing assistant (never overwrite an
unfinished prompt, send a paid call or apply an edit). The user reviews/sends it
and approves its draft. Fix manually opens the existing outline tool. AI boxes
are approximate navigation aids, never masks or erased rectangles. Unsupported
precise corrections remain manual rather than pretending a change succeeded.

Existing local cleanup/detail-loss measurements now have an always-visible
summary and link to their original correction owner. No duplicate cleanup
controls were created; existing Keep it / Let it go and previewed recovery
remain authoritative. This surfaces possible losses; it does not solve every
loss during palette reduction or make all difficult artwork stitchable.

Review results are collapsed to avoid displacing the canvas/player. Changing
a design invalidates its final comparison; late responses cannot replace the
current result or steal canvas focus. Existing empty/generating/blocked/ready
presentation and automatic finished-preview selection remain in place.
Local detail checks operate even with cloud review off or unavailable.

SQLite receipts in work/ai-reviews.sqlite3 reserve each design/source/stage/model/
version/plan identity before the paid request. Concurrent tabs, refreshes and
restarts reuse completed reviews. Pending requests are polled without a new call.
Failure/interruption needs explicit Retry, with a possible-charge warning.
Receipt text is stored locally without duplicate images. Rendering is skipped
for cache hits. There is no automatic paid retry, no key in browser storage,
and no new hosted multi-user authentication.

Verification: test_ai_workflow.py uses explicitly synthetic provider replies for
consent, budget readiness, schema rejection, caching, concurrency, native-text
exclusion, current-plan checks and actual-render input wiring.
browser_ai_workflow.py generates real stitches on disposable artwork; synthetic
AI replies test opt-in/off, thumbnail/detail actions, prompt preservation, stale
responses, error recovery, reload caching, keyboard and narrow/dark layouts.
These are integration evidence, not live-model accuracy or physical sew-out
evidence. Live provider validation after the app restart and real-design
fidelity/physical sew-outs remain required.

Acceptance checkpoint (2026-10-18): 514 unit tests passed; the new automatic-review
browser flow passed with two synthetic provider responses and zero paid calls,
including reload and Undo reuse, stale-response rejection, prompt preservation,
real generation/playback, narrow/dark layout and >=4.5:1 status contrast.
The existing digitization-results browser checks also passed (234 real stitches,
0 trims on the synthetic rectangle; blocked/error states remain distinguishable).
The workspace/browser-state suites passed after correcting stale test assumptions:
eight existing topics including AI, current image coordinate mapping, an outline
larger than the handle hit targets, and keyboard focus on the visible Borders
button rather than its hidden legacy duplicate. No product outline behavior was
changed to satisfy those tests. The strict static audit remains at 89 existing
findings (89 before, 89 after), not a clean audit. Running server still needs a
restart for the new route; no live GPT response or physical sew-out was verified.
