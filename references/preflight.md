# Preflight and first-font handoff

Fontify separates deterministic checks from agent visual judgment. `release_font`
and `fontify release` require both. Low-level `build_font` still supports technical
projects without a quality profile; that is not a reviewed first-font handoff.
Once `quality` is set, even a normal build enforces the gate unless `draft=True`.

## Intent is explicit

Set `"quality": "quality-profile.json"` in the project. Its schema-1 profile has a
`review` path and `glyphs` object with **every** mapped name, including space.
See `examples/imagegen/quality-profile.json` for a complete 27-glyph example.

Each entry has:

- `construction`: `polygon`, `curved` or `blank`. A polygon should contain lines;
  the audit rejects unexpected curves rather than guessing whether rounding is desired.
- `symmetry`: zero or more of `vertical`, `horizontal`. Empty means deliberate
  asymmetric construction; `note` explains why. Reflections are measured about
  the ink bounding-box center. Corrections mirror about the rounded advance center
  and/or rounded vertical ink center; inspect bearings and the resulting design.
- `corners`: optional intentional sharp join coordinates in **font coordinates**.
  Do not list every bad join to silence failures. A diagonal terminal may be a corner.
- `straight_regions`: optional `[xmin,ymin,xmax,ymax]` boxes identifying curved
  trace segments that represent straight features. Curves near an oval's extremum
  are not straight features and must not be flattened merely because they are near-axis.
- `axis_policy`: `near_axis` by default, retaining the geometric-font behavior;
  `declared` checks/corrects only the named `straight_regions`. Use the latter
  for an intentionally handwritten design: a slightly leaning line or gently
  bowed upright is not automatically a defect. Record the actual design intent
  and compare the result; do not use it just to hide failed checks.
- `stems`: optional explicit horizontal probes `{at,index,width,anchor,below}`.
  `at` is y, `index` selects a filled interval from left to right, `width` is its
  target, and `anchor` is `left` or `center`. `below` optionally bounds the edit.
  Automatic stem edits are limited to declared polygon glyphs; curves need local review.
- `note`: concrete construction rationale. A profile is a design choice, not a
  universal rule for every font or a quality result inferred from the letter name.

Defaults: near-axis classification within 3 degrees and at least 30 units;
classified straight edges must then be exact. Tangent joins over 7 degrees are
flagged, except declared corners and tiny trace handles/segments. Small features
remain part of visual review: a one-unit stair can give a meaningless large angle.
Interior cusp checks look for a stationary tangent reversal, and joins check
unexpected tangent breaks. A smooth wide hook is not a cusp merely because its
tangent points more than 100 degrees away from its endpoint chord. Contour
validity runs separately.

The limits are bounded by the implementation to prevent turning off preflight
with absurd tolerances. They are diagnostics; they do not prove smooth curvature,
consistent optical weight, or legibility. The primary example's faceted O counter
passed numeric checks and was fixed only after enlarged visual inspection.

## Internal correction loop

```sh
fontify validate work/fontify.json
fontify audit work/fontify.json --out build/audit-before
# A failed audit exits nonzero and saves its findings.
fontify repair work/fontify.json --out build/candidate-02 --version 0.002
fontify build build/candidate-02/fontify.json --out build/drafts-02 --draft
fontify audit build/candidate-02/fontify.json --font path/to/actual-draft.ttf --out build/audit-after
python scripts/render_quality_review.py path/to/before.ttf path/to/actual-draft.ttf --out build/candidate-02/review-evidence
```

`repair` refuses approved projects, existing outputs and outputs inside the source.
It writes a fresh candidate and `corrections.json`; unresolved audit issues can
remain in that internal candidate and will block release. The original is untouched.
It straightens declared edges, simplifies only declared polygons within the local
epsilon, adjusts explicit polygon stems, makes bounded tangent-handle edits, and
reflects only declared master halves. It does not promise to fix every visual defect.

Each corrected glyph must preserve contour/hole counts and stay within the
profile's area/bounds budgets (defaults: 12% sampled changed area, 6 units per bound).
The generated example explicitly allows 12 units of bound movement; its journal
records actual changes. Area comparison uses identical 0.2-unit subdivisions.
These budgets are guardrails, not aesthetic approval or a license to alter approved forms.

For editorial curve corrections, `repair --patches local-patches.json` accepts a
schema-1 `glyphs` map. Each named patch has the **post-basic-correction** outline
`fingerprint`, a concrete `note`, and `contours`: index-to-path strings in font
coordinates. Each path replaces exactly one selected closed contour; winding is
matched to its original. Other contours remain unchanged. Reflections and the
same overall budgets are checked afterward. A stale fingerprint stops the edit.
`examples/imagegen/source/local-patches.json` is the working example, including
rounded counters and explicit M/W/X notch corrections. Do not apply its geometry
or reset its hashes to fit a different typeface. For a short local segment edit,
edit that portion of the candidate SVG directly and retain a before/after overlay.

## Agent visual review receipt

After inspecting **every** actual compiled glyph and normal-sized shaped text,
write the JSON path named by the profile. The working receipt is
`examples/imagegen/agent-review.json`. It includes:

- `reviewer`, `project_sha256` from `digest(project.data)`, `profile_sha256` and
  `font_sha256` from the **compiled** `audit_project` result.
- `evidence`: saved project-relative `{path,sha256}` proof files.
- `glyphs`: every mapped name, each with its compiled audit `fingerprint`,
  concrete `notes`, and `evidence` paths pointing to the saved proofs.
- Each glyph's `checks` has exactly `symmetry`, `axes`, `curves`, `optical_weight`,
  `spacing`, `source_preservation`, all `passed` only when actually reviewed.
  A blank glyph's notes explain why contour checks are inapplicable and how its
  advance was inspected. Polygon glyphs still need corner/diagonal inspection.

No command auto-fills an aesthetic approval. A text receipt cannot prove that an
agent looked at an image; the skill must do the work and retain honest findings.
It is also not user approval. Never copy the example receipt to a new project.
Changed geometry, project settings (including spacing/kerning), quality intent or
proof bytes invalidate it. The gate rejects absent/incomplete/stale records.

```sh
fontify release reviewed-project/fontify.json --out build
fontify verify-release path/returned/by/release/release-manifest.json
```

Only a passing release updates `current.json`. Drafts have a separate `-draft`
directory and never change that pointer. Present the released proof/font to the
user for final style approval. A subsequent human approval snapshot protects
the reviewed form; it does not replace the per-glyph agent preflight.
