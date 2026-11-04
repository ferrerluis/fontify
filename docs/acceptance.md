# Product acceptance catalog · v2

Each test runs without credentials or network unless explicitly marked live. Run
`python scripts/run_acceptance.py`; results and JUnit evidence go to `test-runs/`.
The runner records component versions, source digest, timestamp and command.

| ID | Prerequisites | Repeatable action | Expected observable result / evidence |
|---|---|---|---|
| TC01.1 | Installed local dependencies | `pytest tests/test_pipeline.py -k offline` | Build checked-in A–Z + space SVG project; reopen TTF/WOFF2, correct cmap, blank space, metrics, names, version and matching outlines. |
| TC01.2 | Same | `pytest tests/test_pipeline.py -k reproducible` | Independent builds produce byte-identical fonts, manifests and proofs; different content cannot replace a version. |
| TC01.3 | Same | `pytest tests/test_validation.py -k curved_placement` | A curve whose control bounds differ from its ink bounds keeps its placement in exported fonts. |
| TC02.1 | Same | `pytest tests/test_validation.py -k coverage` | Missing coverage, duplicate Unicode/name, invalid scalars and unknown pairs fail with a useful error. |
| TC02.2 | Same | `pytest tests/test_validation.py -k vector` | Unsafe, open, intersecting, touching, wrongly wound, degenerate, out-of-metrics and unsupported vectors fail; holes, quadratics, cubics and explicit transforms survive. |
| TC03.1 | Same | `pytest tests/test_pipeline.py -k shaping` | HarfBuzz applies each declared pair by exactly its adjustment; supported samples never use .notdef; unsupported input is reported. |
| TC04.1 | Same | `pytest tests/test_review.py -k approval` | Source, outline, mapping and advance changes to approved glyphs stop builds; new glyphs remain marked unreviewed. |
| TC04.2 | Two local releases | `pytest tests/test_review.py -k comparison` | Changed-glyph overlay/JSON identify the edit at the same origin/scale; corrupted release artifacts fail verification. |
| TC05.1 | Recraft extra, mocked transport | `pytest tests/test_recraft.py -k adapter` | Dry request needs no key; paid call requires explicit opt-in; vector payload, errors and saved SVG provenance work through mocks without secrets in records. |
| TC05.2 | Recraft extra, mocked transport | `pytest tests/test_recraft.py -k discovery` | Initialize and paginated tools/list capture actual schemas without calling tools; auth/block failures are reported, not replaced by assumed schemas. |
| TC06.1 | Built example, browser | Open `build/current.json`'s release `proof.html` | Embedded webfont loads, all glyphs and HarfBuzz samples fit, kerning toggle works, unsupported typed characters are identified. Record screenshot and loaded font evidence. |
| TC06.2 | Local build | `pytest tests/test_review.py -k proof_overhang` | A very wide glyph with negative sidebearing fits both the glyph sheet and shaped-line proof without changing its font outline. |

Catalog v2 adds TC01.3 and TC06.2 for placement and proof-bounds regressions:
12 required sub-tests, 11 automated plus one browser observation; 47 pytest checks.

These checks do not certify visual quality. The example is a deliberately simple
geometric display alphabet, not an approved professional typeface. Live Recraft
schema and generation are separate external checks; unavailable access stays
unverified, and no paid request is part of this suite.
