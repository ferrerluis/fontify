# Fontify

Turn a typeface concept and explicit vector glyph designs into usable, reviewable
font files. **The compiler runs offline and needs no API key.** MIT licensed.
Recraft is an optional source-artwork provider, never a font compiler.

## Offline quickstart

Python 3.11+; tested here with Python 3.14. After dependency installation, every
command below runs locally without a network connection or credentials.

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev,recraft]'
# Or omit ,recraft: pip install -e '.[dev]'
fontify release examples/imagegen/fontify.json --out build
fontify inspect build/FontifyGrotesk-Regular-v0.002/FontifyGrotesk-Regular-v0.002.ttf --text AVATAR
fontify verify-release build/FontifyGrotesk-Regular-v0.002/release-manifest.json
```

Open `build/FontifyGrotesk-Regular-v0.002/proof.html`: a self-contained specimen with
embedded WOFF2, typed coverage warnings, every glyph, and HarfBuzz-positioned
samples with kerning on/off. `glyph-sheet.svg` is a portable vector proof.
For a browser that requires HTTP, serve **only the generated release folder**:

```sh
python -m http.server 8765 --bind 127.0.0.1 --directory build/FontifyGrotesk-Regular-v0.002
# Visit http://127.0.0.1:8765/proof.html
```

The primary example, **Fontify Grotesk**, was created with the built-in image
generation tool, then cropped, traced, corrected and reviewed locally. It covers **A–Z and
space: 27 mappings**, plus `.notdef`; no lowercase, digits, punctuation or accents.
The raw AI image, exact prompt and tracing provenance are checked in. Rebuilding
uses frozen corrected SVGs and a per-glyph agent review receipt; no model call is
needed. The v0.002 preflight passed. Final user design approval is still pending.

See [the image-generated example](examples/imagegen/README.md) for reproduction
and source-versus-compiled proofs. `examples/offline/` is the older hand-coded
engineering fixture; it is kept for structural regression tests, not presented
as the designed typeface. Its geometry recipe remains `scripts/make_demo.py`.

There is also a real [Recraft Vector example, Fontify Mellow](examples/recraft-mellow/README.md):
a friendly informal alphabet covering A–Z, a–z and space. Its frozen vectors,
intent-aware checks and proofs rebuild offline with no account or API key:

```sh
fontify release examples/recraft-mellow/fontify.json --out build
# Open build/FontifyMellow-Regular-v0.002/proof.html
```

## Bring your own glyphs

Copy `examples/imagegen/`, replace its SVGs, set `approval` to `null` while drawing,
and edit `fontify.json` plus the per-glyph quality intent. Replacing letters or
spacing invalidates the example's review receipt; review your new design afresh.
Declare every mapping, advance and required character.
Use black filled, closed paths and explicit placement; see [the format](references/project-format.md).

```python
from fontify import release_font, load_project
from fontify.review import inspect_font, shape_font

