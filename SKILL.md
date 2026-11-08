---
name: fontify
description: Create fonts from a typeface concept or supplied vectors with Fontify. Choose style-aware decision rubrics, run deterministic checks and bounded corrections, then review every glyph before presenting the first font. Recraft is optional; construction runs offline.
---

# Fontify

This repository is both a Python library and an installable skill folder. Work
from its root after installing it with `pip install -e '.[dev,proof]'`. Use the actual
CLI/library in `src/fontify/`; don't replace it with a fresh font-building script.
Examples and commands are in [README.md](README.md).

## Start with evidence

- Inspect the intended project's source manifest, current release pointer,
  compiled version/coverage and approved baseline. An old root README or build
  script may describe a different revision. Verify artifact hashes with
  `fontify verify-release` before comparison.
- Identify exact required characters and intended use. A wordmark provides only
  its known letters; missing letters/lowercase are new designs, not recovered
  originals. Do not promise a complete character set from an alphabet image.
- If building from prior work, keep that project read-only unless the user asks
  to change it. [Ferrer lessons](docs/ferrer-lessons.md) explain actual failure
  modes that motivated these checks; the example does not depend on Ferrer files.

## Separate drawing from construction

Read [generation-routing.md](references/generation-routing.md) before choosing a
generation method. Inspect the references and requested letterform qualities;
decide whether a native-vector model is appropriate to try at all. Vector access
alone is not a reason to use it. Use image generation directly when it better fits
the brief. Preserve supplied artwork and explicit provider or source restrictions.

If trying vector generation, run **one pilot iteration**, with **one output (`n=1`)**,
even when several design options were requested. Inspect that output against the
actual prompt and references before further option work. If it passes, continue
the requested vector options within the existing approval and budget. If it is
**systemically off**, preserve the evidence and fall back to image generation
within the user's authorization; do not spend more vector iterations trying to
rescue the same brief. A successful SVG response is not prompt compliance.

For a Recraft trial, prefer Vector Pro (`recraftv4_1_pro_vector`). Use non-Pro
Recraft Vector only when the user explicitly requests it or Pro is confirmed
unavailable; record the concrete reason before choosing that model. This model
preference applies only after choosing the vector route, not to every new concept.
Hand-coded geometric letters are engineering fixtures, not a substitute for this creative
workflow. The primary runnable example is `examples/imagegen/`; its frozen SVGs
compile offline. `examples/offline/` remains a synthetic regression fixture.

When the brief favors raster artwork, the vector trial is systemically off,
Recraft is unavailable, or the user chooses image generation, use the
built-in image-generation tool for the concept sheet
without inventing an API key requirement. Preserve its original output and exact
prompt. Review explicit letter crops, baselines and common scaling, then use the
optional tracing helper from [the imagegen example](examples/imagegen/README.md).
Compare the actual compiled font against the generated source; a high pixel
overlap does not establish visual quality. Never label an unapproved design as approved.
When the user is choosing among concepts, wait for their selection before cleanup,
tracing or font construction. Liking an option is not selecting or approving it.

**Keep vector sources vector.** Recraft vector output and supplied SVGs go directly
through the vector extraction/outline path. Never rasterize them for cleanup or
tracing. Only bitmap inputs use `fontify trace-sheet`; read
[raster-preparation.md](references/raster-preparation.md) for opt-in guide masks,
component decisions and recorded resampling. Preserve dots, accents, punctuation
and texture deliberately. Inspect original/cleaned/resampled masks before accepting
a trace. Scaling a bitmap is not recovered detail, and 3x is not a universal rule.
Final-font raster previews are display QA, not conversion of vector source artwork.

Read [project-format.md](references/project-format.md) when mapping outlines or
metrics. Set one Unicode scalar and explicit advance for each glyph. Keep space
blank. Inspect coordinate convention and placement before interpreting clipping
or sidebearing warnings. Don't normalize each letter's width/height independently.

For Recraft, read [recraft.md](references/recraft.md) and pass the Pro vector model
explicitly in MCP calls and request plans. Never omit the model and rely on the
service default. Price, latency, missing spend approval, authentication failures,
rate limits or insufficient credits alone do not establish Pro unavailability.
Prefer configured MCP access for exploration, discover its actual `inputSchema`, and
don't assume REST fields fit MCP. A reusable application uses the optional
server-side adapter. First produce a dry request plan. Obtain user authorization
before a paid call, credential creation or purchase; never infer it from general
font-building approval. No Recraft access is needed for build, tests or preview.

## Establish spacing before pair kerning

Read [spacing.md](references/spacing.md). Use `fontify spacing-plan` to measure
vector white areas by declared reference zones and depth limits, then review
bearings, advances, pair candidates and collision guards. Apply a reviewed plan
with `fontify spacing-apply` to a fresh versioned candidate. Do not treat a shared
40/50-unit bearing, crop width, or successful GPOS encoding as optical spacing.
Resolve group/style overrides and existing pairs explicitly; inspect words and
pairs with kerning on/off. Spacing never stretches glyphs or rasterizes vectors.
Retain original and approved sources. Recheck glyph intent and proofs after any
placement/advance change. Keep GPOS kerning; do not replace it with legacy kern
merely to reproduce an example pipeline.

## Finish preflight before presenting the first font

Read [style-rubrics.md](references/style-rubrics.md) for the executable decision
trees and internal correction loop. Use schema 3 for new work; existing schema-1/2
projects keep their frozen profiles until deliberately migrated. Read
[size-proofing.md](references/size-proofing.md) and declare text or display use,
fixed proof sizes, the minimum supported size, and the rationale. Read [preflight.md](references/preflight.md)
for detailed receipt fields and local patches. Do this work autonomously; the user should receive
a corrected, reviewed first candidate, not become the first defect finder.

