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
fontify build examples/offline/fontify.json --out build
fontify inspect build/OfflineSans-Regular-v1.001/OfflineSans-Regular-v1.001.ttf --text AVATAR
fontify verify-release build/OfflineSans-Regular-v1.001/release-manifest.json
```

Open `build/OfflineSans-Regular-v1.001/proof.html`: a self-contained specimen with
embedded WOFF2, typed coverage warnings, every glyph, and HarfBuzz-positioned
samples with kerning on/off. `glyph-sheet.svg` is a portable vector proof.
For a browser that requires HTTP, serve **only the generated release folder**:

```sh
python -m http.server 8765 --bind 127.0.0.1 --directory build/OfflineSans-Regular-v1.001
# Visit http://127.0.0.1:8765/proof.html
```

The checked-in example is **A–Z and space: 27 Unicode mappings**, plus `.notdef`.
It has no lowercase, digits, punctuation or accents. Offline Sans is original,
procedural demonstration artwork, not Ferrer and not a finished professional font.
`python scripts/make_demo.py --out /path/to/new-project` authors it without AI.

## Bring your own glyphs

Copy `examples/offline/`, replace its SVGs, set `approval` to `null` while drawing,
and edit `fontify.json`. Declare every mapping, advance and required character.
Use black filled, closed paths and explicit placement; see [the format](references/project-format.md).

```python
from fontify import build_font, load_project
from fontify.review import inspect_font, shape_font

project = load_project("examples/offline/fontify.json")
release = build_font(project, "build")  # returns the release manifest path
print(inspect_font(release.parent / f"{project.stem}.ttf", "AVATAR"))
```

Draw with a vector editor, supply your own outlines, or generate new geometry
locally. Separate that creative work from compilation. No automatic tracing,
smoothing, mirroring, thinning, auto-fitting, or inferred missing letters occurs
in the compiler. The example's explicit stroke design is a separate authoring script.

## Review and preserve a design

```sh
fontify validate my-font/fontify.json
fontify build my-font/fontify.json --out build
# Edit a candidate in another project/version, then compare actual releases:
fontify compare path/to/before/release-manifest.json path/to/after/release-manifest.json --out build/comparison
# AFTER reviewing it, capture a NEW baseline file (existing files are never overwritten):
fontify snapshot my-font/fontify.json --output my-font/approved-v2.json
```

Set `approval` to that baseline path. A source, placement, outline, Unicode or
advance change to a locked glyph stops the build; new glyphs are listed as
unreviewed. A baseline match proves preservation, not human approval. The bundled
baseline is a regression fixture for the demo. Do not refresh it merely to pass a check.

Each release contains TTF, WOFF2, CSS with exact Unicode coverage, proofs,
`validation.json` and a hashed `release-manifest.json`. `build/current.json`
points to the last successful build. Different bytes cannot replace an existing
version; increase `version`. Use the pointer or returned manifest instead of guessing
the newest filename. [Ferrer evidence](docs/ferrer-lessons.md) motivated these rules.

## Optional Recraft

Use `fontify recraft-plan examples/recraft/concept.txt` for a dry request.
It reads no secret and makes no network call. The [setup and research guide](references/recraft.md)
covers API tokens, remote MCP OAuth, billing, models, candidate review and mock tests.
Generation requires `--allow-paid`; an agent must also obtain your explicit
authorization for the specific spend. Keep tokens on the server, out of client code.

No paid requests were made during development. No Recraft MCP is configured in
this environment; a public initialization attempt was blocked by Cloudflare 403.
The live tool schema and real generation remain unverified. [Discovery evidence](docs/research/recraft-mcp-discovery.json)
records the result; `fontify recraft-discover --output schema.json` performs only
initialization and `tools/list`, never generation. Do not assume MCP fields match REST.

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
pytest -q
python scripts/run_acceptance.py
```

Checks cover exact coverage, Unicode, topology, metrics, reproducible TTF/WOFF2,
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
- Automated symmetry, ink area and topology checks cannot judge optical weight,
  smoothness, rhythm or style. Human review is required before release.
- Next: UFO/designspace exchange for multi-master work, broader font QA, richer
  optical diagnostics, and an authorized Recraft experiment. These are future work.