project = load_project("examples/imagegen/fontify.json")
release = release_font(project, "build")  # requires current complete preflight
print(inspect_font(release.parent / f"{project.stem}.ttf", "AVATAR"))
```

Design a new alphabet with image generation or optional Recraft Vector, or supply
your own approved vector outlines. Separate that creative work from compilation. No automatic tracing,
smoothing, mirroring, thinning, auto-fitting, or inferred missing letters occurs
in the compiler. Raster tracing is an optional, separate authoring step whose
settings and source comparisons must be reviewed.

## Review before the first font is presented

The skill must audit, correct, export, recheck and visually inspect **every glyph**
before presenting a font. Checks cover intended symmetry, exact 0/90-degree edges,
curve kinks/cusps, topology, shared stem targets, spacing and source preservation.
Intentional asymmetry, corners and diagonals are explicit. Numeric checks alone
missed facets in the generated O; enlarged review caught and corrected them.

```sh
fontify validate my-font/fontify.json
fontify audit my-font/fontify.json --out build/audit-before
fontify repair my-font/fontify.json --out build/candidate-02 --version 0.002
fontify build build/candidate-02/fontify.json --out build/drafts-02 --draft
# Recheck the actual exported TTF, inspect every glyph and shaped words,
# then record concrete findings and saved proofs in the agent review receipt.
fontify release build/candidate-02/fontify.json --out build
# Edit a candidate in another project/version, then compare actual releases:
fontify compare path/to/before/release-manifest.json path/to/after/release-manifest.json --out build/comparison
# AFTER reviewing it, capture a NEW baseline file (existing files are never overwritten):
fontify snapshot my-font/fontify.json --output my-font/approved-v2.json
```

See [preflight commands, profiles and receipts](references/preflight.md). Drafts
never update `current.json`; release blocks failed checks and missing/stale review.
Changes to letters, spacing, kerning, intent or saved proof bytes require recheck.
Corrections are separate bounded authoring actions; they refuse approved projects
and never overwrite their input. `build_font` remains a lower-level compiler API
for technical uses; `release_font` always requires complete preflight.

[Style decision rubrics](references/style-rubrics.md) turn the generated-font
[findings](docs/review-rubrics.md) into executable routing. For new work, choose
geometric, humanist, handwritten, serif or display defaults, inspect each glyph's
intent, then run the internal correction/recheck pass:

```sh
fontify rubric-plan my-font/fontify.json --style handwritten --note 'Deliberate lean and organic comic curves.' --output my-font/quality-v2.json
# Set quality to quality-v2.json; inspect and confirm each glyph's decisions.
fontify preflight my-font/fontify.json --out build/pass-01
# Allow only appropriate repairs in the profile, then revise internally:
fontify preflight my-font/fontify.json --out build/pass-02 --repair-version 0.002
```

Preflight saves routed results and actual-font comparisons. Exit 1 means blocked;
2 means visual review is required; 0 means an existing current complete receipt
permits release. It never auto-approves appearance, publishes, or updates the
release pointer. Style defaults can be overridden per feature; technical validity
and the visual gate always apply. Frozen schema-1 examples remain supported.

Set `approval` to the baseline only after user approval. A source, placement, outline, Unicode or
advance change to a locked glyph stops the build; new glyphs are listed as
unreviewed. A baseline match proves preservation, not human approval. The bundled
baseline is a regression fixture for the demo. Do not refresh it merely to pass a check.

Each release contains TTF, WOFF2, CSS with exact Unicode coverage, proofs,
`validation.json`, `quality.json` for gated projects, and a hashed `release-manifest.json`. `build/current.json`
points to the last successful build. Different bytes cannot replace an existing
version; increase `version`. Use the pointer or returned manifest instead of guessing
the newest filename. [Ferrer evidence](docs/ferrer-lessons.md) motivated these rules.

## Optional Recraft

Use `fontify recraft-plan examples/recraft/concept.txt` for a dry request.
It reads no secret and makes no network call. The [setup and research guide](references/recraft.md)
covers API tokens, remote MCP OAuth, billing, models, candidate review and mock tests.
API CLI generation requires `--allow-paid`; an agent must also obtain your explicit
authorization for the specific spend. Keep tokens on the server, out of client code.

One user-authorized MCP generation produced Mellow with `recraftv4_1_vector`,
using 4 Studio subscription credits. OAuth account access, the exposed live tool
signatures and an actual SVG response were verified; the REST adapter is still
mock-tested rather than tested with a live API token. [Live evidence](docs/research/recraft-live-tools.json)
supersedes the earlier [unauthenticated 403 attempt](docs/research/recraft-mcp-discovery.json).
MCP and REST input fields differ. `fontify recraft-discover --output schema.json`
only initializes and lists tools; generation is never part of the offline suite.

## Architecture and tests

`src/fontify/` is the local construction library; `providers/` is optional creative
input. Root `SKILL.md` is the agent entrypoint, with selective `references/`, runnable
`scripts/`, and `examples/`, inspired by [Anatomy's organization](https://github.com/wheresryan22/anatomy).
See [architecture and tradeoffs](docs/architecture.md) and [acceptance cases](docs/acceptance.md).

To use the agent skill, clone or symlink this whole repository into
`~/.agents/skills/fontify`, keeping `SKILL.md` at its root, then invoke `$fontify`.
Install its Python package in a virtual environment; the skill guides the same
library and commands.

```sh
# To reproduce raster tracing and run its additional checks:
pip install -r examples/imagegen/requirements-trace.txt
python scripts/run_acceptance.py
```

The base checks need the dev dependencies; the three imagegen checks also need
the optional trace requirements. Checks cover exact coverage, Unicode, topology, metrics, reproducible TTF/WOFF2,
HarfBuzz kerning, approval drift, release integrity and mocked Recraft requests.
Acceptance results are written under `test-runs/`. `requirements.lock` pins this
development toolchain; use it for byte-for-byte reproduction across rebuilds.

## Limits and next steps

- Static, upright, single-master fonts; pair kerning through GPOS. Complex-script
  layout, mark positioning, ligatures, variable fonts, hinting and CFF/OTF export
  are not implemented. TTF is already an OpenType font; WOFF2 wraps the same outlines.
- SVG input is intentionally narrow: paths and affine groups. Expand strokes,
  remove backgrounds and convert other shapes/arcs in your editor. The compiler
  rejects overlaps/intersections instead of silently repairing approved designs.
- Cubics become quadratics within the declared error, then integer coordinates;
  source and compiled fingerprints both matter. No claim of mathematically exact
  curve preservation or complete font-engine certification.
- Geometry checks cannot establish optical weight, smooth curves, rhythm or
  style. Every-glyph agent visual review is required for release; final user
  approval remains a separate decision. Receipts prove integrity, not aesthetics.
- Next: UFO/designspace exchange for multi-master work, broader font QA and richer
  optical diagnostics. Style rubrics are implemented; more reviewed fonts are
  needed to calibrate their defaults beyond the two source experiments.
