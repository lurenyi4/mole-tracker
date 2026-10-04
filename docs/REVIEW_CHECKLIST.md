# Independent review handoff

Review the entire project, not only latest diff. Run `python -m unittest -v` and `python -m compileall -q moletracker tests`. With a real desktop, rerun tests and visually inspect native UI using generated fixtures only.

- [ ] Confirm the application has no network/telemetry/uploads/external assets; the source repository may have a GitHub remote, with journals, photos and secrets excluded
- [ ] Verify stable identities, correction audit, session/coverage semantics and no absence/new-growth claims
- [ ] Inspect import limits, preserved bytes/EXIF/ICC, original-coordinate geometry and path/backup validation
- [ ] Check explicit sRGB handling, linearization, D50/2° profile, least-squares math and L* formula
- [ ] Check training-fit/pixel refusal gates; distinguish mandatory human blur/shadow checks from automated detection
- [ ] Validate simulated color-cast recovery retains actual lesion change and independent skin change
- [ ] Try incomplete polygons, mask/profile edits, repeated saves/imports, interrupted saves, canceled dialogs and corrupted originals/backups
- [ ] Verify uncalibrated/retake records contain no fabricated measurements, non-ordinary skin omits D and profile/method mismatch suppresses deltas
- [ ] Verify one photo can serve several IDs without silently reusing target masks; map overview and detailed locations explicitly
- [ ] Try screenshot at smaller supported window sizes, CJK fonts, zoom/pan, history comparison and entire coverage route
- [ ] Inspect backup roundtrip and provenance; note archives are not encrypted or authenticated and should come from trusted local sources
- [ ] Distinguish historical Linux/Tk validation and the 2026-10-04 Windows UTF-8 test run from untested macOS and unsigned optional packaging
- [ ] Check docs acknowledge real card validation, real 20–30-mole timed trial and clinical validity remain unverified
- [ ] Explicit complete-record validation rejects null/missing/wrong-type masks; measurement-only validation cannot weaken persistence gates
- [ ] Reference wizard can import CSV/CGATS, map columns, reject wrong units/illuminant/observer, preview patch IDs, convert Lab/XYZ and save/use without editing JSON
- [ ] Physical-card source/model/version must be supplied and verified by owner; no synthetic or guessed commercial values presented as real
- [ ] Comparison failures clear all displayed results, failed month creation retains dirty protection, coverage remains scrollable with larger fonts and status remains visible
- [ ] Explicit null/malformed capture context rejects save/restore, while genuinely absent legacy context loads safely
- [ ] New-ID cancel, invalid input and storage failure retain current identity, masks, notes and dirty protection; success alone commits the transition
