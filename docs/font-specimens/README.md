# Font specimen PDFs

One eight-page PDF per family, using the cream paper, rust headings and large font titles of the Bunvale review specimen. These documents use the latest corrected local review fonts as of 10 November 2026, including Bunvale 0.023. They do not use the older binaries from the earlier modernized-sample integration.

| PDF | Font version | Mapped characters | Intended display minimum |
|---|---:|---:|---:|
| [Reedmere](Reedmere-v0.030-specimen.pdf) | 0.030 | 354 | 48 px |
| [Presswake](Presswake-v1.021-specimen.pdf) | 1.021 | 354 | 48 px |
| [Bunvale](Bunvale-v0.023-specimen.pdf) | 0.023 | 358 | 32 px |
| [Lapisent](Lapisent-v1.007-specimen.pdf) | 1.007 | 354 | 32 px |
| [Liltvale](Liltvale-v0.080-specimen.pdf) | 0.080 | 354 | 32 px |
| [Tessaplay](Tessaplay-v0.032-specimen.pdf) | 0.032 | 354 | 48 px |
| [Riftstave](Riftstave-v0.023-specimen.pdf) | 0.023 | 354 | 48 px |
| [Semiloft](Semiloft-v0.034-specimen.pdf) | 0.034 | 355 | 32 px |
| [Marqevra](Marqevra-v0.036-specimen.pdf) | 0.036 | 354 | 48 px |
| [Charterquill](Charterquill-v0.306-specimen.pdf) | 0.306 | 354 | 48 px |

Each PDF contains:

1. Uppercase and lowercase alphabets, both pangrams, and a sample at the font's intended minimum size.
2. Numerals and common symbols, plus real kerning-on/off comparisons.
3. Period, comma and both slashes on each side of r/w/y/e, plus unencoded helper glyphs where present.
4. Five inventory pages covering every mapped character beyond A-Z/a-z, including isolated combining marks and labeled blanks.

The specimen glyphs are the exact TTF vector outlines positioned with HarfBuzz. They remain sharp at any zoom and do not require the fonts to be installed. PDF labels use embedded DejaVu Sans; specimen glyphs are outlined rather than substituted or embedded as a font. Text samples also carry ActualText, although text extraction support varies by PDF viewer.

## Versions and scope

[sources.json](sources.json) identifies exact source TTF hashes. [validation.json](validation.json) binds the verified PDF hashes to their fonts, coverage and checks. The original font binaries, source projects and earlier evidence remain unchanged and are not added by this specimen-only update.

The eight-page layout preserves the supplied font shapes and spacing. It is a specimen, not a new assertion of universal rendering quality, language coverage or body-text suitability. Rasterization can vary across screens and printers. Printing at actual size preserves the stated point sizes; 1 CSS px is represented as 0.75 pt.

The PDFs are uploaded at the owner's request. This does not assign a new license to the font artwork or change the repository's code license. Source provenance and any wider distribution license remain separate.

## Rebuild and verify

The exact TTF inputs must be supplied separately in one directory. The generator rejects unexpected font hashes. With ReportLab, fontTools, uharfbuzz and pypdf available, run from the repository root:

```sh
python scripts/build_font_specimen_pdfs.py \
  --fonts /path/to/exact-fonts \
  --label-font /path/to/DejaVuSans.ttf \
  --label-bold-font /path/to/DejaVuSans-Bold.ttf
python scripts/verify_font_specimen_pdfs.py --fonts /path/to/exact-fonts
```

Generation checks every drawn glyph's bounds. The independent verifier reopens each PDF, checks complete inventories, versions, footer numbering, pangrams, punctuation tests and kerning, and compares every used glyph form's actual vector path to the source font. Render all pages with Poppler and inspect them after changes; structural verification is not a substitute for visual review.
