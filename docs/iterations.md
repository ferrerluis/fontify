# Product iterations

## B01 · demo cap alignment and vertex spikes

- Reproduction: first demo (v1.000), open compiled-font proof; compare A/M/N/V/W
  extrema and stem baselines with H/T. Structural tests passed; the artwork was
  not visually consistent enough for the example.
- Affected acceptance: TC06.1; fixture changes invalidate TC01–TC04 evidence.
  TC05 provider/schema tests are unrelated and remain valid until changed.
- Cause: miter joins and butt caps in the demo's original centerline drawing
  recipe, not geometry transformations inside the compiler.
- Fix: explicit rounded joins and square caps in the authoring script, baseline
  placement updated, new 1.001 release and fresh demo regression snapshot.
  Preserve 1.000 output and produce `build/review-1.000-vs-1.001/comparison.html`.
- Required checks: rebuild example, rerun dependent checks, inspect 1.001 in the
  browser at the same scale. This is fixture review, not a claim of professional
  optical quality. General human review remains necessary.

## B02 · OS/2 metadata warning

- Reproduction: initial build logged that USE_TYPO_METRICS is undefined in OS/2
  version 3. Affected TC01.1/TC01.2; dependent compiled proofs need rebuilding.
- Fix: write OS/2 version 4, which defines that flag. Required checks: reopen
  TTF/WOFF2 and rerun offline export/reproducibility/shaping; no provider impact.

## B03 · curve bounds and proof overhangs

- Reproduction: a quadratic contour whose off-curve point extends beyond the
  visible ink can have a different TrueType xMin. Using tight ink xMin as hmtx
  left bearing translates the glyph in consumers; export verification rejects it.
  A glyph wider than its advance can also be clipped in a fixed proof canvas.
- Affected: new TC01.3 and TC06.2, with TC01.1/TC01.2 and TC06.1 dependent.
  Catalog v2 adds two required sub-tests (10 to 12); no previous requirements removed.
- Fix: use the actual TrueType control bounding box for the stored left bearing;
  measure ink separately. Bound proof canvases by actual ink, preserving a shared
  scale and origin. New unreviewed glyphs are also explicit in the proof status.
- Required checks: rebuild/reopen curves, measure generated proof path extents,
  rerun dependent checks and reload the browser proof. Provider tests are unaffected.

## B04 · showcase used a geometric fixture instead of generated design

- Reproduction: the user found Offline Sans visually poor and asked whether AI
  designed it. It was hand-coded geometry; no creative model had been called.
- Affected: primary example, README/skill workflow and TC06.1 browser evidence.
  The old fixture's structural TC01–TC05 checks remain valid; it is retained solely
  for engineering regressions. Catalog v3 adds TC07.1–TC07.3 (12 to 15 sub-tests).
- Fix: one built-in image_gen call creates a new candidate alphabet; freeze raw
  artwork and exact prompt, explicitly map crops and normalize shared row scales,
  trace without curve optimization, compile and compare against the source.
  `approval` stays null. The compiler's provider independence is unchanged.
- Tracing tool investigation: VTracer 0.6.15's native Python 3.14 binding exited
  with signal 11 for both pixel and encoded-image input. It was removed. The
  optional pure-Python Potracer path succeeded; no paid Recraft request was made.
- Required checks: generated example's cmap/metrics/shaping, source provenance,
  tracing reproduction/refusal to overwrite, per-glyph raster/compiled comparison,
  and browser proof. Human aesthetic approval remains outstanding.

## B05 · source comparison panels used different display scales

- Reproduction: comparison's source crop expanded to its box, while the overlay
  used the font coordinate frame, making the source appear larger despite matching
  outlines. Affects TC07.3 comparison evidence, not the font or other checks.
- Fix: both panels use identical viewBoxes and source-placement transforms.
  Add a regression assertion for every paired frame, rerun imagegen checks and
  visually verify the regenerated comparison. Source artwork/fonts stay unchanged.

## B06 · skill handed off defects before doing the design review

- Reproduction: generated v0.001 compiled and matched its raster source, yet
  intended symmetries, upright weight and 0/90-degree features were uneven.
  The user correctly required the Ferrer audit/correction work before first handoff.
- Affected: shared build path TC01–TC04, generated TC07, browser TC06.1, and new
  TC08.1–TC08.5. Catalog v4 adds five sub-tests (15 to 20); no old requirement removed.
- Fix: complete per-glyph intent, deterministic source/compiled audits, separate
  bounded corrections, actual-font close-ups and an all-glyph agent review receipt.
  `release` requires current passing evidence; drafts never advance `current.json`.
  Changes to glyphs, settings, spacing/kerning or proof bytes invalidate review.
- Required checks: missing/unsafe intent, bounded axes/diagonals, curve defects,
  approved-source protection, stale/incomplete/evidence gate refusal, final offline
  build and actual browser proof. The core still needs no generator or credentials.

## B07 · reflection was lost during quadratic export

- Reproduction: symmetric source curves passed source audits but exported C/D/O/U
  showed small reflected-area differences. Affects TC08.3 and generated release.
- Cause: decomposed quadratic splines introduce half-unit implied endpoints;
  independently rounding mirrored halves changes the final outlines.
