# Work log

## Plan and criteria
- Phase 1: requirements, capture and validation documents; local repository only
- Phase 2: test-first durable local storage and experimental color core; integrity and refusal tests
- Phase 3: native end-to-end desktop workflow; explicit coverage, editable masks, comparison and local backup/restore
- Phase 4: synthetic integration and GUI smoke, cross-platform instructions and independent review handoff

All production line growth must support a listed requirement; prefer standard library/Tk/SQLite and two image/math dependencies over a server/framework. No ADR changes, no remote configured, no real medical photos.

## Phase 1
Created requirements, capture protocol and validation boundaries before implementation. Chose native Tk to avoid network attack surface and external assets. Dependencies already present in this Linux runtime: Python tkinter (Tk 9), Pillow 12.3.0 and NumPy 2.3.5. No tests run yet. No inherited applicable AGENTS.md found in workspace ancestry; other projects untouched.

## Open validation
Real user trial, clinical/scientific review, actual Windows/macOS execution, real reference-card selection and validation. GUI availability being investigated.

## Phase 2: test-first core
- Red: `python -m unittest -v` failed as expected before modules existed (ModuleNotFoundError)
- Implemented local SQLite identity/session/coverage/audit, byte-preserving content-addressed originals, bounded image decoding and portable integrity-checked backups restored only into new directories
- Implemented explicit sRGB/ICC handling, sRGB decoding, 3×3 least squares, D50 L*, polygon/exclusion masks, pixel/fit gates, independent mole/skin measurements and version/profile-gated deltas
- First green run caught a SQL placeholder-count defect; fixed and reran all 8 tests successfully
- Tests cover synthetic global cast recovery, preserved lesion change, independently changing skin, no non-ordinary skin D, invalid profiles/rank/masks, clipping and too few pixels, identity correction, missing coverage, import, persistence and backup roundtrip
- Production growth: two core modules, ~440 lines, for storage/integrity and testable color behavior. No server or framework added

## Phase 3: native Chinese desktop and integration
- Added native Chinese three-tab workflow: monthly import/ID selection, original-coordinate zoom/pan polygon and exclusion editing, ordered color-card rectangles, explicit sRGB assumption and manual QC, versioned observations, identity correction, side-by-side history, coverage and explicit local backup/restore
- Added source launch/package instructions and a synthetic geometric demo generator; no real photographs or actual-card reference values included
- Extended TDD: repeated import/save and tampered-original tests first failed, then added idempotency and read-time original hash validation. Added transaction-abort rollback/retry, immutable measurement snapshots after mask/profile edits, failed-backup nonpublication and no-overwrite tests
- Shell-only `python -m unittest -v`: 18 tests, 17 passed and GUI test explicitly skipped without DISPLAY. `compileall` passed
- A shell dummy-display attempt could not create sockets; apt setup was unavailable. No system settings changed. Existing cloud desktop subsequently worked through CUA terminal and shared workspace, without creating another server
- Actual desktop `python -m unittest -v` initially passed all 13 then-existing tests including native widgets. Visual QA found incorrect CJK rendering with bundled Tk 9 and clipped lower controls. Selected installed CJK fonts, used system Python/Tk 8.6 and adjusted requested canvas/list sizing; visual QA then confirmed legible Chinese controls and visible save/import buttons at 1180×812
- Visual QA exercised selection, two-month comparison, original mask reload and reset QC. Synthetic mole L* +8.32, skin +0.00, D −8.32 displayed correctly; numbers describe generated squares only
- Production growth: ~460 UI lines plus launch files for the complete manual workflow, no HTTP server or background process. Cross-platform native packaging and real capture trial remain unrun

## Phase 4: final verification and review handoff
- Final native desktop command: `/usr/bin/python -m unittest -v` through the existing CUA desktop terminal: **18 tests passed, zero skips, 0.534 s**. System Python is 3.13.5 / Tk 8.6 / Pillow 11.1.0 / NumPy 2.2.4. Historical raw test output was removed during the 2026-10-04 repository cleanup; this summary remains.
- `python -m compileall -q moletracker tests`: passed
- `python -m pip wheel --no-deps --no-build-isolation --no-index . -w /tmp/mole-wheels`: passed, created moletracker_local-0.1.0-py3-none-any.whl. This checks Python packaging only, not a signed/native executable or another OS
- `git diff --check`: passed. `git remote -v`: empty. Local author configured as requested
- Production Python: 804 lines across app, storage, color and package entry point; tests: 304 lines. UI work added ~393 lines for explicit manual workflow, while storage/measurement remain independently testable. No ADRs or existing projects changed
- Final source frozen for fresh independent whole-project review. Outstanding: Windows/macOS execution and native packages, real physical-card selection and accuracy/repeatability, real 20–30-mole under-hour capture trial, independent scientific/clinical validation. App remains a non-diagnostic prototype

