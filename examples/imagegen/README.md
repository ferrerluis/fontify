# Image-generated Fontify Grotesk candidate

The letterforms were generated in **one built-in image_gen call** from the exact
prompt in `source/prompt.txt`. No Recraft request was made, and no model identifier
is invented: the built-in tool did not expose one. `source/alphabet-v1.png` is the
original, unchanged output; `source/provenance.json` records its hash and origin.

The generated sheet has A–Z, with black silhouettes on white. It is source artwork,
not a ready font. The bottom row was generated smaller; the reviewed crop plan
uses one explicit uniform scale for that row and another shared scale for the
first three rows. Each letter keeps its width/height ratio. A shared cap target
of 700 units, explicit baselines and 50-unit sidebearings set the font placement.
No per-letter stretching was used during tracing. The raw traced v0.001 is preserved
in `source/traced-v0.001/`. It is a tracing reference, not the finished example.
The main project is corrected v0.002; its explicit reflections, stem edits and local
curve patches are recorded in `quality-profile.json`, `source/local-patches.json`
and `corrections.json`.

## Offline build

```sh
fontify release examples/imagegen/fontify.json --out build
# Open build/FontifyGrotesk-Regular-v0.002/proof.html
```

This needs only the compiler dependencies. It never regenerates the AI image.
Coverage is exactly uppercase A–Z and space. The project has `approval: null`;
it remains a candidate for final human approval. Agent preflight has passed for
all 27 mappings; `agent-review.json` contains individual findings and links to the
saved actual-font sheets in `review-evidence/`. Compiling is not aesthetic approval.

## Reproduce the optional raster tracing

```sh
pip install -r examples/imagegen/requirements-trace.txt
python scripts/trace_generated_sheet.py examples/imagegen/source/trace-plan.json --out build/retrace-candidate
fontify build examples/imagegen/source/traced-v0.001/fontify.json --out build/raw-trace --draft
python scripts/review_generated_font.py examples/imagegen build/raw-trace/FontifyGrotesk-Regular-v0.001-draft/release-manifest.json --out build/imagegen-trace-review
```

Tracing checks the source hash and requires a new output directory. The explicit
crop boxes map letters to Unicode; no OCR or guessed missing letters is involved.
`turdsize=0` preserves small components; curve optimization is disabled. Potrace's
curve fitting still approximates pixels, so the output needs visual review.
The main compiler performs no raster tracing and has none of these dependencies.

`source-comparison.html` shows each raw crop beside an overlay with actual TTF
outlines. `source-comparison.json` records mask overlap at the original pixel
scale. This measures tracing fidelity; beauty, optical balance and smoothness
still need visual review.

## Reproduce corrections and internal review

```sh
fontify repair examples/imagegen/source/traced-v0.001/fontify-preflight.json --out build/repaired-v0.002 --version 0.002 --patches examples/imagegen/source/local-patches.json
fontify build build/repaired-v0.002/fontify.json --out build/repaired-drafts --draft
fontify audit build/repaired-v0.002/fontify.json --font build/repaired-drafts/FontifyGrotesk-Regular-v0.002-draft/FontifyGrotesk-Regular-v0.002.ttf --out build/repaired-audit
python scripts/render_quality_review.py build/raw-trace/FontifyGrotesk-Regular-v0.001-draft/FontifyGrotesk-Regular-v0.001.ttf build/repaired-drafts/FontifyGrotesk-Regular-v0.002-draft/FontifyGrotesk-Regular-v0.002.ttf --out build/repaired-v0.002/review-evidence
```

The checked-in corrections reproduce the final SVGs offline. The repair output
stays internal until a current complete review receipt exists. See
[the preflight guide](../../references/preflight.md) for the schema and gate.
Tracing overlap compares the **raw trace**, not subsequent editorial changes;
the latter have explicit bounds/area/topology budgets and individual review.

Eight internal iterations exposed rounding-induced export asymmetry, faceted
counters that passed numeric checks, and central notches introduced by mirroring
polygon letters. Corrections rounded named bowls/counters, made declared edges
exact, matched a 192-unit upright group and removed M/W/X notches. Source and
compiled audits pass; original image and traces remain unchanged. No Recraft
calls were used for these corrections.

The optional [Potracer authoring dependency](https://github.com/tatarize/potrace)
is GPL-2.0-or-later; no upstream tracer code is bundled. The MIT compiler's
runtime and vector-only builds do not depend on it. VTracer was evaluated first
but its installed Python 3.14 binding crashed; it was not used for these glyphs.

## Final approval

The agent inspected every glyph enlarged and at word sizes, including counters,
I/J distinction, S curves, Q's tail, diagonal proportions and shared stem weight.
These are review findings, not a claim of professional type-family certification.
Final style approval remains with the user. Further edits need a new version and
fresh review; capture an approval baseline only after that approval.
