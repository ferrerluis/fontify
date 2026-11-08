# Optical spacing and kerning proposals

Spacing is an explicit vector-only authoring pass, not a compiler optimization.
Run it before final quality intent, preflight and visual review. It never traces,
rasterizes, rescales, smooths or redraws a glyph. It uses the same SVG coordinate
contract as compilation: viewBox padding is not ink or a scaling instruction.
Native vector sources stay vector throughout.

```sh
fontify spacing-plan my-font/fontify.json --output build/spacing-plan.json
# Inspect the JSON measurements, proposals, overrides and collision adjustments.
fontify spacing-apply my-font/fontify.json build/spacing-plan.json \
  --out build/spaced-candidate --version 0.002
# Create fresh quality intent for build/spaced-candidate/fontify.json, then
# complete preflight, inspect the actual exported glyphs/pairs and review again.
```

Planning is read-only, including for approved projects. Applying requires an
unapproved source, a different valid version and a previously nonexistent output
directory outside the source project. Existing targets, including dangling
symlinks, are refused. Projects containing symlinks cannot be copied by this
command. Approved projects are protected: an intentional, separately created,
unapproved candidate is required before applying proposals.

The plan binds source project bytes/settings and each glyph's source, normalized
outline and compiled-outline hashes. Application regenerates the complete plan
and refuses stale or edited results. Change the configuration and regenerate
instead of editing result values. A new candidate contains unchanged source SVG
bytes, horizontal placement changes, integer advances, explicit kerning and
`spacing-changes.json` with the plan and before/after hashes. No source files are
modified and no candidate is overwritten.

**Old quality intent is preserved as a file but disconnected:** the candidate's
`quality` becomes `null`. Stem probes, straight regions, symmetry declarations
and patch fingerprints must not carry confirmed coordinates into moved glyphs.
Create and resolve a fresh quality profile and fresh review evidence. No approval,
readiness or successful preflight is inherited. The ordinary release gate still
requires the quality profile and actual-font review.

## Measurement method

