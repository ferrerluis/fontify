# Ten modernized display-font samples

These are the selected final production fonts, integrated locally alongside Fontify's existing examples. Open [the visual catalog](index.html), then a family's live WOFF2 specimen or final TTF preview. Each sample includes its title, description, story, historical inspiration, exact coverage, final font hashes and compact build/provenance notes.

| Sample | Inspiration / selection | Final font version | Mappings | Display minimum |
|---|---|---:|---:|---:|
| [Reedmere](reedmere/README.md) | Papyrus A | 0.025 | 354 | 48px |
| [Presswake](presswake/README.md) | Impact 2A, package v5 | 1.011 | 354 | 48px |
| [Bunvale](bunvale/README.md) | Cooper Black B | 0.016 | 358 | 32px |
| [Lapisent](lapisent/README.md) | Trajan A | 1.003 | 354 | 32px |
| [Liltvale](liltvale/README.md) | Curlz MT A | 0.048 | 354 | 32px |
| [Tessaplay](tessaplay/README.md) | Jokerman B | 0.024 | 354 | 48px |
| [Riftstave](riftstave/README.md) | Chiller A | 0.018 | 354 | 48px |
| [Semiloft](semiloft/README.md) | Bauhaus 93 B, selected M patch | 0.019 | 355 | 32px |
| [Marqevra](marqevra/README.md) | Broadway A, report-r1 package | 0.021 | 354 | 48px |
| [Charterquill](charterquill/README.md) | Old English Text MT A | 0.216 | 354 | 48px |

All ten retain the agreed [354-codepoint expanded-Latin union](required-union.json). Bunvale additionally retains U+201A, U+201E, U+2039 and U+203A; Semiloft retains U+0237. Coverage is an exact inventory, not every Latin orthography. The samples are static Regular display faces, with no body-text certification.

## Sources and construction

Bunvale and Lapisent start from original native Recraft vectors. The other eight start from selected OpenAI raster artwork, followed by recorded tracing and cleanup. Semiloft includes the explicitly selected generated M patch. Supporting glyphs are authored additions or same-family composites. Historical commercial fonts provide inspiration; their font software and outlines are not bundled.

The final TTF/WOFF2 bytes are unchanged from the verified final packages. Full editable projects, original artwork, source-specific compatibility runners and extensive production evidence remain in the exact local packages named by each `provenance.json`. The compact folders here are **final-artifact use samples**, distinct from the source-rebuild demos in `examples/imagegen` and `examples/recraft-mellow`.

All production builds used Fontify commit `249bf421e4be58bac8b42024fb42af264bd39838`. Its plain JSON model cannot admit every extended blank or zero-advance mark. Some producers run a strict project-local adapter through actual Fontify gates; others assemble final layout/marks after a compiler-valid ordinary source. Each README states its boundary. The integration verifier validates actual frozen binaries; it does not invent an unrun full-source CLI release pass.

## Local viewing and validation

Open `index.html` directly. If your browser needs HTTP, serve only this sample directory locally:

```sh
python -m http.server 8765 --bind 127.0.0.1 --directory examples/modernized
# Open http://127.0.0.1:8765/index.html
```

With the existing Fontify dependencies, run from the repository root:

```sh
python scripts/verify_modernized_samples.py --output test-runs/modernized/binary-validation.json
```

This checks exact font/preview hashes, complete coverage including extras, all outlines/metrics in both formats, exact naming/layout tables, every mapped scalar, 173 canonical decomposition pairs per format/family, classified zero-advance marks, focused mixed contexts and native whitespace/control behavior. Fresh installed-Chrome specimens also load the actual supplied WOFF2 without fallback. [The integration report](../../docs/modernized-font-integration/REPORT.md) records evidence and test results.

## Review, limitations and terms

Nine final packages, including Liltvale 0.048, have independent clearance reported by the integration coordinator. Charterquill's current 0.216 has additional local raw/source preservation, source-to-final outline, language, mixed-mark, control and actual 48/72/96px checks; the earlier remote review alone is not claimed to cover this revision. Final human aesthetic approval remains separate for every family.

Read each family's limitations. Liltvale needs high contrast and generous line height. Tessaplay's specified stress cases extend 13/78 units below its typographic descender. Bunvale's ordinary į is correct; precomposed į plus an extra above accent remains convention-unreviewed and is omitted from the shared sample phrase. Quieter authored companions remain taste decisions. Some Chrome discretionary-hyphen layouts differ positionally from forced references while real native-font semantics pass. Arbitrary accent stacks and every rendering engine are not certified.

**Distribution terms remain pending owner review.** No new MIT license or unrestricted redistribution right is assigned to these sample font assets. The existing repository code license is unchanged. No publishing, external upload or combined upload is authorized by this local integration. The separate Charterquill upload hold remains in force and includes font-derived payloads; no transfer route was attempted here.