- Fix: quantize the clipped master before reflection and preserve matching seams.
  Recheck the actual compiled TTF, not just source paths. Regression asserts exact
  declared reflection after export for curved and polygon examples.

## B08 · numeric passes missed facets and mirrored center notches

- Reproduction: enlarged internal sheets showed angular B/O counters, faceted
  curves and small notches in M/W/X after reflection. Tangent checks alone did
  not judge the shapes. Affects TC08 and generated review evidence TC06/TC07.
- Fix: sub-unit quadratic conversion avoids excessive short quantized segments;
  explicit named contour patches round bowls/counters, make G's bar exact and
  remove the three center notches. E/F/H/I/L/T/Y share an explicit 192-unit stem
  target. Original image/raw traces remain preserved; no approved glyph was changed.
- Eight internal iterations led to v0.002. Every glyph was inspected at common
  scale and word sizes; source/compiled audits pass. Journal records sampled
  changed area and bound movement; the maximum changed area is below the declared
  12% budget. This is agent preflight, not user approval or professional certification.
- Required checks: reproducible corrections from the frozen trace, all 27 review
  records/proof hashes, compilation/shaping and browser review. Broad whole-contour
  smoothing was not added to the compiler.

## B09 · vector paint and integer-collapse cleanup

- Reproduction: the first real Recraft SVG used dark filled outlines plus white
  shapes for counters. Treating those as one black drawing would fill holes.
  Ten glyphs also contained tiny edges that collapsed at TrueType rounding;
  the compiler correctly rejected the initial prepared B with a zero-length edge.
- Affected: new TC09.1/TC09.2. Catalog v5 adds two cases (20 to 22 sub-tests).
- Fix: a separate offline helper maps explicit rows/components, subtracts painted
  counters, retains i/j dots and applies one common scale. Only edges whose
  controls all round to one point are joined locally. No raster tracing, curve
  fitting or implicit compiler repair was added; original SVG stays unchanged.
- Required checks: exact frozen extraction, 53 mappings, separate dots, source
  hash/overwrite guards, offline font compilation and preserved source evidence.

## B10 · a smooth wide hook was misclassified as a cusp

- Reproduction: Recraft g's ear is smooth, but its endpoint tangent exceeds 100
  degrees relative to the chord. The earlier heuristic called that a cusp.
- Affected: TC08.3 and every gated build. Fix: evaluate the derivative for an
  interior stationary tangent reversal; unexpected reversals at joins are also
  flagged. Tests retain genuine cubic/quadratic cusps and reject the false positive.
- Required checks: curve regressions plus all dependent gated/offline builds.

## B11 · geometric corrections damaged a handwritten design

- Reproduction: the first Mellow profile assumed exact X reflection. The 24.33%
  filled-area difference exceeded the guard, so repair stopped. A later numeric
  pass visibly pinched/jogged I/i/l caps or dots. The user also explicitly asked
  to preserve intentional curvature rather than force straightness.
- Affected: TC08.2/TC08.3, TC09 and visual review. Fix: declare axis features for
  organic styles; retain geometric defaults for existing profiles. Reject the X
  assumption and revert I/i/l edits after actual-font comparison. Both rejected
  profiles are preserved; no approval baseline was reset.
- Final Mellow changes only H, Z and q. The other 49 exported letter outlines
  match the first sample exactly. Topology/cusp/coverage/metrics/shaping and every
  glyph's visual checks still apply. Required checks: intentional lean remains,
  named axes still become exact, bounded edits and before/after inspection.

## B12 · lowercase descenders exceeded review-sheet rows

- Reproduction: enlarged g/j/p/q/y overlapped the next row or were cropped by the
  fixed-height comparison renderer. Fonts themselves were valid.
- Affected: TC06.2 and visual proof evidence. Fix: derive shared baseline and row
  height from both actual font bounds. Sample text is also fit at one common size
  to both fonts; labels support vector inputs instead of assuming raster traces.
- Required checks: every glyph included, both rows have clear bottom margins,
  full descenders visible and final mixed-case browser proof inspected.

## B13 · source formatting was presented as a changed shape

- Reproduction: Mellow's normalized SVG records all changed, although only three
  actual exported glyph outlines differed. A generic CHANGED label obscured this.
- Affected: TC04.2 and final comparison evidence. Fix: retain conservative record
  change reporting while separately reporting exported outlines, mapping/advance
  changes and source-only refreshes. The heading no longer implies an unapproved
  source was approved. Required checks: source-only whitespace edit and a real
  outline edit produce different categories; final Mellow comparison reports H/Z/q.

## B14 · proof still said pending after adding an approved baseline

- Reproduction: gated releases hard-coded user design approval pending even when
  an approval baseline matched. Found while archiving the user's approved Mellow.
- Affected: new TC04.3 and browser TC06.1; catalog v6 has 23 required sub-tests.
- Fix: show glyph baseline matches for that exact state; retain pending for
  projects without a complete matching baseline. Do not infer aesthetic quality
  from a fingerprint match. Required checks: font bytes unchanged, protection
  active, proof label accurate and human review still distinguished.