This is Fontify's own deterministic exterior-white-space estimator, inspired by
the general idea of measuring negative space. It is not HT Letterspacer/HTLS or
Tesseract, does not implement their exact results, and contains no copied GPL
implementation. The [HT Letterspacer description](https://letterspacer.htfonts.com/)
is useful background on area-based spacing, not a dependency or accuracy claim.

1. Classify glyphs into caps, lowercase, decimal digits or punctuation/symbols.
   Unicode case and decimal-category checks supply defaults; `glyph_groups`
   provides explicit corrections. Space keeps its explicit advance by default.
2. Use each group's vertical reference zone, with only its configured overshoot
   extension. Do not stretch a small punctuation mark to fill a cap-height zone.
3. Subdivide Bézier outlines to vector segments using Fontify's existing bounded
   0.2-font-unit diagnostic subdivision. Split at every vertex height, find the
   exterior left/right boundary and integrate the linear white-depth functions
   continuously. These are vector polygons, not pixels or bitmap scanlines.
4. Measure exterior indentation relative to the ink bounds. Cap the depth at
   `counter_depth` before integration, so a deep open C or G counter cannot
   dominate spacing. Enclosed holes are not exterior side space. Rows without
   ink contribute no height; the report exposes the active measurement height.
5. Subtract each mean white depth from the group's `side_space`, limit suggested
   bearings to the group's bounds, then use integer horizontal translation and
   integer advance rounding. Tight curve extrema can have fractional bearings;
   the report distinguishes desired from actual proposed bearings. Blank space
   and glyphs with no ink in the zone are preserved unless explicitly overridden.
6. Recompile the proposed glyph placement before pair checks. Measure shared-zone
   pair gaps and propose a signed adjustment toward the sum of the two group
   side-space targets. Apply the optical limit and threshold, then collision-check
   **all drawn pairs**, including pairs outside the optical selection.

Pair safety uses full compiled outlines, not just the reference zone. An initial
vector-silhouette bound is followed by PathOps intersection against an expanded
outline. The buffer uses round joins, a 0.01-unit numerical cushion, and vector
conic-to-quadratic conversion at 0.001 units. Safety adjustments may exceed the
optical threshold or `max_kerning`; explicit overrides and preserved authored
pairs cannot disable this guard. Close curved boundaries still need actual-font
visual inspection. This is a conservative spacing aid, not a mathematical proof
of typographic quality, and no automatic measurement replaces a designer's eye.

## Configuration

Pass `--config spacing-config.json`. Unknown settings, missing override reasons,
unknown glyphs, non-finite values and conflicting dimensions fail explicitly.
Distances and areas use font units and square font units respectively. Defaults
scale from units-per-em except the 10-unit kerning threshold.

```json
{
  "schema": 1,
  "groups": {
    "caps": {
      "zone": [0, 700],
      "overshoot": 20,
      "counter_depth": 200,
      "side_space": 62,
      "min_bearing": 0,
      "max_bearing": 250
    },
    "lowercase": {"zone": [0, 500], "side_space": 55},
    "digits": {"zone": [0, 700]},
    "punctuation": {"zone": [-200, 700], "side_space": 45}
  },
  "glyph_groups": {"A": "caps"},
  "glyph_overrides": {
    "space": {"advance": 280, "reason": "Chosen word-space rhythm."},
    "A": {"left_bearing": 30, "right_bearing": 25, "reason": "Review the diagonal foot separately."}
  },
  "pairs": [{"left": "A", "right": "V"}],
  "pair_overrides": [
    {"left": "A", "right": "V", "value": -70, "reason": "Reviewed AV rhythm."}
  ],
  "kerning_threshold": 10,
  "max_kerning": 200,
  "collision_gap": 10,
  "preserve_existing": true
}
```

Omit `pairs` (or set it to `null`) to consider all drawn pairs for optical
adjustment. An empty list disables optical pair proposals, **not collision
checks**. Existing authored pairs and explicit pair overrides remain visible.
`preserve_existing: true` keeps authored values, unless they become unsafe under
the proposed bearings. Set it to `false` to deliberately regenerate those values.
Every collision-driven change has a reason and retains the requested value for
review. Zero-value pairs are omitted from the resulting project list.

Glyph overrides accept left/right ink bearings, or an explicit advance instead
of a right bearing. A blank glyph only accepts an advance. Fractional curve ink
bounds mean a requested bearing can only be approximated by integer placement;
ordinary group bearing limits remain enforced. Explicit overrides can go outside
those group limits. Pair overrides bypass the optical magnitude limit and
threshold, but never collision safety.

The compiler continues to produce its existing explicit **GPOS** pair positioning
and HarfBuzz verification. No class kerning, legacy `kern` shortcut, implicit
ligatures or coverage guesses are introduced.

## Python API

- `spacing_config(project, config=None)` resolves validated configuration.
- `spacing_plan(project_path, config=None)` returns JSON-safe review data.
- `save_spacing_plan(project_path, output, config=None)` writes a new JSON file.
- `apply_spacing_plan(project_path, plan, output, version)` returns the fresh
  candidate's `fontify.json` path. `plan` may be the returned dict or a JSON path.

Configuration may be a dict or JSON path. Results are deterministic for identical
inputs and versions of the geometry dependencies. Hashes detect edits and stale
inputs; they are not signatures or claims of human approval.

## Work bound

The authoring pass currently supports at most **20,000 drawn-glyph pairs**
(141 drawn glyphs, plus blank space). Larger candidate sets fail before geometry
compilation or pair-set construction. This covers the bundled Latin examples,
not large Unicode repertoires. An optical pair filter does not bypass the bound:
all-pair collision safety is retained. Use an explicitly smaller candidate
character set or manual spacing for larger fonts; class-based large-font spacing
is not implemented.
