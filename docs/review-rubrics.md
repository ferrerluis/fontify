# Review themes and a proposed decision tree

Status: findings from the image-generated Grotesk and Recraft-generated Mellow
experiments, plus a proposal for review. This is **not** an implemented automatic
style classifier or a new profile schema. The current executable rules are in
[preflight.md](../references/preflight.md).

## Themes to review

1. **Symmetry must follow intent.** Mirroring Mellow X would change 24.33% of
   its filled area and was refused; later I/i/l edits passed numeric checks but
   made their caps or dots worse and were reverted. Require exact reflection
   only where declared; otherwise measure balance and review the actual shape.
2. **Straightness belongs to a feature, not a font category.** An organic font
   can have exact crossbars and deliberately bowed or leaning uprights. Route
   0/90-degree checks to named straight features; preserve intended lean and
   genuine diagonals rather than snapping every almost-vertical segment.
3. **Curves need more than a smoothness score.** Mellow g's smooth wide hook
   exposed a false cusp heuristic; Grotesk O's faceted counter passed numeric
   checks. Use derivative/join diagnostics for specific faults, declare intended
   corners, and inspect every curve enlarged and at reading size.
4. **Equal measurements do not prove equal optical weight.** Tall ascenders,
   overshoot, differing bowl widths and varying stroke widths can be deliberate.
   Apply exact stem targets only to declared comparable features; review visual
   weight and rhythm in groups and shaped words for every style.
5. **Artwork preparation and design revision are different operations.** Recraft
   supplied white painted counters, separate dots and tiny edges that collapsed
   at integer export. Convert the artwork explicitly, preserve the raw source,
   and keep contour/export validation mandatory; never silently smooth the design.
6. **Small changes still need review.** A change budget stopped X, but did not
   stop the harmful I/i/l edits. Preserve approved glyphs, compare actual compiled
   outlines separately from source formatting, and review every proposed edit
   even when it falls below a numeric limit.
7. **Spacing must be tested in use.** HarfBuzz can verify that declared pairs
   actually apply and covered text avoids missing glyphs; it cannot decide that
   the spacing looks good. Always inspect real mixed-case words and kerning
   on/off at matched sizes, with coverage stated explicitly.
8. **The proof and the review are part of the gate.** Our first lowercase review
   sheets clipped descenders even though the font was valid. Verify proof bounds,
   common scale/baseline and actual exported outlines; require complete agent
   review before the user sees the first font, while keeping user taste approval
   separate from technical and agent passes.

Evidence: [Mellow experiment](../examples/recraft-mellow/README.md),
[Grotesk experiment](../examples/imagegen/README.md),
[iterations B08–B13](iterations.md), and
[Ferrer lessons](ferrer-lessons.md). Mellow's final compiled changes are H, Z and q;
the other 49 letter outlines match the initial compiled sample. This is one
experiment, not proof that these rules generalize to every typeface.

## Proposed routing

Font type should supply defaults, not decide every glyph's treatment. Even a
geometric font can need optical asymmetry, and a handwritten font can contain
precise straight features. Resolve uncertain intent internally from the brief,
source and comparisons before treating a measurement as a design requirement.

| Decision | Run / action | When it blocks presentation |
|---|---|---|
| Is the input valid for the supported font pipeline? | Always check safe vectors, closed nondegenerate contours, holes, coverage, mappings, metrics, compilation and release integrity. | Any invalid or unsupported input; intentional artwork still needs an explicit supported representation. |
| Is this an approved glyph? | Always check source, mapping, placement, advance and compiled preservation. | Unapproved changes to a protected glyph; create a separate proposed revision instead of resetting the baseline. |
| Is exact reflection part of this glyph's design? | Yes: measure declared axes in source and export. No: review optical balance without enforcing reflection. Unknown: review intent first. | A declared exact rule fails, or uncertain intent remains unresolved. |
| Is this feature intended to be exactly straight? | Yes: check its declared direction; apply 0/90-degree rules only to intended horizontal/vertical features. No: preserve its curve or lean. | Declared straightness fails; a near-axis angle alone does not justify correction. |
| Is a curve join intentionally sharp? | Declared corner: retain it while checking topology. Otherwise: investigate tangent breaks and stationary reversals; always review curve flow. | An unexplained defect remains; a wide hook alone is insufficient evidence. |
| Are these stems meant to have a shared width? | Yes: test explicit probes/targets. No: use measurements as diagnostics alongside optical review. | A declared target fails, or visible weight problems remain unresolved. |
| Did a correction improve the shape? | Check change budgets/topology, recompile, compare every edited glyph and affected shaped samples. | Budget failure, worse appearance, or insufficient evidence; passing the budget never approves the edit. |
| Are the final artifacts ready to show? | Always reopen TTF/WOFF2, test real shaping/kerning, verify proofs and bind every glyph's review to the final bytes. | Missing, stale or unresolved checks/reviews. |

The correction loop remains: diagnose → propose a local edit → check limits →
export → recheck → inspect → retain or revert. It runs before presentation.
An inconclusive style decision returns to internal review, rather than silently
disabling a rule or asking the user to find the first defects.

## Turning this into executable rubrics

Each future rubric should record its scope (font/glyph/feature), applicability
facts, deterministic measurement and units, threshold and rationale, allowed
correction, evidence and result. Keep **check applicability**, **check result**
and **permission to edit** separate: a finding does not authorize a repair.

Use explicit outcomes such as passed, failed, not applicable with a reason, and
needs visual review. The current receipt requires each review area to be resolved
and marked passed with concrete notes; it does not yet implement those richer
outcomes or automatic routing. Current profiles already support declared symmetry,
corners, axis regions and stem targets, so reviewed branches can be expressed
without inventing an entirely new compiler.

Before choosing more thresholds, use the retained accepted/rejected examples as
regressions: reject true cusps, retain g's smooth hook and organic lean, catch the
faceted O, and reject the pinched I/i/l results. Later style presets need more
examples than these two fonts, including serif, italic and high-contrast designs;
supporting an italic preset would also require lifting the current upright-only
font metadata limitation. No new preset or universal optical score is claimed here.
