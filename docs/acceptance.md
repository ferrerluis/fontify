# Product acceptance catalog · v7

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
| TC04.3 | Reviewed local project | `pytest tests/test_quality.py -k approval_proof` | Adding a matching protection baseline keeps TTF/WOFF2 bytes identical and changes the proof's pending label to baseline matches, without claiming optical-quality approval. |
| TC05.1 | Recraft extra, mocked transport | `pytest tests/test_recraft.py -k adapter` | Dry request needs no key; paid call requires explicit opt-in; vector payload, errors and saved SVG provenance work through mocks without secrets in records. |
| TC05.2 | Recraft extra, mocked transport | `pytest tests/test_recraft.py -k discovery` | Initialize and paginated tools/list capture actual schemas without calling tools; auth/block failures are reported, not replaced by assumed schemas. |
| TC06.1 | Built example, browser | Open `build/current.json`'s release `proof.html` | Embedded webfont loads, all glyphs and HarfBuzz samples fit, kerning toggle works, unsupported typed characters are identified. Record screenshot and loaded font evidence. |
| TC06.2 | Local build | `pytest tests/test_review.py -k proof_overhang` | A very wide glyph with negative sidebearing fits both the glyph sheet and shaped-line proof without changing its font outline. |
| TC07.1 | Checked-in image-generated example | `pytest tests/test_imagegen.py -k generated_example` | Frozen AI artwork builds offline as A–Z + space; actual TTF/WOFF2 names, coverage, kerning and review-required status match the example. |
| TC07.2 | Optional trace dependencies | `pytest tests/test_imagegen.py -k generated_trace` | Re-tracing the frozen image reproduces the checked-in SVGs; source hash changes and existing output directories are rejected. |
| TC07.3 | Same | `pytest tests/test_imagegen.py -k generated_fidelity` | Each compiled glyph retains at least 96% mask overlap with its recorded generated crop; comparison HTML uses actual compiled outlines. This is a tracing check, not a visual-quality score. |
| TC08.1 | Local project + explicit quality intent | `pytest tests/test_quality.py -k intent` | Every mapped glyph has a construction/symmetry rationale; absent glyphs or disabled limits are rejected. |
| TC08.2 | Same | `pytest tests/test_quality.py -k axes` | Intended horizontal/vertical edges become exact; declared handwritten lean and genuine diagonals remain intact, and repairs stay within bounds/area/topology budgets. |
| TC08.3 | Same | `pytest tests/test_quality.py -k curves` | Curve kinks/cusps are detected; only named intentional corners are accepted. Mirroring stays exact after font export. |
| TC08.4 | An approved or constrained source | `pytest tests/test_quality.py -k preservation` | Repair refuses approved sources, excessive movement and existing output directories; originals remain unchanged. |
| TC08.5 | Internal draft and review receipt | `pytest tests/test_quality.py -k release_gate` | Drafts do not update current.json. Missing/stale/incomplete per-glyph review blocks release; all checks and evidence must match the compiled font. |
| TC09.1 | Frozen Recraft vector sheet | `pytest tests/test_recraft_example.py -k extraction` | Reproduce all 52 glyph SVGs plus explicit space without network; preserve dots, convert painted white counters into holes, reject changed sources or existing output. |
| TC09.2 | Frozen reviewed Recraft project | `pytest tests/test_recraft_example.py -k offline` | Build and reopen TTF/WOFF2 offline with 53 exact mappings, intact counters/metrics, current review receipts and real HarfBuzz pairs. |
| TC10.1 | Local outlines, no credentials | `pytest tests/test_rubrics.py -k plan` | Style plans cover every mapping, explain defaults and leave ink intent unconfirmed; unknown styles and overwrites fail. |
| TC10.2 | Confirmed style/feature intent | `pytest tests/test_rubrics.py -k routing` | Exact reflection, selected axes and stem probes run only where declared; organic lean and variable weight remain intact; unresolved or contradictory intent blocks release. |
| TC10.3 | Unapproved candidate | `pytest tests/test_rubrics.py -k permission` | A failed check does not authorize an edit; only allowed repairs run, unchanged SVGs remain byte-identical and approved sources stay protected. |
| TC10.4 | Candidate with a repairable defect | `pytest tests/test_rubrics.py -k preflight` | Preflight corrects into a fresh candidate, compiles and rechecks both font formats with real shaping, saves actual-font comparisons and requires visual review without updating a release pointer. |
| TC10.5 | Compiled candidate and review evidence | `pytest tests/test_rubrics.py -k gate` | Missing/unresolved/stale intent or visual receipts prevent presentation; only current complete review permits release. No command creates aesthetic approval. |
| TC10.6 | Each supported style | `pytest tests/test_rubrics.py -k universal` | Every style still rejects invalid contours/mappings/metrics and preserves the mandatory source/export checks; styles cannot opt out of technical validity. |

Catalog v4 adds TC08.1–TC08.5 for the pre-presentation audit/correction/recheck gate:
20 required sub-tests, 19 automated plus one browser observation. TC07.3 applies
to the frozen tracing stage; intentional subsequent repairs have separate bounded
change checks and must pass TC08 before a user-facing release.

Catalog v5 adds TC09.1–TC09.2 for the real Recraft vector example: 22 required
sub-tests, 21 automated plus the browser observation. TC08.2 also checks that a
declared intentional lean is preserved, while TC08.3 distinguishes a smooth
wide hook from a stationary cusp. Live generation is recorded as an authorized
experiment, never re-run by automated tests. New descender review sheets must
fit complete g/j/p/q/y shapes at a shared scale and preserve all glyphs.

Catalog v6 adds TC04.3 for the approval handoff: 23 required sub-tests,
22 automated plus the browser observation. Mellow's protected baseline follows
the user's design approval on 2026-11-03; a matching baseline proves preservation,
not independent style quality.

Catalog v7 adds six style-rubric sub-tests: 29 required, 28 automated plus the
browser observation. Existing approved example inputs and artifacts are retained;
schema-1 profiles remain reproducible while new skill work uses schema 2.

These checks do not certify visual quality. The image-generated example is an
unapproved candidate; its creation, normalization and tracing are explicit. A
separate user-authorized Recraft MCP call was verified and recorded; tests use
its frozen SVG, never the live service. No paid request is part of this suite.
