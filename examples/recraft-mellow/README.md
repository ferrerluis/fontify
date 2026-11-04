# Fontify Mellow: one Recraft Vector experiment

A friendly, informal contemporary comic-inspired typeface sample. The original
52-letter sheet was generated once with the official remote MCP and
`recraftv4_1_vector`, using **4 Studio subscription credits** on 2026-11-03.
No API token or additional generation was used. The raw SVG, exact prompt,
request, extraction plan and sanitized provenance are in `source/`.

```sh
fontify release examples/recraft-mellow/fontify.json --out build
# Open build/FontifyMellow-Regular-v0.002/proof.html
python -m http.server 8769 --bind 127.0.0.1 --directory build/FontifyMellow-Regular-v0.002
```

This build is entirely offline. Exact coverage: **A–Z, a–z, space (53 mappings)**,
plus `.notdef`. No digits, punctuation, accents or other characters are implied.
The generated two-loop g was retained even though the prompt requested a
single-storey g. Tall ascenders and organic stroke curvature are intentional.

## What the checks changed

Only **H, Z and q** differ in the actual compiled outlines from the first sample:
H's declared alignment, a small outer tangent kink on Z, and q's pointed top
terminal. The other 49 letter outlines are identical after compilation. The
original artwork is preserved, and local changes are recorded in `corrections.json`.

The first geometric profile tried to mirror X: its 24.33% changed-area result
exceeded the preservation guard, which stopped the edit. A later numeric pass
introduced visible cap/dot defects in I/i/l; enlarged review rejected those edits
too. Both rejected profiles are saved in `source/rejected-profiles/`. Passing a
numeric check is not permission to force an organic font into geometric symmetry.

This example uses `axis_policy: "declared"`: only named straight regions are
axis-corrected. Its other curves, lean and optical asymmetries remain source design
choices. All glyphs still undergo topology, curve/cusp, export, coverage, metrics
and shaping checks plus per-glyph visual review. `agent-review.json` records the
findings and saved actual-font before/after sheets. The user approved this design
and the name **Mellow** on 2026-11-03. `approved-v0.002.json` now protects every
mapped glyph; `user-approval.json` records the decision and exact font hashes.
Adding this baseline changes no TTF/WOFF2 bytes. Further drawing changes require
a separately reviewed proposed revision, rather than refreshing this baseline.

## Reproduce vector preparation and corrections

```sh
python scripts/prepare_recraft_sheet.py examples/recraft-mellow/source/extraction-plan.json --out build/mellow-extracted
fontify build build/mellow-extracted/fontify.json --out build/mellow-raw --draft
fontify repair examples/recraft-mellow/source/extracted-v0.001/fontify-preflight.json --out build/mellow-repaired --version 0.002 --patches examples/recraft-mellow/source/local-patches.json
fontify build build/mellow-repaired/fontify.json --out build/mellow-drafts --draft
```

The helper checks the source hash and explicitly maps the reviewed row order.
It preserves separate dots, converts painted white counter shapes to actual
holes, removes the paper background and applies one common scale with declared
row baselines. It joins only tiny edges whose controls collapse to one integer
point at font export; it does not raster-trace, fit curves or infer missing letters.
Glyph filenames use Unicode values so uppercase/lowercase do not collide on
case-insensitive filesystems. The frozen extracted stage lives in `source/extracted-v0.001/`.

The final project includes a complete review receipt and can be released directly.
Fresh edited candidates require current preflight; a raw/draft build is not a
first-font handoff. Review figures use equal sizes and baselines, with enough
height to show full descenders. The comparison tool reports source-only edits
separately from actual exported-outline changes.
