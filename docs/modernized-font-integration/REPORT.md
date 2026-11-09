# Modernized-font integration · local review handoff

All ten selected final TTF/WOFF2 pairs are integrated with unchanged bytes. Each sample has a title, description, story, historical inspiration, exact coverage CSV, final-TTF preview, live WOFF2 specimen, CSS, package/source hashes, production notes and an integration preview receipt. No font outline or metadata bytes were edited.

## Repository isolation and base

- Repository: `/home/ferrerluis/repos/fontify`, on `pi-main`.
- Integration branch: `integration/modernized-font-samples-20261109`.
- Worktree: `/home/ferrerluis/Documents/Codex/2026-11-09/task-2/fontify-integration`.
- Exact integration base: `a09832297ebc887bb64d61a687ec177f7fd59010`, fetched current `origin/main`. It includes merged PR #4 and its generation-routing changes. No unrelated unmerged work was included.
- Local commit preparation is complete with the authorized author `ferrerluis <ferrerluis97@gmail.com>`. Identity is set only in the integration worktree’s `config.worktree`; no global or shared author identity is set. The common repository enables `extensions.worktreeConfig=true` so that worktree-local identity can be used. The resulting commit is identified by Git and the handoff, without recording a self-referential commit hash here.
- Production/build provenance pin remains `249bf421e4be58bac8b42024fb42af264bd39838`. The shared `main` checkout remains at that commit, clean. Only the isolated integration branch was fast-forwarded to the newer merged main before additions.
- Shamber was absent from the pinned tree, other local refs/worktree and freshly fetched current main. Existing Grotesk/Mellow example conventions guided the layout; no missing Shamber assets were invented.

## Deliverables

Open [the catalog](../../examples/modernized/index.html) or [the sample overview](../../examples/modernized/README.md). The exact [changed-file list](changed-files.txt) records every addition and the root README edit.

The families are Reedmere 0.025, Presswake 1.011 (package v5), Bunvale 0.016, Lapisent 1.003, Liltvale 0.048, Tessaplay 0.024, Riftstave 0.018, Semiloft 0.019, Marqevra 0.021 (report-r1) and Charterquill 0.216. Bunvale v0.017 and all older intermediate font binaries are excluded.

Every family retains the agreed 354-codepoint union. Bunvale preserves its four extra punctuation scalars (358 mappings); Semiloft preserves U+0237 (355). The display minima remain 32px for Bunvale, Lapisent, Liltvale and Semiloft, and 48px for the other six.

Full editable projects and extensive evidence archives remain separate in the exact named local production packages. The repository carries compact artifact-use samples and retained package manifests. No combined ZIP was needed.

## Validation results

- **Input integrity:** all 7,036 listed package-manifest entries match size/hash where declared, with no mismatches. All supplied ZIPs pass CRC checks. Both Charterquill archives match the supplied archive hashes, and their font bytes agree. [Package results](package-integrity.json).
- **Final artifacts:** all 20 integrated font files match the selected package hashes. Every TTF/WOFF2 pair has identical coverage, glyph order, all outline records and metrics, and exact naming/layout tables. All mapped scalars shape without `.notdef`; 173 canonical equivalents per format/family pass. Fourteen real zero-advance classified/attached marks, specified i/j mixed mark orders, below-only dot retention, blank SPACE/NBSP and native soft-hyphen hiding pass. [Binary results](binary-validation.json).
- **Release integrity:** verified producer releases for Reedmere 0.025, Riftstave 0.018, Semiloft 0.019 and Charterquill 0.216. Verified historical compiler-valid bases for Presswake 1.008 and Lapisent 1.002 separately from their final artifact assemblies. [Scoped release results](producer-release-integrity.json). No unrun full-assembly stock CLI release is claimed.
- **Preview integration:** installed Chrome 156.0.8078.47 loads the actual supplied custom WOFF2 in all ten specimens, with no fallback in sample rows. Complete inventory cell counts and 1500px/390px layout checks pass. Fresh TTF previews and minimum-size browser sample rows were inspected; letters, figures, accents and focused contexts remain visible without clipping. [Browser results](browser-validation.json). This is a bounded integration inspection, not a replacement every-glyph optical certification.
- **Repository suite:** 174 existing tests passed initially; the sole browser test failed because the sandbox blocked Chrome's local socket initialization. That exact test passed outside the socket-restricted sandbox (1 passed in 4.32s). All 175 existing cases therefore pass across the initial run and targeted rerun. Ruff passes for the new verifier, and `git diff --check` passes. [Environment/test details](environment-and-tests.json). Raw logs remain under the worktree's ignored `test-runs/` directory. Before local commit, the exact 152-file staged set, all 151 indexed deliverable hashes, the saved suite/rerun results, fresh all-ten binary validation, Ruff and staged whitespace checks were reverified.

