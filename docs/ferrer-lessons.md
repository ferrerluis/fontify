# Ferrer evidence and resulting safeguards

Read-only review on 2026-11-03 of local session
`01a18e47-5d10-7d02-a776-8c3147b5a68d` ("Design my own branding font") and the
Ferrer workspace. No Ferrer files were modified or copied into this repository.
Ferrer artwork and its personal attribution are not part of Fontify's MIT demo.

## What was verified locally

- The session starts with the existing CREATOR lettering, three concept images,
  selection of a faithful extension, extraction, symmetry and later stem corrections.
  Letters absent from CREATOR and all lowercase were designed extensions, not
  recovered original characters.
- The user reported altered width/height and spacing in wordmarks, unexpected
  rounding on straight edges, hard corners in bowls, filled/narrow counters and
  broad thinning that changed k, S/s, g and y. Multiple targeted revisions followed.
- The user explicitly approved stopping at 010 and using it in Drive. This is
  approval evidence; picking the newest-looking directory would not establish it.
- `release/Ferrer-font-v1.010/Ferrer-font-manifest.json` states version 1.010 and
  approved revision 010. All 111 listed artifact hashes matched the local files.
- The actual TTF has 53 Unicode mappings: uppercase A–Z, lowercase a–z and space;
  54 glyphs including `.notdef`. Its name table says Version 1.010. The 16.16
  `head.fontRevision` is approximately 1.0099945, normal binary quantization.
- The release TTF SHA-256 is
  `fc1144c56a553fecf7191c03e9e7b7cc5caef2bd86132e2759a36743c7af35c2`.
  The release WOFF2 SHA-256 is
  `b4ebfb01c4ae49e33c06c202421ec872370dbe3954f70cfdf6087a2538455c82`.
- The root `Ferrer-font-README.txt` and `Ferrer-font-project.json` still describe
  1.002, and root `build_font.py` is an older extraction/stem workflow. Re-running
  those is not evidence of rebuilding approved 010.

The local artifacts/session were accessible. Current Google Drive contents,
installed system font caches, apparel production and the visual approval of every
individual curve were not independently revalidated in this task.

## Lessons implemented

| Ferrer issue | Fontify behavior |
|---|---|
| Broad thinning altered character | No thinning/smoothing/auto-fit in the compiler; baseline checks source and compiled outlines. Edit a candidate explicitly. |
| Exact mirroring looked insufficient | Enforce only explicitly intended reflections; recheck the exported font. Agent review separately checks optical weight and curves. Intentional asymmetry is declared per glyph. |
| Rounded straight edges / angular bowls | Audit exact intended 0/90-degree features and curve tangents/cusps. Make bounded local corrections, then inspect every actual glyph at enlarged and normal sizes before release. |
| Missing or narrowed counters | Closed-contour, nesting, winding, crossing and zero-area checks; inspect counter proportions manually. |
| Changed wordmark spacing | Explicit advances and GPOS pair kerning; HarfBuzz positions and feature-off comparison from the built font. |
| Assumed full font coverage | Required coverage is explicit; extra/missing mappings are reported, unsupported preview text is flagged. |
| Root scripts/docs lagged release | One project version, versioned artifacts, compiled names, hash manifest, verified current pointer and same-version overwrite refusal. |

This is practical evidence for guardrails, not proof that Ferrer was flawless or
that Fontify can automatically create a visually coherent family. The example
and tests do not depend on the private Ferrer workspace being available.

The read-only local axis and refinement audits also documented that broad
whole-contour smoothing regressed b/h/p/y and other letters. Later fixes used
targeted tangent-constrained patches while preserving stems, shoulders, tails
and unaffected contours. Small one-unit trace stairs could inflate angle counts;
numeric severity needed to be checked against the actual shape. Fontify's
[preflight loop](../references/preflight.md) retains that distinction and requires
agent correction/review before the user's first font, rather than handing defects
to the user as a review task. No Ferrer repair code or artwork was reused.
