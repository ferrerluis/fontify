# Project format (schema 1)

Use `examples/imagegen/fontify.json` as a complete reviewed runnable source. Unknown fields
are rejected, so a misspelled setting cannot silently produce the wrong font.

```json
{
  "schema": 1,
  "family": "My Alphabet",
  "style": "Regular",
  "version": "1.000",
  "units_per_em": 1000,
  "ascender": 800,
  "descender": -200,
  "cap_height": 700,
  "x_height": 500,
  "svg_baseline": 800,
  "curve_error": 0.25,
  "required_characters": "AV ",
  "glyphs": [
    {"name":"space","unicode":"U+0020","source":null,"advance":300},
    {"name":"A","unicode":"U+0041","source":"glyphs/A.svg","advance":660},
    {"name":"V","unicode":"U+0056","source":"glyphs/V.svg","advance":660}
  ],
  "kerning": [{"left":"A","right":"V","value":-70}],
  "samples": ["AV AV"],
  "approval": null
}
```

Family/style use ASCII letters, digits and spaces, beginning with a letter.
Version is a string with three fractional digits, such as `1.001`. `copyright`
and `license` are optional strings recorded in the font; the library's MIT
license does not grant rights to any supplied artwork. `line_gap` defaults to 0.
The first release builds upright Regular metadata; use `style: "Regular"`.

Every glyph has a unique name, one Unicode scalar (`U+0000` notation, 4–6 hex
digits), an integer positive advance in font units, and a local source path.
Space is mandatory, blank and explicitly mapped. `.notdef` is generated and
unmapped. Control characters and surrogate codepoints cannot be drawing glyphs.
Supplementary Unicode mappings are supported through fontTools' Unicode cmap.

For new skill projects, use `fontify coverage-plan` and copy its `coverage`
object, `required_characters` and `samples`. The fixed five-language baseline is
mandatory; see [character-coverage.md](character-coverage.md) for the exact
Unicode inventory, on-request language selection and normalization behavior.
The project loader rejects missing profile mappings or reduced requirements;
export checks both TTF/WOFF2 and adds the mandatory specimens to proofs.

`coverage` has `profile: "en-es-fr-it-pt-v1"`, a `languages` list (always retaining
en/es/fr/it/pt), `additional_characters` and `request_note`. The last two default
to empty strings. Extra languages or characters require a nonempty request note.
Unknown profile names/language codes/fields fail. Historical unprofiled subset
projects still rebuild unchanged; that is not the contract for new skill work.
U+00A0 and U+202F, like U+0020, require `source: null` and positive advances.
Profiled exports require NBSP to match the ordinary space advance and narrow
NBSP to be no wider. Other drawing glyphs still need local SVG sources.

`required_characters` lists the minimum coverage, not an assumed character set.
Extra mappings are reported too. A missing required mapping or unsupported proof
sample is an error; no lowercase aliasing or fallback glyph is invented.

## Coordinate contract

One SVG coordinate unit is one font unit. SVG viewBox is required for a valid
canvas, **not** an instruction to resize or center the artwork. Root width/height
do not scale it. In the usual y-down SVG frame, `font_y = svg_baseline - svg_y`
and `font_x = svg_x`. This retains intentional overshoots and relative widths.

A glyph can specify `transform: [a,b,c,d,e,f]`, applied **after** the SVG-to-font
y flip. It means `x' = a*x + c*y + e`, `y' = b*x + d*y + f`. All such changes are
explicit, fingerprinted, and must be reviewed. `<g>` and `<path>` may also use
`matrix`, `translate`, `scale` or `rotate` transforms in SVG order. Singular or
non-finite transforms fail. There is no automatic per-letter bounding-box fit.

The source x position sets the left sidebearing; `advance - xMax` is the right
sidebearing. Negative bearings are reported for review, not silently removed.
Ink outside the ascender/descender fails to prevent accidental line clipping.
Do not thin a letter by scaling its whole width; stems and width/height ratio
are separate visual decisions. Change the actual source outlines deliberately.

## SVG contract

- Allowed drawing elements: root `<svg>`, `<g>`, `<path>`; `<title>`/`<desc>` are
  ignored. Paths support line, quadratic and cubic commands and their relative
  and smooth forms. Close **every** contour with `Z`.
- Use black filled paths with the nonzero rule. Nested contours need opposite
  winding for counters. Compilation reverses contour direction when needed for
  TrueType; that operation does not relocate any points.
- Unsupported: strokes, arcs (`A`), shapes, `<use>`, images, text, CSS/styles,
  clipping, masks, effects, gradients, opacity and background artwork. Convert
  them explicitly to clean individual paths in your editor; do not submit a
  whole Recraft concept sheet as one mapped glyph.
- Sources must stay within the project directory, including resolved symlinks.
  DTDs, entities and external XML references are disabled. Size, nesting, segment,
  coordinate and diagnostic complexity limits keep errors bounded.

Topology diagnostics reject zero-area contours, crossings, touching edges and
same-winding nested counters. They use curve subdivision at 0.2 font units and
can miss very small tangencies or report near-touching artwork for manual review.
Skia PathOps is used for measurements, not outline simplification in the compiler.

## Review files

`quality` names a project-local intent profile. It is mandatory for `release`;
see [preflight.md](preflight.md) for all-glyph intent, exact-axis/curve checks,
bounded authoring corrections and the required agent visual review receipt.
The receipt is invalidated by changed project settings, font bytes or proof files.
Legacy low-level builds without `quality` remain possible and are not preflight-qualified.

`fontify snapshot` writes a fresh baseline with source-byte, normalized-outline,
compiled-outline, Unicode and advance fingerprints, plus construction settings.
It does not confer approval. Set `approval` only after reviewing the actual fonts
and proofs. A baseline can protect a subset; additions remain explicitly unreviewed.

`fontify compare` checks both release manifests' artifact hashes, then overlays
actual compiled glyphs in red/blue at a shared baseline and scale. It also reports
added/removed/changed records, global metrics and kerning changes. An overlay
cannot infer intent; inspect counters, corners, stems and text before reapproval.
Source-only record changes are reported separately from exported-outline and
mapping/advance changes. A reformatted SVG can change a conservative source hash
while leaving the actual compiled shape identical; both facts should be visible.
