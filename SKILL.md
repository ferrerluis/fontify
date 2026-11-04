---
name: fontify
description: Create fonts from a typeface concept or supplied vectors with Fontify. Choose style-aware decision rubrics, run deterministic checks and bounded corrections, then review every glyph before presenting the first font. Recraft is optional; construction runs offline.
---

# Fontify

This repository is both a Python library and an installable skill folder. Work
from its root after installing it with `pip install -e '.[dev]'`. Use the actual
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

For a new typeface concept, use Recraft Vector Pro (`recraftv4_1_pro_vector`) for
generated glyph artwork when configured Recraft access is available. Use non-Pro
Recraft Vector only when the user explicitly requests it or Pro is confirmed
unavailable; record the concrete reason before choosing that fallback. Preserve
an explicit choice of another provider or supplied approved vector artwork.
Hand-coded geometric letters are engineering fixtures, not a substitute for this creative
workflow. The primary runnable example is `examples/imagegen/`; its frozen SVGs
compile offline. `examples/offline/` remains a synthetic regression fixture.

When Recraft is unavailable or the user chooses image generation, use the
built-in image-generation tool for the concept sheet
without inventing an API key requirement. Preserve its original output and exact
prompt. Review explicit letter crops, baselines and common scaling, then use the
optional tracing helper from [the imagegen example](examples/imagegen/README.md).
Compare the actual compiled font against the generated source; a high pixel
overlap does not establish visual quality. Never label an unapproved design as approved.

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

## Finish preflight before presenting the first font

Read [style-rubrics.md](references/style-rubrics.md) for the executable decision
trees and internal correction loop. Use schema 2 for new work; existing schema-1
approved examples keep their frozen profiles. Read [preflight.md](references/preflight.md)
for detailed receipt fields and local patches. Do this work autonomously; the user should receive
a corrected, reviewed first candidate, not become the first defect finder.

1. Preserve the original artwork, trace, approved baseline and release. Work in
   a new unapproved candidate (`approval: null`). Never reset a baseline just to
   silence drift. Approved glyphs need separate, explicit proposed edits.
2. Choose the rubric strategy from the brief: geometric, humanist, handwritten,
   serif, or display/mixed. Run `fontify rubric-plan` with the style and a concrete
   rationale. Inspect **every** ink glyph before confirming its decisions; a
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
5. **Inspect every letter visually** at enlarged and normal sizes, at a common
   scale/baseline, plus actual shaped words and pair samples with kerning on/off.
   Check all curves and straight features, symmetry, optical weight, contours,
   spacing and source preservation. Review blank space too. Use actual-font
   before/after sheets (`scripts/render_quality_review.py`) and overlays; a
   numeric pass or high tracing overlap is insufficient.
6. Repeat correction, export, audit and visual review until no identified defect
   remains. A numeric pass that looks worse must be rejected and reverted; inspect
   changes below the budget too. Preserve iteration findings and evidence, and
   change the approach when a repeated edit fails to improve the result. Do not
   invent corner exceptions or change intent solely to silence a finding. If the
   design needs regeneration, preserve accepted glyphs; paid calls still need approval.
7. Write a per-glyph agent review receipt with concrete findings and saved proof
   hashes **after** inspection, with findings tied to the actual rubric branches.
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
and remaining design decisions. State whether generation actually ran and which
provider was used. Rebuilding doesn't authorize system font installation,
publishing or changing a separate font project.
