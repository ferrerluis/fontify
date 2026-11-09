# Fontify

Fontify turns letter drawings into font files you can install on your computer
(TTF) or use on a website (WOFF2). Use it with a coding agent to develop a typeface
from an idea, or bring your own SVG drawings.

## Why

Letter drawings need spacing and a way for apps to match each drawing to the
character you type. Fontify puts those pieces together and gives you a browser
preview; the agent checks every letter, and you approve the design.

## How

Requires Python 3.11+ and an agent that supports local skills.

1. Install the skill by cloning this whole repository into your agent's skills
   folder. For agents that use `~/.agents/skills`:

   ```sh
   git clone https://github.com/ferrerluis/fontify.git ~/.agents/skills/fontify
   ```

2. Ask your agent to use it. For example:

   ```text
   Use $fontify to make a friendly handwritten font with uppercase and
   lowercase letters and spaces. Check every letter and show me a preview
   before I approve the design.
   ```

3. Review the font files and browser preview. Request changes or approve the
   design when you're happy with it.

Building fonts runs locally after setup, with no API key needed. Generating new
artwork may use an online service; Recraft is optional. The agent's setup and
build commands are below.

Try the included examples: [Fontify Grotesk](examples/imagegen/README.md)
(uppercase and space) or [Fontify Mellow](examples/recraft-mellow/README.md)
(uppercase, lowercase and space). Both rebuild offline from saved drawings;
neither includes digits, punctuation or accents.

Explore [ten modernized display-font samples](examples/modernized/README.md),
with final TTF/WOFF2 files, live specimens, stories and exact expanded-Latin
coverage. These frozen final-artifact samples have their own documented build
boundaries, display minima and pending distribution terms.

The compiler and code are [MIT licensed](LICENSE). Distribution terms for the
[new modernized font assets](examples/modernized/README.md) remain pending owner review;
no new license grant is made for those assets.

<details>
<summary>Agent reference: setup, font creation, review, release and tests</summary>

Read [SKILL.md](SKILL.md) before creating or revising a font. It defines the agent
workflow; the commands and links below support it. Keep the whole repository
together, with `SKILL.md` at the skill folder's root. Work from the repository
root and use the existing CLI/library in `src/fontify/`.

### Choose the source method before generating

Inspect the references and requested letterform qualities before deciding whether
to try a vector model. Image generation can be the first choice. If trying vector,
make one pilot iteration with one output, even when several options were requested,
and review prompt compliance before producing the rest. A passing pilot permits
the requested vector options within existing approval and budget; a systemically
off result switches to image generation instead of repeated vector attempts.
See [generation routing](references/generation-routing.md) for the review criteria,
source restrictions, cost boundaries and provenance requirements.

Keep existing options intact. When the user is choosing among designs, wait for
their selection before cleanup, tracing or construction. Liking an option does
not select or approve it. Native vectors stay vector; only raster artwork is traced.

### Optical spacing, raster input and size proofing

New work separates source preparation, optical spacing and final-font proofing.
Native Recraft/SVG artwork remains vector throughout extraction and construction.
Raster cleanup and tracing apply only to bitmap input. Rendering a finished font
for legibility review does not replace or rasterize its source outlines.

- [Spacing and kerning proposals](references/spacing.md): measured white areas,
  reference-height/depth controls, collision-guarded pairs, and fresh candidates.
- [Raster preparation](references/raster-preparation.md): explicit guide masks,
  component decisions that preserve marks, optional resampling, and saved evidence.
- [Intended-size proofing](references/size-proofing.md): fixed-size TTF and browser
  WOFF2 proofs, text/display minimum sizes, and a stricter release receipt.

The new profile schema is 3. Existing schema-1/2 examples keep their frozen
geometry, profiles and historical evidence. New proof generation and browser
capture never imply inspection or aesthetic approval.

### Setup

Python 3.11+ is required; the offline suite runs on Python 3.11 and 3.14. Install
the package in a virtual environment:

