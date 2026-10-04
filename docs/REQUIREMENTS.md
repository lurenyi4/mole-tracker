# Product requirements and boundary

A private, offline, manual monthly photo journal for approximately 20–30 identified moles. It is not a medical device, diagnostic system, screening guarantee, melanin estimator, or risk score. New, changing, itching or bleeding spots should prompt professional advice without waiting for a monthly session. The monthly cadence is a workflow preference, not a clinical recommendation.

## Required acceptance behavior
- Stable non-reused mole ID, editable region/location and observation identity, retained correction history; newly recorded does not mean newly grown
- Dated monthly sessions, explicit coverage states and missing-mole list; missing coverage never means absence
- Import original JPEG/PNG safely without recompression; retain EXIF/ICC bytes, hash provenance, original-coordinate masks and immutable measurement snapshots
- Overview/location and regional-detail roles; one adequate regional image may serve multiple moles
- Manual polygons with exclusion areas, reference patch rectangles, explicit adjacent ordinary-skin selection; image review rejects comparisons with shadows, glare, blur, insufficient detail or unsuitable processing
- Color requires an explicitly supplied trustworthy multi-patch reference profile (D50, 2° XYZ) and supported encoded color space; no universal card values, no gray-only calibration
- Per-image linear RGB-to-XYZ 3×3 least squares and D50 Lab; median mole L*, normal-skin L*, D = skin minus mole; eligible longitudinal deltas only with matching methods and reference provenance
- Uncalibrated or unsuitable records remain useful as photos; no invented numbers or silent imputation. Retake guidance prominent
- Local explicit backup and validated restore, no upload; no encryption claim
- Cross-platform Python launch instructions; OS tests clearly separated from assumptions

## Deliberate first-version limits
No automatic lesion detector, automatic identity matching, registration, physical area/diameter estimation, calibrated clinical interpretation, mobile app, automatic photo acquisition, remote account, or background backup. Manual visual QC is mandatory; automated checks cannot certify absence of blur, local tone mapping or shadow. A real capture trial is needed to establish whether capture + import + review takes under one hour.
