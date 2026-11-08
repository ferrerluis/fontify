# Intended-use and size-specific release evidence

New `rubric-plan` output uses quality-profile schema 3. Schemas 1 and 2 remain
readable with their original review contract and proof bytes, so archived approved
examples can still be reproduced. Replanning an old project opts into schema 3.

This is display QA of the **final compiled font**, not source tracing. Native
vector artwork stays vector artwork. A vector-generated source does not need a
raster-to-vector step. Final TTF and WOFF2 fonts must nevertheless be rendered at
intended use sizes to inspect their actual pixels.

## Declare the use and supported sizes

A schema-3 profile keeps the existing per-glyph rubric decisions and adds:

```json
"proofing": {
  "intended_use": "text",
  "sizes_ppem": [12, 16, 24, 48],
  "min_supported_ppem": 12,
  "rationale": "Reading text must remain distinguishable at 12 pixels."
}
```

The Python planner and CLI default to an explicitly recorded text-use plan. Text
plans must include 12, 16, 24 and 48, and may add smaller or intermediate sizes.
Sizes are sorted unique integer pixels per em, from 6 through 512. The declared
minimum must equal the first size. At least two sizes are required.

A display font may declare, for example, `[32, 64, 96]` with a minimum of 32 and an
explicit rationale explaining its title-only use. It does not acquire a claim of
text-size legibility by passing at those larger sizes. The `display` visual style
and `display` intended use are separate decisions.

```sh
fontify rubric-plan fontify.json --style display --note "Decorative title face" \
  --intended-use display --sizes 32 64 96 --min-size 32 \
  --size-rationale "Title artwork only; not supported below 32 CSS pixels." \
  --output quality-plan.json
```

## Produce real, fixed-size proofs

Install `fontify[proof]`. TTF proofs require Pillow with FreeType and RAQM/HarfBuzz.
Browser capture requires Playwright and an installed Chromium/Chrome browser.
Historical builds do not import these optional renderers.

A schema-3 draft build automatically saves:

- `size-ttf-12.png`, etc.: actual TTF pixels at exactly the declared ppem, device
  scale 1, without shrinking text to fit an image width. Longer content expands
  the canvas; bounding-box padding preserves overhangs.
- `size-proof.html`: live embedded WOFF2 samples at exactly those CSS pixel sizes.
  These are font-rendered text, not SVG outline facsimiles.
- `size-proof-evidence.json`: font and proof hashes, fixed size/unit, renderer and
  version, pixel dimensions, samples, and **unreviewed** records. WOFF2 screenshot
  records stay empty until a real browser captures them.

Do not add screenshots to a frozen draft/release directory: its manifest hashes
all original artifacts. Generate a separate bundle inside the source project's
relative evidence directory so the review receipt can reference it safely:

```sh
fontify size-proofs fontify.json path/to/draft/release-manifest.json \
  --out evidence/size-v1
fontify capture-size-proofs evidence/size-v1/size-proof.html \
  evidence/size-v1/size-proof-evidence.json --browser /usr/bin/google-chrome
```

Omit `--browser` to use Playwright's installed Chromium. Capture verifies the
embedded WOFF2 hash, successful font loading, each sample's text and computed CSS
size, and actual browser/device scale. It saves actual browser PNGs. Pillow never
fills in browser evidence. Scale 1 is required for release; optional scale-2
captures are additional evidence, not a substitute.

Generators refuse existing proof filenames. Browser capture also refuses to
replace reviewed records or existing screenshots. If a capture fails after some
PNGs were saved, those files remain unreviewed; retain them for diagnosis and use
a new evidence directory for the retry.

Every size covers all mapped characters and project word samples. Covered
confusable groups such as `Il1`, `O0`, `rn/m`, `CG` and `EF`, punctuation, and mixed
case are included automatically. A limited all-caps repertoire never silently
uses fallback lowercase: absent categories have empty sample lists and require
explicit not-applicable findings. Coverage strings are split into bounded lines;
font size is never adjusted to fit.

## Inspect and record findings

Generation and capture do **not** review the images. Inspect actual PNGs at 100%
scale, plus the existing enlarged glyph and before/after proofs. Look for closed
counters, missing strokes, unstable apparent weight, ambiguous characters,
punctuation loss, spacing rhythm, and mismatches between native TTF and browser
rendering. Revise or restrict the supported minimum where warranted, then rebuild
and review new evidence. A font-byte change invalidates earlier size reviews.

Schema-3 profiles require a **schema-2 review receipt**. It retains the existing
reviewer, project/font/profile hashes, per-glyph fingerprints, linked evidence,
and six per-glyph review checks. Add `size_reviews` copied from the separate
bundle, adjusting every `proof` and browser `html` path to be relative to the project root, for
example `evidence/size-v1/size-ttf-12.png`. Keep hashes and renderer records exactly
as captured. Each record must include:

- `format`: `ttf` or `woff2`; the hash of that actual final-format font.
- `size`, `size_unit` (`ppem` or `css_px`), and `device_scale`.
- `renderer` with kind/name/version and FreeType/shaping details or browser engine,
  user agent, successful font loading, and the source `html` path and hash.
- `proof`, `proof_sha256`, `pixel_dimensions`, and the exact generated `samples`.
- `status: "passed"` **only after inspection**, and seven concrete findings:
  `legibility`, `counters`, `optical_weight`, `spacing`, `confusables`,
  `punctuation`, and `mixed_case`.

Each finding is an object with `status` and `notes`. Applicable findings must be
`passed`; a genuinely absent repertoire category must be `not_applicable` with an
explanation. Notes must describe what was observed at that size. Empty notes,
"passed", missing checks, generated pending records, and unresolved defects do
not satisfy the gate. The software checks structure and staleness; the reviewer
remains responsible for truthful visual observations and typographic judgment.

Example finding structure, to fill with actual observations rather than copy as
an approval:

```json
"findings": {
  "legibility": {"status": "passed", "notes": "Describe the actual observed result at this size."},
  "counters": {"status": "passed", "notes": "Name the inspected counters and their observed behavior."},
  "optical_weight": {"status": "passed", "notes": "Describe relative stroke weight in these rendered samples."},
  "spacing": {"status": "passed", "notes": "Describe word and pair rhythm at this size."},
  "confusables": {"status": "passed", "notes": "Identify the covered groups and distinguishing features."},
  "punctuation": {"status": "passed", "notes": "Identify visible punctuation and its baseline/spacing behavior."},
  "mixed_case": {"status": "passed", "notes": "Describe the observed uppercase/lowercase relationship."}
}
```

`release` and `preflight` reject missing format/size combinations, stale font or
PNG hashes, wrong units, absent scale-1 evidence, incomplete covered samples,
unidentified renderers, non-browser WOFF2 substitutions, and missing/unresolved
findings. An old generic checklist cannot release a schema-3 font. Passing the
agent evidence gate does not imply the user's design approval.
