# Experimental color method v1

## Explicit prerequisites
A trustworthy physical matte multi-patch reference, its actual manufacturer/measured values and provenance, D50 illuminant and 2° observer. The user has not selected a real card. No commercial-card values are bundled. No claim that a gray patch or arbitrary printed chart is sufficient. The generated demo profile is synthetic test data only.

Profile JSON fields:
- `name`: actual card/profile identity and edition/batch if known
- `source`: manufacturer measurement document, measurement protocol or other trustworthy reference provenance
- `white`: exactly `D50`
- `observer`: `2`
- `xyz`: at least six corresponding `[X,Y,Z]` triples with Y=1 scale (not 0–100); entries in the same order as manually marked patch rectangles

Never copy universal invented patch values. If values are given in another illuminant/observer/space, do not merely change the label; obtain appropriately measured or professionally converted reference data. Metadata validity cannot verify physical authenticity. The operator must confirm profile/card correspondence.

## Pipeline and provenance
1. Originals are stored byte-for-byte, with their EXIF/ICC. Analysis uses an independent copy of the original unrotated raster. Masks/patch rectangles persist in original coordinates, not scaled canvas coordinates
2. Embedded ICC is converted using Pillow/LittleCMS into encoded sRGB. An EXIF sRGB declaration can be used; untagged images require an explicit user sRGB assumption. Unknown/broken profiles and non-RGB/transparent analysis are rejected. Display images are previews, not calibrated monitors
3. Per-patch median encoded RGB is decoded using the piecewise sRGB transfer function into linear RGB. Fit a zero-offset 3×3 least-squares matrix from these samples to supplied D50 XYZ
4. Reject too few patches, insufficient rank, matrix condition >100, clipping and training XYZ RMSE >0.025 (XYZ Y=1). These are engineering refusal gates, not validated accuracy bounds. In-sample residual does not establish real-world generalization, spectral fidelity or repeatability
5. Transform selected original-coordinate pixels and compute CIE L* from normalized Y with the CIE piecewise formula. The fixed D50 reference white is [0.96422,1,0.82521]. Only L* is reported, not a*/b*, melanin content or a diagnostic score
6. Report median mole L*, median adjacent comparable normal-skin L*, D = skin L* − mole L*. A minimum 100 retained pixels is required per ordinary-skin region. More than 1% of selected pixels with any channel ≤2/255 or ≥253/255 is rejected. Thresholds are engineering heuristics
7. Non-ordinary-skin mode (including mucosal/nail regions) omits skin L* and D, retaining only experimental target L*. The app does not infer tissue type; operator selection is required
8. Each measurement snapshots method/version, full profile and hash, patch RGB, fitted matrix/residual/condition, color-space provenance, pixel counts and manual QC. Edits produce a new snapshot. Deltas require matching method/profile hash/ordinary-skin mode; equal identifiers do not prove the photos are comparable

## Mandatory human checks
The UI requires visual confirmation of sufficient sharp detail, no local shadow/glare/clipping/obvious HDR, matched reference geometry/light and correct identity/masks. Manual exclusion masks remove hair, reflections and lesion edges. Automated checks do not reliably detect blur or local tone mapping. A smooth mole cannot be classified as blurred from texture alone. Bad pictures should be reshot; storing an explicitly uncalibrated/retake record never produces a comparable result.

A card cannot undo arbitrary phone processing, spectral differences, local illumination or shadows. Same phone/lens/mode and fixed lighting are strongly recommended; changing them can invalidate comparisons despite an acceptable fit. Adjacent skin may independently tan/inflame/change: read both L* values and D. No clinical delta threshold exists in this application.

## Synthetic tests and remaining work
Known linear transforms, encoded/linear handling, cast/exposure recovery and deliberately changed lesion/skin values are tested. The transformation uses reference patches only, so a true simulated lesion change survives correction. Synthetic tests do not validate real-camera accuracy, phone HDR, shadow correction, specific commercial cards, time-to-capture or clinical interpretation. Out-of-sample reference validation and device/card repeatability studies remain prerequisites to stronger claims.

## Review hardening
Both observed RGB and target XYZ must have rank 3 and condition number ≤100. The reference must span at least 0.05 in Y and reach Y≥0.1 (Y=1 scale). The fitted transform must be full-rank, condition ≤100, and have a non-collapsed luminance column. These conservative engineering gates reject zero/grayscale/collapsed references; they do not authenticate a card or establish color accuracy.

A shared observation validator checks saved, restored and compared measurement snapshots. Required provenance includes the supported method, recomputable profile/hash/fit, finite consistent L*/D, explicit tissue mode, color-space source, pixel counts and four affirmative manual-QC flags. Save/restore additionally enforce photo/month/role consistency and bounded original-coordinate masks matching pixel counts and reference rectangles. Incomplete legacy snapshots cannot produce deltas; invalid backup records are rejected, not silently repaired or assigned invented provenance.

The native reference wizard now accepts vendor CSV/CGATS with explicit D50/2° Lab or XYZ units; see [the no-code setup walkthrough](REFERENCE_SETUP.md). It preserves source identity, file hash, selected columns and patch labels. Lab conversion uses the inverse CIE piecewise formula; XYZ Y=100 is explicitly rescaled. No non-D50 chromatic adaptation is attempted. Unknown physical-card model/source remains a setup prerequisite, not a default chosen by the app.

Complete persisted-observation validation now requires explicit masks/photo/session arguments with no nullable geometry shortcut. A separately named measurement-only validator supports delta math and shares the measurement checks; it cannot admit an observation to storage. Null/missing/wrong-type/empty comparable geometry is rejected during save or restore.