## Independent review repair cycle
Fresh full-project review blocked C1 and M1–M5. Added regression tests before changes. Shell regression run failed on degenerate references, absent provenance, invalid restore relationships, asymmetric backup limits and corrupted-original reuse. Native Tk regression run separately failed on atomic image selection and assumption leakage (red evidence retained).

Fixes:
- C1: validate target XYZ rank/condition/luminance spread and fitted-transform rank/condition/luminance mapping; zero, grayscale and collapsed references fail closed while valid change-preservation tests still pass
- M1: decode/render before committing photo/session selection, roll back canvas state on load errors, retain editor state and selection on failure; all observation writes recheck original integrity
- M2 / reuse gate: added one domain-focused authoritative validation module shared by save, restore, backup and comparison eligibility. Validates required provenance, refitted matrix/hash, manual QC, tissue/source, finite consistent measurements and original-coordinate geometry/photo relationships
- M3: writer and reader share uncompressed/member/manifest/record limits; limits are preflighted before publication. Boundary, compressed-vs-uncompressed, manifest growth and record-count tests included. Limits and actionable offline-directory backup guidance documented
- M4: source/tissue defaults reset for new observations; photo-only snapshots save explicit capture context; history restores its own context with QC cleared. Profile changes clear correspondence confirmation and patch rectangles
- M5: every existing content-addressed destination is checked before reuse across months or roles; mismatch rejects without inserting a row

Verification after fixes:
- Full actual Linux native desktop `/usr/bin/python -m unittest -v`: **26 passed, zero skipped, 0.830 s**, including failed-select and failed-history-load/retry, assumption/profile transitions and earlier native workflow
- Shell suite: 23 passed, 3 native-only skipped; compileall and diff whitespace checks passed
- Additional production growth is limited to the shared validator and explicit transactional UI/error boundaries; no framework or parallel validator implementations added. No remote, ADR or unrelated project changes
- Source prepared for a new independent focused AND whole-project review. Existing real-card, real-device, medical, timing and Windows/macOS validation limitations remain unchanged

## Second independent review repair cycle
Reproduced R1 null-mask save/restore bypass with new regression tests before changing validator contexts. Reproduced R3 stale comparison and R4 failed-new-month dirty loss with failing real native tests; evidence retained. Added reference-import tests before the importer existed (expected import failure).

- R1: complete-record validator now has mandatory masks/photo/session arguments; masks must be a dictionary and comparable geometry is always enforced. Explicit measurement-only validation is separately named and used only for delta snapshots, sharing the same numerical/provenance checks
- R2: added a small offline CSV/CGATS parser/converter and Chinese setup wizard. Owner supplies exact manufacturer/model/edition/source/layout, confirms D50/2° and units, maps columns, previews patch labels/XYZ, then saves/uses a local profile without hand-writing JSON. Supports D50 Lab inverse conversion and XYZ 0–100/0–1; no guessed adaptation or commercial values. Source file hash and import provenance are saved. Added no-code walkthrough and primary-source support pointers with explicit 502/403 access limitations; no commercial dataset downloaded or bundled
- R3: comparison stages both previews and summary; any original failure clears the full panel with unavailable status, and retry works
- R4: discard confirmation is side-effect-free; dirty state changes only when a successful transition resets editor state. Invalid/duplicate month and simulated storage-failure regressions pass
- R5: bottom status gets reserved layout space; coverage is explicitly scrollable. Exact 1100×760 content-window regression (override-redirect only in test, because cloud window manager otherwise forces 1180×812) verifies status and coverage scrolling with 17-point fonts
- Native visual inspection found the first wizard preview behind its container; corrected its parent and rechecked visible patch-label/XYZ preview, fields and save controls. No real card or medical photo used

Final verification: actual desktop `/usr/bin/python -m unittest -v`: **33 passed, zero skips, 1.346 s**. Includes reference wizard → saved profile → measured synthetic observation, null masks, both failed comparison originals/retry, invalid/duplicate/storage-failure month transitions and minimum-size/large-font coverage. Final shell suite, compileall, whitespace check and offline wheel build also rerun. Red/green native evidence committed. Added production code is the small importer and wizard plus explicit validation/UI state fixes; existing Tk/SQLite/Pillow/NumPy stack retained, no framework or network code.

Actual physical-card model/reference selection and source verification still must be performed by the owner; the workflow is now supplied but no real-card calibration claim is made. Real-device repeatability, timed 20–30-mole capture, medical validity and Windows/macOS/native packaging remain unverified. Source frozen for another independent review.

## Third independent review repair cycle
Added regressions first and reproduced numeric D65 accepted as D50, duplicate declaration override and malformed falsey photo-only shapes. Red evidence retained.

