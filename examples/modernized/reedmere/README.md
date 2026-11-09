# Reedmere · Broad hand-ink headlines

A broad, heavy hand-ink display face with blunt nib endings, softly squared bowls and an uneven written rhythm. Suited to expressive headlines, packaging and identity lettering.

![Reedmere final TTF preview](preview.png)

## Story and inspiration

Papyrus supplies the calligraphic and material ancestry. The selected current A raster, after its uppercase I whole-sheet correction, takes a broader and bolder direction. Its 52 letters were traced with protected counters and components; recorded cleanup, optical spacing and authored Latin companions turn the selected drawing into a usable display font. The whole-sheet edit and its collateral changes remain disclosed.

Historical inspiration: **Papyrus**, selection **A**. This is independent new artwork, not an official revival or an endorsed product. Openai raster followed by documented tracing and cleanup. Authored extensions and same-family composites are documented in the full production package; no commercial font software is bundled.

## Use the exact final fonts

- Desktop font: [`Reedmere-Regular-v0.025.ttf`](fonts/Reedmere-Regular-v0.025.ttf).
- Web font: [`Reedmere-Regular-v0.025.woff2`](fonts/Reedmere-Regular-v0.025.woff2) and [font.css](font.css).
- Open [specimen.html](specimen.html) for a live final-WOFF2 specimen and complete inventory.
- Version **0.025**, **354 mappings**: the full 354-codepoint union. [coverage.csv](coverage.csv) lists names, glyphs and advances from the actual TTF.
- Display minimum **48px**; use sufficient line height. These are static Regular display fonts.

## Provenance, construction and validation

[provenance.json](provenance.json) records the exact local final package, source path/hash, manifest verification and pinned production commit. [metadata.json](metadata.json) binds both final font hashes. The integrated fonts are byte-identical copies; no rebuilding or outline editing was done for integration. `preview.png` is a fresh actual-TTF raster at its recorded sizes; `specimen.html` loads the supplied WOFF2. Neither is a concept/A/B/C review image.

Documented project-local compatibility adapter runs the pinned Fontify compiler and gated review; plain JSON CLI cannot directly admit blank NBSP/zero-advance marks. Producer source-stage, compiled and release records are distinct from the integration binary checks.

The full editable sources, original artwork, tracing/native-vector decisions, authored extension records, compatibility scripts and complete proofs remain in the named local production package. This compact sample is an artifact-use example, not a self-contained source-rebuild fixture. Read [the preserved production notes](provenance/production-notes.txt) for the package's reproduction entry point and evidence scope. Those notes describe the production handoff at that time; the present integration is separately authorized. Rebuild only into a fresh directory using its pinned environment and recheck any new bytes. Do not substitute an older intermediate from the package.

Run `python scripts/verify_modernized_samples.py` from the repository root with existing Fontify dependencies. It validates hashes, exact coverage including extras, all TTF/WOFF2 outlines and metrics, layout-table equivalence, real canonical/mixed shaping and whitespace semantics. This integration check is separate from producer source-stage gates and from human aesthetic approval.

## Bounded limitations

- Display use from 48px; body text and smaller sizes are not certified.
- Exact listed coverage and documented language/one- or two-mark samples only. Arbitrary accent stacks, every Latin orthography and every rendering engine are not certified.
- Static Regular TTF/WOFF2 only; no CFF OTF, variable axes or additional styles.
- Monochrome outlines retain edge personality, not grayscale ink shading.
- 56 explicit core kerning pairs; extended spacing is reviewed without an exhaustive extended-pair claim.

## Review and distribution status

Current final package cleared in integration handoff. Final human aesthetic approval remains pending. Source provenance and distribution terms need owner review. No new MIT license is assigned to these font assets; the repository's existing compiler/code license is unchanged. Local integration does not authorize upload, publication or redistribution. No generation, paid call, installation or credential creation was performed here.
