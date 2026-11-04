---
name: fontify
description: Build and review font files from a typeface concept and explicit vector glyph designs using Fontify. Use for SVG-to-font construction, Unicode coverage, metrics, spacing, kerning and approved-glyph comparisons, with optional Recraft source artwork. Does not require a paid generator or alter existing approved font projects by default.
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

Supply per-glyph SVGs from any editor, existing original vectors or a local
procedural design. For a runnable offline foundation, copy `examples/offline/`.
If new geometry is wanted, `scripts/make_demo.py --out <new-project>` shows a
deterministic drawing recipe; its stylistic choices are not compiler defaults.

Read [project-format.md](references/project-format.md) when mapping outlines or
metrics. Set one Unicode scalar and explicit advance for each glyph. Keep space
blank. Inspect coordinate convention and placement before interpreting clipping
or sidebearing warnings. Don't normalize each letter's width/height independently.

If Recraft is explicitly wanted, read [recraft.md](references/recraft.md). Prefer
configured MCP access for exploration, discover its actual `inputSchema`, and
don't assume REST fields fit MCP. A reusable application uses the optional
server-side adapter. First produce a dry request plan. Obtain user authorization
before a paid call, credential creation or purchase; never infer it from general
font-building approval. No Recraft access is needed for build, tests or preview.

## Build a candidate

1. Use a new project/version or output directory. Preserve original/approved
   sources and baseline. During drawing, set `approval: null`; this marks the
   candidate as requiring review, not approved.
2. Run `fontify validate <project.json>`, then
   `fontify build <project.json> --out <build-dir>`. Resolve source/topology/metrics
   errors explicitly; do not bypass them by smoothing, unioning or thinning all
   letters. Correct named glyphs in the vector editor.
3. Follow the returned release manifest. Reopen the compiled TTF with
   `fontify inspect <font.ttf> --text '<supported sample>'`. Check exact coverage,
   names, version, metrics and HarfBuzz positions. Fonts with only A–Z cannot
   produce a truthful lowercase/title-case pangram.

## Review and approve

- Open the release's `proof.html` and `glyph-sheet.svg`. They use actual compiled
  outlines; the typed preview uses embedded WOFF2. Review all glyphs at shared
  scale, plus supported words, alphabets and diagnostic pairs with kerning on/off.
- For a revision, run `fontify compare <before-manifest> <after-manifest> --out
  <review-dir>`. The overlay preserves baseline/scale and identifies record,
  kerning and metric changes. Match sample sizes and line breaks; don't stretch
  text to equal width to hide changed proportions.
- Audit straight edges, intentional sharp corners, bowls, counters, diagonals,
  joins and lowercase distinctions. Symmetry/ink measurements do not establish
  optical weight or smooth curves. Exact reflection is not a universal goal.
- After human approval, `fontify snapshot <project.json> --output <new-baseline>`
  writes a fresh candidate baseline. Point `approval` at it and build again.
  Don't refresh a baseline solely to make a failing preservation check pass.
  A stored fingerprint proves preservation, not aesthetic approval.

## Deliver evidence

Run the appropriate acceptance checks from [docs/acceptance.md](docs/acceptance.md).
Use `scripts/run_acceptance.py` for the full offline foundation. Check both
TTF/WOFF2, coverage, release integrity, approval drift and real shaping, not
just the command's exit code. Human visual approval and live provider access
must be reported separately from automated passes.

Return the versioned font paths, proof/comparison paths, exact coverage, checks
run and remaining visual limitations. State whether any provider experiment
actually ran. Rebuilding doesn't authorize system font installation, publishing
or changing a separate font project.
