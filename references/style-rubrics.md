# Style decision trees and the first-font gate

Use this for **new font work**. Schema-1 profiles and the approved examples keep
their existing behavior; do not migrate or reapprove them merely to try this workflow.
The executable rules are `src/fontify/rubrics.py`, the shared audit/repair code,
and `src/fontify/preflight.py`. All commands run offline.

## 1. Choose defaults, then inspect the source

```sh
fontify rubric-plan work/fontify.json --style handwritten \
  --note 'Friendly contemporary comic lettering, with deliberate lean and bowed strokes.' \
  --output work/quality-v2.json
```

The command reads existing outlines and any profile, writes a **new** schema-2
profile, and leaves the project untouched. Set the candidate's `quality` to that
file. Inspect each ink glyph, replace its placeholder note with a concrete source
observation, resolve its choices, and only then set `confirmed` to true.
Space is mechanically recognized as blank; its spacing still needs visual review.

| Style | Suggested balance | Suggested axes | Suggested weight / review focus |
|---|---|---|---|
| `geometric` | Optical; exact axes chosen individually | Near-axis line classification for polygons; declared regions for curves | Optical; name comparable stem probes when precision is intended |
| `humanist` | Optical | Declared regions | Optical modulation, overshoot and reading rhythm |
| `handwritten` | Asymmetric | Organic | Variable strokes, intended lean and natural curve flow |
| `serif` | Optical | Declared regions | Variable contrast, serif joins and intentional corners |
| `display` | Unresolved | Unresolved | Resolve mixed/decorative construction individually |

These are review strategies, not an automatic font classifier or a complete
taxonomy. A geometric font can need optical asymmetry; a handwritten H can need
exact reflection and a straight crossbar. Existing explicit regions, axes and
probes take priority over style suggestions. No italic/complex-script capability
is added: the compiler still builds static upright fonts.

## 2. Resolve each glyph's branches

Keep the existing `construction`, `symmetry`, `corners`, `straight_regions`,
`stems` and `note` fields. Schema 2 adds these decisions:

```json
{
  "construction": "curved",
  "symmetry": [],
  "straight_regions": [],
  "note": "This upright is deliberately bowed; the uneven terminals retain the source's hand-drawn character.",
  "decisions": {
    "confirmed": true,
    "balance": "asymmetric",
    "axes": "organic",
    "weight": "variable",
    "repairs": []
  }
}
```

| Question | Deterministic branch | Visual branch / correction decision |
|---|---|---|
| Is it blank? | Require a blank source and explicit advance; ink rules are not applicable. | Review word gaps and preservation. |
| Is exact reflection intended? | `balance: exact` requires named `symmetry` axes and source/export reflection checks. | `optical` or `asymmetric` requires an empty axes list; review balance without mirroring. |
| Is an exact straight feature intended? | `axes: declared` checks selected `straight_regions`; a region that matches no edge fails. Selected small or far-from-axis features cannot silently disappear from the audit. | `organic` retains curvature/lean and forbids exact regions; review their flow. |
| Are near-axis lines deliberately geometric? | `near_axis` uses the bounded length/angle classifier for line segments; genuine diagonals remain intact. | Inspect the source before accepting this branch; it is not inferred from Unicode. |
| Are exact widths intended here? | `weight: measured` requires specific stem probes with individual targets; only these are compared. | `optical`/`variable` forbids exact targets; inspect weight in groups and shaped words. |
| Does it contain curves? | Check stationary reversals and unexpected tangent joins; named corners exempt only those joins, never invalid topology. | Inspect every curve/counter at enlarged and reading sizes. Smooth hooks can be intentional; numeric joins can miss facets. |
| May this finding change the drawing? | Only operations in `repairs` may run. Topology, area and bounds limits still apply. | Compare every edit, including ones below the budget; reject/revert an edit that looks worse. |

Choices include `unresolved`, which blocks correction and presentation. Blank
glyphs use `none`; ink glyphs cannot use it. Contradictory choices fail validation.
For schema 2 use `decisions.axes` as the axis policy; `axis_policy` is the legacy
spelling and cannot contradict it.

Straight regions select edges by enclosing **all their control points** in
`[xmin,ymin,xmax,ymax]` font coordinates. They mean intended horizontal/vertical
features; the audit measures the nearer axis. Arbitrary-angle constraints are not
implemented. A large misalignment can need a deliberate local edit: automatic
straightening retains its small-angle safety limit even when the audit flags it.

Allowed repair names are `axes`, `symmetry`, `stems`, `tangents`, `polygonize`,
`patches`. Defaults allow **none**. Automatic stems/polygon simplification require
polygon intent; curved widths need local edits. Tangent edits require curved
intent. A patch also needs a fingerprint-bound explicit patch plan. Never enable
all operations merely to obtain a pass.

Permission alone does not run a numeric repair: it also needs a matching current
finding. Already compliant outlines remain unchanged. Editorial patches can
address visually identified defects that the numeric checks did not detect.
Budgets compare each pass with its input; keep the original artwork as a reference
across passes and compare back before presentation. Do not chain passes to evade
the intended preservation limit.

## 3. Run one internal correction and recheck pass

```sh
# Inspect without editing:
fontify preflight work/fontify.json --out build/pass-01
# If appropriate repairs have been explicitly allowed:
fontify preflight work/fontify.json --out build/pass-02 --repair-version 0.002
# For reviewed local contour replacements, also pass --patches local-patches.json.
```

The pass validates vectors/coverage/metrics, runs routed source checks, optionally
repairs into a fresh candidate, compiles TTF/WOFF2, reopens both and tests actual
HarfBuzz shaping, then audits the exported TTF. A repair pass saves before/after
drafts, a correction journal and an actual-font comparison. It refuses approved
source edits, existing outputs and outputs inside the source; it never publishes
or updates `current.json`.

`preflight.json` records the style, decisions, applicability reasons, numeric
limits/units, results and edit permissions separately. Numeric routes return `passed`, `failed`,
`not_applicable`, or `needs_intent`. Visual work remains explicitly required.

| Result / exit | Next action |
|---|---|
| `blocked` / 1 | Resolve intent, geometry, topology or export failures internally. Inspect the saved failure; do not repeat the same ineffective edit blindly. |
| `needs_visual_review` / 2 | Inspect every compiled glyph and actual shaped samples, retain/revert edits, revise locally and repeat in a fresh output directory. |
| `ready_for_release` / 0 | A current complete receipt exists; run `fontify release` and verify the returned manifest before presenting the first font. |

The agent performs this loop before showing the user a font. The deterministic
command does not judge appearance, create a review receipt or run an AI service.
If a new source generation is needed, preserve accepted glyphs; paid calls still
need separate authorization. If a design choice cannot be resolved from the brief
and source, report that uncertainty instead of inventing an exception.

## 4. Finish visual review and release

Use [preflight.md](preflight.md) for the receipt fields and release commands.
Inspect all six review areas for every glyph: balance, axes, curves/corners,
optical weight, spacing and source preservation. A numeric `not_applicable` does
not waive the related visual area; for blank glyphs explain inapplicability and
inspect the advance. Cite the specific rubric decisions and actual proof files
in the glyph's notes. Do not auto-fill all-pass notes.

Changed style intent, repair permissions, project settings, glyphs or proof bytes
invalidate the bound receipt. The final release still requires passing source
and export audits plus complete evidence. User style approval remains separate;
no numeric score, change budget or stored receipt proves good typography.