Reproduce the portable artifact check with existing dependencies:

```sh
python scripts/verify_modernized_samples.py --output test-runs/modernized/binary-validation.json
```

## Current Charterquill 0.216 recheck

The selected replacement-A raster hash matches the package, original selected source and raw trace input. All 52 selected SVGs are byte-identical to the original trace; placements/advances match the preserved 0.209 source reference. Direct pinned Fontify outline compilation reproduces all 354 mapped records plus three unencoded helpers against the actual current TTF. The comparison reads earlier work only as a preservation baseline; no old font is integrated. [Source results](charterquill-source-validation.json).

Ordinary į has its source-derived detached dot; its 21-point contour topology, flags and bounds match selected i's dot, with at most one font unit of composite/export rounding. Exact dot-contour identity is not claimed. The contextual dotless-ogonek helper excludes that dot. Ordinary selected i/j remain exact.

Fresh native TTF and decoded-WOFF2 renderings at 48/72/96ppem agree. Twenty-one language groups render identically in NFC/NFD; mixed j+comma-below+acute, i+comma-below+double-acute and reversed inputs agree. Plain į/NFD and above-ogonek equivalent contexts agree. Real Chrome TTF/WOFF2 pixel comparisons pass at all three sizes. Actual SPACE wrap, NBSP nonbreak, hidden/zero-advance SHY and own-font visible discretionary hyphen checks pass without fallback. Six fresh fixed-size sheets were inspected. [Rendering results](charterquill-rendering-validation.json), [local proof assets](../../examples/modernized/charterquill/review-evidence/).

The known Chrome unbroken-word kerning difference is reproduced: at 48px `soft\u00adhyphen` measures 234.9125366px versus 231.4565430px after removing SHY. Forced-reference pixel identity remains unclaimed. These findings validate the current final bytes within the stated scope; they do not certify other engines or arbitrary mark stacks.

Local source/rendering recheck scripts are retained beside the worktree as `check_charterquill_source.py` and `check_charterquill_rendering.py`; they consume the exact inventoried packages without changing original sources. Full per-check reports and hash-bound proof assets are included here.

## Remaining decisions and restrictions

Liltvale's completed independent review cleared its original acceptance hold. Nine current final packages have coordinator-reported independent clearance. Charterquill current-version local checks above supplement the earlier remotely reviewed build.

Final human aesthetic approval and source/distribution terms remain with the owner. No new MIT grant is assigned to the new font assets; unrelated repository code licensing is unchanged. Family-specific limitations remain visible, including high-contrast Liltvale use, Tessaplay's 13/78-unit overflow stress cases, Bunvale's convention-unreviewed extra-above-accent į context, quieter companion glyphs and positional discretionary-hyphen differences.

The separate Charterquill upload hold remains unchanged. No font or font-derived asset was uploaded, no alternate transfer route was attempted, and no combined payload was created for external transfer. There was no generation, paid call, installation, credential creation, public push, PR, integration merge into production/main, deployment or publication. Public distribution and packaging decisions remain deferred. Shamber's intended source/location remains an unresolved reference discrepancy, not a blocker to these ten verified local additions.