```sh
cd ~/.agents/skills/fontify
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev,proof]'
# Only for bitmap source authoring: pip install -e '.[raster]'
# Optional REST artwork provider: pip install -e '.[recraft]'
# Browser capture: python -m playwright install chromium
# Or pass --browser /path/to/installed/chrome when capturing size proofs.
```

Use your actual checkout path if you installed elsewhere. The `dev` extra adds
test tools; `proof` adds fixed-size raster/browser QA and `raster` adds bitmap
tracing. `pip install -e .` is enough for the compiler and legacy profiles.
Use `pip install -r requirements.lock` for the complete pinned offline test suite. After dependencies are
installed, compilation, checks and previews run locally without credentials or a
network connection. Recraft supplies optional artwork, never font compilation.

### Rebuild and inspect an example

```sh
fontify release examples/imagegen/fontify.json --out build
fontify inspect build/FontifyGrotesk-Regular-v0.002/FontifyGrotesk-Regular-v0.002.ttf --text AVATAR
fontify verify-release build/FontifyGrotesk-Regular-v0.002/release-manifest.json
```

Open `build/FontifyGrotesk-Regular-v0.002/proof.html`. It embeds WOFF2 and includes
typed coverage warnings, every glyph and HarfBuzz-positioned samples with kerning
on/off. `glyph-sheet.svg` is a portable vector proof. If the browser needs HTTP,
serve only the generated release folder:

```sh
python -m http.server 8765 --bind 127.0.0.1 --directory build/FontifyGrotesk-Regular-v0.002
# Visit http://127.0.0.1:8765/proof.html
```

Fontify Grotesk covers **A–Z and space: 27 mappings**, plus `.notdef`. Its original
AI image, exact prompt, tracing provenance, corrected SVGs and per-glyph agent
review receipt are checked in. Rebuilding calls no model. Its v0.002 preflight
passed; final user design approval is pending. See [the image-generated
example](examples/imagegen/README.md) for reproduction and source comparisons.

Fontify Mellow covers **A–Z, a–z and space: 53 mappings**, plus `.notdef`. It uses
saved Recraft vectors and has user approval recorded in its project. See [the
Mellow example](examples/recraft-mellow/README.md) for provenance and corrections.

```sh
fontify release examples/recraft-mellow/fontify.json --out build
# Open build/FontifyMellow-Regular-v0.002/proof.html
```

`examples/offline/` is the older hand-coded engineering fixture, kept for
structural regression tests. Its geometry recipe is `scripts/make_demo.py`.

### Create a new font project

Start in a separate project directory. You can copy `examples/imagegen/` as a
template, replace its SVGs and edit `fontify.json`. Set `approval` to `null` for
the new design and create fresh quality intent and review evidence. Never reuse
the example's receipt for changed letters or spacing.

- Declare every character mapping, advance width and required character. A
  wordmark or alphabet image doesn't supply missing letters automatically.
- Use black filled, closed SVG paths and explicit placement. Review coordinate
  conventions, baselines and shared scale; don't fit each letter independently.
  See [the project and SVG format](references/project-format.md).
- Choose image generation, a reviewed vector pilot, or supplied artwork using
  [generation routing](references/generation-routing.md). Keep original artwork
  and prompts. Raster tracing is a
  separate optional authoring step whose settings and source comparisons need
  review.
- The compiler doesn't trace, smooth, mirror, thin, auto-fit or invent letters.
  Corrections are separate, bounded authoring actions that preserve their input
  and refuse approved projects.

### Check, correct and review before presenting a font

Follow [the style decision rubrics](references/style-rubrics.md) for new work.
Choose geometric, humanist, handwritten, serif or display defaults, then inspect
and confirm each glyph's intent. Use schema 3 for new profiles; frozen schema-1/2
projects remain supported without changing their approval evidence.

```sh
fontify rubric-plan my-font/fontify.json --style handwritten --note 'Deliberate lean and organic comic curves.' --intended-use text --output my-font/quality-v3.json
# Set the candidate's quality to quality-v3.json.
# Inspect every glyph, resolve its decisions and confirm its intent.
fontify validate my-font/fontify.json
fontify preflight my-font/fontify.json --out build/pass-01
# Enable only appropriate repairs in the profile, then revise internally:
fontify preflight my-font/fontify.json --out build/pass-02 --repair-version 0.002
```

