# Architecture decisions · 2026-11-03

## Working path

```text
concept + explicit coverage
    -> image generation / supplied vectors / optional Recraft artwork
    -> individual SVGs + fontify.json + explicit per-glyph intent
    -> safe parse + explicit coordinate normalization
    -> source topology / metrics / approval / intent checks
    -> bounded candidate correction + audit loop (separate authoring step)
    -> fontTools FontBuilder + cubic-to-quadratic conversion + GPOS
    -> TTF -> reopen / compare / shape with HarfBuzz
    -> WOFF2 -> reopen / compare / shape again
    -> compiled geometry recheck + all-glyph agent visual review + proofs
    -> release gate + artifact hashes + current.json
```

Creative generation is a separate module and an explicit command. `build_font`
has no provider imports, tokens or network operations. The local SVG provider and
checked-in example cover the entire path for users who never use Recraft.

## Tool choice

| Tool | Current role / decision |
|---|---|
| [fontTools](https://fonttools.readthedocs.io/en/latest/) | Maintained Python tooling for OpenType tables, SVG paths, pens and compilation. Build directly for this small static-outline foundation. |
| [fontmake](https://github.com/googlefonts/fontmake) | Compiles UFO/Glyphs/designspace sources. Better future interchange/multi-master route; not needed to add a full authoring-tool source model to the first SVG build. |
| [FontForge](https://fontforge.org/en-US/) | Free editor for human correction and fuller font work. Keep editor choice optional; do not require a desktop installation to run CI. |
| [uharfbuzz](https://github.com/harfbuzz/uharfbuzz) | Bindings to real HarfBuzz shaping. Check both feature-on/off pair adjustments and actual sample glyph IDs/positions. |
| [Skia PathOps](https://github.com/fonttools/skia-pathops) | Measure filled area and reflected XOR area. Boolean geometry is read-only in the compiler; the original demo's authoring recipe deliberately expands strokes before review. |

These choices follow the projects' official docs/repositories, reviewed on the
date above. Exact development versions are in `requirements.lock`; each release
records its font toolchain. Dependency upgrades can change rounding, compression
or proofs; use a new release version and compare when that happens.

## Format tradeoffs

TTF is OpenType with quadratic TrueType outlines, usable in desktop/design tools.
WOFF2 is the same font packaged for browsers with Brotli compression. Reopening
both verifies cmap, names, advances and outline fingerprints. This is a concrete
first deliverable, rather than two different font designs behind two extensions.

SVG cubics require [bounded conversion to quadratics](https://fonttools.readthedocs.io/en/latest/pens/cu2quPen.html).
`curve_error` (default 0.25 font units) bounds that approximation before integer
coordinate rounding. It is not a pixel error at every display size. Keep sources
and compiled snapshots; no assertion of exact cubic preservation is made. Native
CFF/OTF could retain cubics but requires another output/validation path; deferred.

No variable masters, hinting, complex-script substitutions, mark positioning or
automatically inferred kerning. GPOS stores explicit pairs. The schema accepts
Unicode beyond Latin but does not supply script-specific layout behavior.
Broad platform certification (including OTS/FontBakery and application testing)
remains a release-hardening step for a professional font.

## Preservation, publication and scope

- SVG source bytes, normalized outlines and exported outlines are separately
  fingerprinted. No broad geometry repair runs during compilation. Even a source
  formatting edit is conservative approval drift; deliberate reapproval is possible.
- Compiler-normalized winding changes traversal direction, not shape. Topology
  checks run before and after quadratic conversion/rounding. Overlaps are rejected,
  since silently unioning them can change counters and character.
- Builds stage artifacts before publishing a versioned folder. A different release
  cannot overwrite the same version; `current.json` is written last. Concurrent
  builds to one output folder are not supported; use separate folders per process.
- Release hash manifests and `verify-release` catch stale/corrupted exported files.
  They are integrity records, not signatures or protection against a malicious
  editor who can rewrite both manifest and artifacts.
- The root skill borrows Anatomy's progressive structure, not its code or graphic
  workflow. The Python library stays usable without any agent or skill runtime.

## Visual quality boundary

The primary example now uses a real built-in image generation call. Its frozen
PNG, exact prompt, explicit crop/normalization plan and traced SVGs are checked
in under `examples/imagegen/`. The hand-coded `examples/offline/` alphabet remains
an engineering fixture. The agent workflow starts new concept alphabets with
image generation or optional Recraft, or accepts the user's own approved vectors.

Raster tracing is a separate optional authoring helper, never an implicit compiler
operation. Raw/compiled comparison proofs expose approximation. The image model
made the final row smaller; its explicit uniform row scaling is recorded and
remains subject to optical review. Structural passes do not validate that design.

Symmetry ratios measure geometric differences between a path and its reflection;
ink fraction measures filled area within bounds. Neither establishes optical
balance, perceived stem weight, curve continuity or style consistency. Flattened
topology checks are diagnostics, not an exact intersection theorem. Inspect
letters at matched scale and in shaped words, particularly bowls, counters,
diagonals, terminals and lowercase distinctions. The first demo's visual check
found cap alignment/vertex spikes that structural tests correctly did not certify.

`quality.py` adds per-glyph construction intent, exact intended axes, selected
symmetry, explicit stem probes and curve cusp/tangent diagnostics. `repair.py` is
an optional separate authoring action, refuses approved projects, preserves
originals and enforces area/bounds/topology budgets. Named fingerprint-bound
contour patches support deliberate local corrections; there is no universal
curve fitter or implicit smoothing during compilation.

`release_font` requires passing source/actual-TTF audits and a complete agent
review receipt bound to project, profile, compiled font and saved proof hashes.
The skill requires the agent to inspect every glyph, enlarged and in shaped text,
then correct/recheck before the first user handoff. `build --draft` can expose
diagnostics internally without updating the release pointer. Legacy low-level
builds without a quality profile stay supported but are not preflight-qualified.
The receipt is an integrity record, not independent evidence of taste or proof
that an agent viewed an image. User aesthetic approval remains separate.

The generated example needed eight internal iterations. Sub-unit implied points
from quadratic decomposition initially broke symmetry after integer rounding;
the authoring step now quantizes the master before reflection. Enlarged review
also caught facets and mirrored notches despite passing numeric checks. Explicit
named corrections and preserved before/after sheets demonstrate why both stages
are necessary.

The Recraft Mellow experiment subsequently verified the authenticated remote MCP
and a native SVG result (one authorized call, 4 Studio credits). Its live tool
inputs differ from REST; see the saved signatures and setup guide. A frozen
vector-sheet helper performs explicit paint-order normalization and component
mapping; it uses no raster tracing or network. Upper/lowercase files use Unicode
filenames to avoid case-insensitive filesystem collisions.

The same experiment exposed a geometric-profile limitation: intended humanist
curvature and lean must not be forced to exact axes just because they are close.
Per-glyph `axis_policy: "declared"` limits corrections to named regions. The
default remains compatible with the earlier geometric example. A 24.33% X
reflection was refused, and numerically passing but visually worse I/i/l edits
were reverted. Only H, Z and q differ in the final compiled outlines. Curve cusp
checks now test stationary tangent reversals rather than misclassifying smooth
wide hooks by their chord angle. Human visual review remains necessary.