- F1: one source-metadata normalization/consistency function checks named and numeric white points, observer, declared CIE representation, conventional selected column semantics/order and explicit units. Numeric white points normalize by Y, accepting rounded D50 at different scales and rejecting D65/zero/nonfinite values. Conflicting duplicate declarations are rejected; repeatable KEYWORD declarations are distinguished. CTI3 XYZ requires Y=100; display/absolute/unsupported relevant condition metadata is rejected. Generic CSV remains explicitly mapped/confirmed. Generated profiles recheck their source metadata on use, preventing a saved-profile bypass. Supported subset and limitations documented against the official Argyll format reference; no adaptation, guessed card values or new dependencies
- F2: existing shared geometry validator now requires list structure for every present region/exclusion/reference field, finite numeric coordinate lists and no boolean coordinates, for all statuses. Empty/missing optional lists remain valid photo-only records. Wrong-type save/restore cases fail without publishing a restored destination

Final native verification: 36 tests passed, zero skipped (exact output retained). Shell suite: 30 passed, six GUI skips. Compileall, whitespace check and offline wheel build rerun. Production growth is limited to the one metadata gate and stricter existing geometry checks. No remote, unrelated project edits or physical/clinical validation claims. Ready for fresh focused plus entire-project review.

## Fourth independent review repair cycle
No major/critic findings in the preceding review; fixed its two minor consistency issues before release. Regression-first evidence reproduced explicit null capture context acceptance and native new-ID cancellation clearing unsaved masks.

- Q1: shared complete-record validation distinguishes a missing legacy capture_context from an explicitly present invalid value. Null, wrong types and malformed values now reject saves/restores, with no restored directory published. Native legacy-absence load confirms normal defaults without inventing stored context
- Q2: new-ID dialog leaves masks, notes, dirty protection and current identity untouched while open, on cancel, invalid input and simulated database failure. Reset and selection commit happen only after the new ID is successfully created. Native tests exercise all four outcomes using the actual dialog controls

Final actual native desktop suite: **39 passed, zero skipped, 1.812 s**. Shell: 31 passed, eight GUI skips. Compileall, diff whitespace and offline wheel build passed. Documentation reviewed: no changed product/privacy/medical claims are needed; physical-card/source verification, real-world accuracy/timing and Windows/macOS/native packaging remain unverified. Production change is 16 touched lines across the existing shared validator and existing dialog transition, with no new abstraction or dependency. Red/green evidence retained. Source frozen for fresh whole-project review.

## Final software acceptance and source delivery
Final independent gate on behavior revision `b253bf3e260280b06ed2fa50ea32918d6ee42dfe`: **PASS** focused repair verification and entire-project review, covering both software Spec and Standards. No outstanding blocker, critic/major finding or mandatory simplification. Independent existing-desktop run: **39 passed, zero skipped, 2.269 s**; shell: 31 passed, eight explicit display skips. Fresh 1100×760 visual inspection confirmed editor actions, coverage guidance and privacy/status line. Historical raw test output was removed during the 2026-10-04 repository cleanup; this summary remains.

Reviewed all product, capture, color, reference, validation, review and launch documentation for delivery. Added a Chinese quickstart and release boundaries, and clarified that Windows/macOS instructions are not actual OS validation. This closure changes documentation only; no production behavior, dependencies or ADRs changed.

Deliverable is a tracked-files-only source ZIP, with tests and synthetic generator, excluding Git history, caches, virtual environments, generated images, journals and user data. Local Git remains the rollback record; no remote is configured and nothing is published externally. Source archive integrity/content and an extracted shell test run are checked before handoff.

Still unverified: owner's actual card/model/reference authentication, real phone/card/light repeatability and precision, clinical usefulness, real 20–30-mole under-hour completion, Windows/macOS execution and signed native distributions. Application-level encryption is not implemented; documented archive limits remain. These are retained setup/validation boundaries, not claims of completed testing.

## 2026-10-04 repository cleanup and GitHub preparation

The sections above describe the original Linux source delivery and its historical reviews. This extracted source directory contained no Git history. The owner requested removal of generated artifacts and upload to a public GitHub repository.

- Retain application source, test source, synthetic generator, requirements and project documentation. Do not change application/test behavior or ADRs.
- Move `.venv/`, `moletracker/__pycache__/` and 11 historical output files under `docs/test-evidence/` to the Windows Recycle Bin. Old red/green output mentioned above is no longer distributed; historical summary claims are retained as historical records.
- Preserve the local `MoleJournal/` database and exclude it from Git, along with tool/test caches and local secrets. No photos or database files are part of the upload.
- Windows validation before removing the virtual environment: Python 3.13, Pillow 12.3.0, NumPy 2.3.5; `python -B -X utf8 -m unittest -v`: 39 passed, zero skipped, 4.217 s. Without UTF-8 mode one GUI test raises `UnicodeDecodeError` while reading its generated JSON under default GBK; documented the UTF-8 command without changing code.
- Update launch paths and current verification boundaries. No fresh independent code-review claim is made for this documentation/file-management task. Recreate `.venv` from requirements before running the application again.