Read the saved `preflight.json` and follow the returned candidate paths. Exit 1
means blocked; 2 means visual review is required; 0 means a current complete
receipt permits release. Preflight saves routed results and actual-font
comparisons. It never auto-approves appearance, publishes or updates `current.json`.

For separate audit, repair and internal draft commands:

```sh
fontify audit my-font/fontify.json --out build/audit-before
fontify repair my-font/fontify.json --out build/candidate-02 --version 0.002
fontify build build/candidate-02/fontify.json --out build/drafts-02 --draft
# Audit the actual exported TTF too; substitute the returned TTF path:
fontify audit build/candidate-02/fontify.json --font path/to/actual-draft.ttf --out build/audit-after
```

Before presenting the first font, audit, correct, export, recheck and visually
inspect **every glyph**, including blank space. Inspect actual compiled letters
at enlarged and every declared fixed size, plus shaped words and pairs with kerning
on/off. Text profiles require 12/16/24/48 px; display profiles record their minimum
and rationale. See [size-proofing.md](references/size-proofing.md) for TTF and
actual-browser WOFF2 evidence, pending capture and mandatory `size_reviews`.
Check intended symmetry, exact horizontal/vertical features, curves and corners,
contours, optical weight, spacing and source preservation. Preserve intentional
asymmetry, corners, diagonals and organic strokes.

Numeric checks alone missed facets in Grotesk's O; enlarged review caught them.
Reject and revert edits that look worse even if they pass numeric checks. Repeat
correction and review until no identified defect remains. Unresolved intent
blocks correction and presentation; don't invent exceptions to silence findings.

After inspection, write a per-glyph agent review receipt with concrete findings
and saved proof hashes, then rerun preflight. Changes to letters, spacing,
kerning, project settings, intent or proof bytes require recheck. See
[preflight commands, profiles and receipt fields](references/preflight.md) and
[the review findings behind the rubrics](docs/review-rubrics.md).

### Release, compare and record user approval

```sh
fontify release build/candidate-02/fontify.json --out build
# Use the manifest path returned by release:
fontify verify-release path/to/release-manifest.json
fontify compare path/to/before/release-manifest.json path/to/after/release-manifest.json --out build/comparison
# Only after user approval, write a NEW baseline (existing files aren't overwritten):
fontify snapshot build/candidate-02/fontify.json --output build/candidate-02/approved-v2.json
```

Use `release` for the first user-facing font. It requires passing source and
compiled checks plus a current complete receipt. Drafts never update
`current.json`. Agent review and a matching baseline don't establish user design
approval; receipts establish integrity, not aesthetic quality.

After user approval, point `approval` at the new baseline for the approved
project. Re-audit and refresh the receipt binding for this metadata change only
after verifying that the reviewed font and proof bytes still match.
A source, placement, outline, Unicode or advance change to a locked
glyph stops the build; additions are listed as unreviewed. Never refresh a
baseline just to pass a check. Keep approved projects unchanged and propose edits
in a separate candidate/version. [Ferrer lessons](docs/ferrer-lessons.md) explain
the failures that motivated these rules.

Each release contains TTF, WOFF2, CSS with exact Unicode coverage, proofs,
`validation.json`, `quality.json` for gated projects and a hashed
`release-manifest.json`. `build/current.json` points to the last successful
release. Different bytes cannot replace an existing version; increase `version`.
Use the returned manifest or verified pointer instead of guessing a filename.

The same workflow is available in Python:

```python
from fontify import release_font, load_project
from fontify.review import inspect_font, shape_font

project = load_project("examples/imagegen/fontify.json")
release = release_font(project, "build")  # requires current complete preflight
print(inspect_font(release.parent / f"{project.stem}.ttf", "AVATAR"))
```