1. Preserve the original artwork, trace, approved baseline and release. Work in
   a new unapproved candidate (`approval: null`). Never reset a baseline just to
   silence drift. Approved glyphs need separate, explicit proposed edits.
2. Choose the rubric strategy from the brief: geometric, humanist, handwritten,
   serif, or display/mixed. Run `fontify rubric-plan` with the style and a concrete
   rationale, plus `--intended-use text` or `--intended-use display` and the
   appropriate size options. Inspect **every** ink glyph before confirming its decisions; a
   preset is a recommendation, not inferred intent or approval. Declare exact
   reflection axes, intentional corners, selected straight features and any
   measured stem probes. Preserve optical asymmetry and variable strokes where
   intended. Unresolved intent blocks correction and presentation.
3. Use `fontify preflight <project> --out <fresh-pass-dir>`. Enable only appropriate
   per-glyph repairs, then use `--repair-version <new-version>` for a bounded
   candidate correction; explicit contour patches also need `patches` permission.
   Numeric findings do not authorize edits by themselves. Exact 0/90-degree checks
   apply to intended axial features; preserve genuine diagonals, lean and curved
   uprights. Fix kinks, facets, cusps, counters and weight locally. Never smooth,
   thin or stretch the alphabet to improve a score.
4. The pass compiles internal drafts, reopens TTF/WOFF2 and checks real HarfBuzz
   shaping, then reruns the audit on the actual TTF: export can reintroduce defects.
   Read `preflight.json` and its routed check reasons/results. `blocked` needs
   internal correction; `needs_visual_review` is not permission to present a font.
   Drafts never update `current.json`.
5. **Inspect every letter visually** enlarged and at every declared fixed proof
   size, at a common scale/baseline, plus actual shaped words and pair samples
   with kerning on/off. For text fonts include 12, 16, 24 and 48 pixels. Display
   fonts can declare a higher minimum with a concrete rationale. Use actual TTF
   raster proofs and browser-loaded WOFF2 screenshots, never resized large proofs
   or fallback fonts. Run `fontify capture-size-proofs` for the generated size
   proof HTML; record renderer, font/proof hashes, device scale and findings.
   Inspect covered confusables, detached marks, punctuation and mixed-case words.
   Generated/captured evidence is pending inspection, not automatically approved.
   Check all curves and straight features, symmetry, optical weight, contours,
   spacing and source preservation. Review blank space too. Use actual-font
   before/after sheets (`scripts/render_quality_review.py`) and overlays; a
   numeric pass or high tracing overlap is insufficient.
6. Repeat correction, export, audit and visual review until no identified defect
   remains. A numeric pass that looks worse must be rejected and reverted; inspect
   changes below the budget too. Preserve iteration findings and evidence, and
   change the approach when a repeated edit fails to improve the result. Do not
   invent corner exceptions or change intent solely to silence a finding. If the
   design needs regeneration, preserve accepted glyphs and follow the pilot
   generation gate above; this correction loop does not authorize repeated vector
   attempts after systemic failure. Paid calls still need approval, and a requested
   concept-selection gate still applies.
7. Write a per-glyph agent review receipt with concrete findings and saved proof
   hashes **after** inspection, with findings tied to the actual rubric branches.
   Schema-3 profiles require a schema-2 receipt with complete `size_reviews` for
   both formats at every required size; include readability and glyph-distinction
   findings. Report unsupported sizes honestly. Validate in the intended PDF or
   desktop application too when that output is requested.
   Rerun preflight to reach `ready_for_release`. Use `fontify release`, never an ungated build,
   for the first user-facing font. The release command requires passing source
   and compiled audits plus a current complete receipt. Follow its returned
   manifest and verified pointer; present only that reviewed version.

## Final user approval and revisions

- For a revision, run `fontify compare <before-manifest> <after-manifest> --out
  <review-dir>`. The overlay preserves baseline/scale and identifies record,
  kerning and metric changes. Match sample sizes and line breaks; don't stretch
  text to equal width to hide changed proportions.
- Agent preflight is not user aesthetic approval. A review receipt is an integrity
  gate, not an independent optical-quality classifier or a cryptographic attestation.
  Fonts with only A–Z cannot produce a truthful lowercase/title-case pangram.
- After human approval, `fontify snapshot <project.json> --output <new-baseline>`
  writes a fresh candidate baseline. Point `approval` at it and build again.
  Re-audit and update the receipt binding for that changed project metadata only
  after verifying the actual font and reviewed evidence still match.
  Don't refresh a baseline solely to make a failing preservation check pass.
  A stored fingerprint proves preservation, not aesthetic approval.

## Deliver evidence

Run the appropriate acceptance checks from [docs/acceptance.md](docs/acceptance.md).
Use `scripts/run_acceptance.py` for the full offline foundation. Check both
TTF/WOFF2, coverage, release integrity, approval drift and real shaping, not
just the command's exit code. Human visual approval and live provider access
must be reported separately from automated passes.

Return versioned font/proof paths, exact coverage, corrections/checks performed,
and remaining design decisions. Keep exact method, provider/model, prompt and
source provenance in project records. Volunteer a generation-method summary
**only if the user specifically requested vector generation**; then say whether
native vector generation or image generation followed by tracing was actually
used. Otherwise keep routine updates focused on designs and results, while still
answering direct questions truthfully and disclosing necessary costs, permissions
or blockers. Never claim traced raster artwork is native-vector-generated.
Rebuilding doesn't authorize system font installation,
publishing or changing a separate font project.
