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