`build_font` remains a lower-level compiler API for technical uses;
`release_font` always requires complete preflight. Return exact versioned font
and proof paths, coverage, checks, corrections and remaining design decisions.
Keep the actual generation method and provider in project provenance. Volunteer
the method used only if the user specifically requested vector generation,
including any image-generation fallback; otherwise focus routine messages on
designs and results. Answer direct questions truthfully, disclose required costs
or permissions, and never describe traced raster artwork as native-vector-generated.
Rebuilding doesn't
authorize system font installation, publishing or changes to a separate project.

### Optional Recraft artwork

```sh
fontify recraft-plan examples/recraft/concept.txt
```

Choose whether to try vector generation first, following
[generation routing](references/generation-routing.md). This dry request reads
no secret and makes no network call. Within the vector route, it defaults to
Vector Pro (`recraftv4_1_pro_vector`). Use non-Pro only when explicitly requested
or Pro is confirmed unavailable, following `SKILL.md`; pass the model explicitly
in MCP calls rather than relying on service defaults. Preserve the user's choice
of another provider or supplied artwork.

Read [the Recraft setup and research guide](references/recraft.md) for API
tokens, remote MCP OAuth, billing, models, candidate review and mock tests.
Discover actual MCP tool schemas; REST and MCP input fields differ.
`fontify recraft-discover --output schema.json` only initializes and lists tools.
API CLI generation requires `--allow-paid`; agents also need explicit user
authorization for the specific spend. Keep tokens on the server, out of client
code. Generation is never part of the offline suite.

One user-authorized MCP generation produced Mellow with `recraftv4_1_vector`,
using 4 Studio subscription credits. OAuth access, live tool signatures and an
actual SVG response were verified. The REST adapter remains mock-tested rather
than tested with a live API token. [Live evidence](docs/research/recraft-live-tools.json)
supersedes the earlier [unauthenticated 403 attempt](docs/research/recraft-mcp-discovery.json).

### Architecture and tests

`src/fontify/` is the local construction library; `providers/` is optional
creative input. Root `SKILL.md` is the agent entrypoint, with selective
`references/`, runnable `scripts/` and `examples/`, inspired by
[Anatomy's organization](https://github.com/wheresryan22/anatomy). See
[architecture and tradeoffs](docs/architecture.md) and
[acceptance cases](docs/acceptance.md).

```sh
# With the dev extra installed, add optional raster-tracing dependencies:
pip install -r examples/imagegen/requirements-trace.txt
python scripts/run_acceptance.py
```

Base checks need the dev dependencies; the three imagegen checks also need the
trace requirements. Checks cover exact coverage, Unicode, topology, metrics,
reproducible TTF/WOFF2, HarfBuzz kerning, approval drift, release integrity and
mocked Recraft requests. Results go under `test-runs/`. `requirements.lock` pins
the development toolchain for byte-for-byte reproduction across rebuilds.

### Technical limits and next steps

- Builds static, upright, single-master fonts with pair kerning through GPOS.
  TTF is already an OpenType font; WOFF2 wraps the same outlines.
- Can't build variable fonts such as [Inter Variable](https://rsms.me/inter/download/)
  with adjustable weight and optical size. A fixed-weight design with similar
  letter shapes is within the compiler's scope.
- Doesn't generate the context-dependent letter forms and mark positioning
  needed by fonts such as [Noto Naskh Arabic](https://notofonts.github.io/arabic/).
  Mapping Arabic characters alone doesn't provide correct joining behavior.
- Ligatures, hinting and CFF/OTF export aren't implemented.
- SVG input is limited to paths and affine groups. Expand strokes, remove
  backgrounds and convert other shapes/arcs explicitly. The compiler rejects
  overlaps/intersections instead of silently repairing approved designs.
- Cubics become quadratics within the declared error, then integer coordinates.
  Source and compiled fingerprints both matter; mathematically exact curve
  preservation and complete font-engine certification aren't claimed.
- Geometry checks can't establish optical weight, curve quality, rhythm or
  style. Every-glyph agent visual review is required for release; final user
  approval remains separate.
- Future work: UFO/designspace exchange for multi-master work, broader font QA
  and richer optical diagnostics. More reviewed fonts are needed to calibrate
  style defaults beyond the two source experiments.

</details>
