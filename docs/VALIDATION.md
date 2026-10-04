# Validation plan

## Automated gates
1. Red/green domain tests: stable IDs, persistence/reopen, correction audit, coverage and duplicate-month rejection
2. Red/green color tests: sRGB transfer function, known synthetic calibration, bad references/fit/rank, insufficient pixels and clipping, lesion changes retained under simulated global exposure/cast, independent skin change and no mucosal D
3. Safe imports: malformed/oversized files, originals byte-identical, paths not accepted from backups, hash validation, no overwrite restore
4. End-to-end synthetic workflow: session → import → ID → masks → measurement → second month → eligible deltas → correction → backup → restored reopen
5. Native GUI launch and smoke: import/select/mark/save/review and cancellation/repeated actions where display available

## Human gates not replaced by synthetic tests
- Windows and macOS launch/package and file-dialog checks
- Real card/device/lighting repeatability; reference profile provenance verified by owner
- Manual match verification, all-pose coverage, retake usability and privacy review
- Timed trial on 20–30 moles under 60 minutes; report completion and omissions, not only elapsed time
- Independent code review and scientific review before relying on color measurements

## Claims
Synthetic data establish numerical/software properties only. They do not establish clinical validity, real-camera color accuracy, detection of disease, capture-time performance or cross-platform packaging. QC constants are conservative engineering gates, not diagnostic thresholds. Every run and limitation belongs in WORK_LOG.md.
