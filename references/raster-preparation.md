# Optional raster preparation

This authoring step applies only to bitmap artwork. Recraft vector generation and
native SVG compilation **do not call it**, do not rasterize outlines, and do not
need Pillow, NumPy, or Potracer. A native SVG/PDF/EPS passed to this helper is
rejected. Install the optional authoring tools with `pip install -e '.[raster]'`.
Use the pinned `requirements.lock` when reproducing a reviewed result.

Run a reviewed crop plan with:

```sh
fontify trace-sheet path/to/trace-plan.json --out candidates/trace-v2
# The existing script remains an equivalent entry point:
python scripts/trace_generated_sheet.py path/to/trace-plan.json --out candidates/trace-v2
```

The plan's directory must also contain `fontify-base.json`, the explicit font
metadata and coverage used by the existing example. The output directory must
not exist. A candidate is published only after ordinary SVG topology and metrics
validation succeeds. Nothing here approves or releases a font.

## Compatibility and scope

A schema-1 trace plan **without** a `preparation` field retains the legacy
threshold/crop/pad/Potrace behavior, including crop-width-derived advances. The
frozen ImageGen example still reproduces its font project and SVGs byte for byte.
Adding `"preparation": {"schema": 1}` explicitly selects the new behavior:
retention of every component by default, ink-based placement and advance, and
retained intermediate evidence. Unknown preparation fields and versions fail
rather than silently doing nothing.

The existing plan fields remain required: `schema`, `image`, `source_sha256`,
`image_size`, `threshold`, `cap_height`, `svg_baseline`, `sidebearing`, `rows`,
`trace`, and `glyphs`. See `examples/imagegen/source/trace-plan.json` for a complete
base plan. Prepared `cap_height` and `svg_baseline` must match `fontify-base.json`.
Each row declares its original-sheet `baseline` and `pixels_per_cap`; one uniform
scale applies to both axes of every glyph in that row. The original source image
hash and dimensions are checked before preparation. Animated/multi-frame inputs
are rejected: choose one frame explicitly first. Transparency is composited on
white in prepared mode; legacy grayscale conversion is unchanged.

## Version 1 preparation plan

The following is an illustrative `preparation` field. Replace all coordinates
and glyph names with reviewed values from your sheet; it is not an automatic
cleanup recipe.

```json
{
  "schema": 1,
  "masks": [
    {"kind": "guide", "box": [0, 240, 900, 241], "reason": "Printed template rule"},
    {"kind": "label", "box": [0, 0, 40, 25], "reason": "Cell identifier, not artwork"}
  ],
  "protect_boxes": [
    {"box": [110, 230, 125, 250], "reason": "Letter stroke crosses the rule"}
  ],
  "components": {
    "connectivity": 8,
    "small_area_max": 4,
    "glyphs": {
      "i": {
        "preserve": [
          {"point": [118, 70], "reason": "The detached dot belongs to i"},
          {"point": [130, 160], "reason": "Intentional texture"}
        ],
        "remove": [
          {"point": [149, 112], "reason": "Reviewed isolated scan speck"}
        ]
      }
    }
  },
  "resample": {"scale": 4, "filter": "nearest", "threshold": 128}
}
```

All boxes and selector points use integer **original sheet coordinates**, with
x increasing right and y increasing down. Boxes are half-open `[left, top, right,
bottom]`. They are not glyph-relative, font units, or resampled pixels. Regions
outside a glyph crop have no effect on it.

### Guide and label removal

Only the explicitly listed rectangular masks erase pixels. `kind` must be
`guide` or `label`; every entry requires a reason. There is no guessed grid,
label detector, morphology, background reconstruction, or line erasure.
`protect_boxes` override masks pixel by pixel, preserving the original pixels
inside the protected region. A mask across a glyph can destroy a real stroke;
inspect the raw/cleaned comparison and protect crossing strokes explicitly.
Where a guide and artwork share the same pixels, the original artwork is not
recoverable automatically. Keep uncertain pixels and review rather than infer
replacement ink.

### Connected components

Components are measured **after** the rectangular masks. Connectivity is `4` or
`8` (default `8`). Stable IDs follow a top-to-bottom, left-to-right scan. Reports
classify them as `primary_ink`, `detached_ink`, or `small_candidate` using area;
`small_area_max` defaults to `4`. These labels are descriptive, not a claim that
a component is noise. **No component is removed based on size or class.**

To remove a component, name its glyph and select an existing foreground pixel
with a review reason. The entire connected component containing that point is
removed. A selector on blank, erased, or out-of-crop pixels is an error. Never
select a speck joined to a real stroke without reviewing the entire component.
Explicit `preserve` selections take precedence over `remove`, including when
they point at different pixels of the same component. The report retains both
reasons. Unselected dots, accents, punctuation and texture remain intact.
`trace.turdsize` must be explicitly `0` in prepared mode so Potrace cannot silently
remove these small components afterward. Review interpolation too: a non-nearest
filter or changed resampling threshold can alter tiny marks despite preservation
at the cleanup stage.

### Optional pre-trace resampling

`resample` defaults to scale `1`, filter `nearest`, threshold `128`. Scale is a
uniform integer from `1` through `8`; this is interpolation, not generated detail
or AI enhancement. Filters are `nearest`, `bilinear`, `bicubic`, and `lanczos`.
The input is the cleaned binary mask. It is cropped to its ink bounds and given
a fixed four-source-pixel white border before interpolation and rethresholding.
The border supports all listed filters, makes output independent of arbitrary
empty crop padding, and avoids clipping edge filter support. A scale of `1`
performs no interpolation. A source or resampled glyph above 40 million pixels
is rejected to bound memory use.

Keep the original image and inspect counters, joins, tiny components and stroke
weight at actual font sizes. Resampling cannot invent genuine high-resolution
source detail, guarantee topology, or replace visual approval.

## Coordinate mapping, metrics and evidence

Prepared glyphs are traced using their actual foreground bounds after resampling.
The leftmost ink is positioned at the declared sidebearing; advance is the
foreground width in font units plus two sidebearings, rounded to an integer.
Extra empty pixels around an unchanged source crop do not change the SVG,
placement, advance, or resampled mask. No glyph is stretched to a target width or
height. Vertical placement uses the original-sheet baseline, not the cropped
bounding-box bottom. Overshoot and detached marks retain their source positions.

A `trace-record.json` schema-2 report contains the versioned preparation plan,
original source and plan hashes, base metadata hash, effective resampling options,
package versions, each component's classification and decision, source-coordinate
ink bounds, baseline, row scale and resampled-to-source mapping. It retains
mask-erased and protected pixel counts. Every glyph saves:

- `masks/<name>/raw.png`: thresholded, unedited source crop.
- `masks/<name>/cleaned.png`: original-sized crop after explicit masks/removals.
- `masks/<name>/resampled.png`: canonical, padded mask used before tracing.
- SHA-256, dimensions and foreground-pixel count for each mask.

`source/original.<ext>` retains the original source bytes. `source/trace-plan.json`
and `source/fontify-base.json` retain exact reviewed inputs; the plan snapshot's
image path is the original path, not rewritten to the evidence copy. To rerun,
use the original source layout or restore the retained bytes at that relative
path. The original artwork and input plan are never changed. The output includes
ordinary SVGs and `fontify.json`; all downstream font compilation remains
vector-only and `review_required`.
