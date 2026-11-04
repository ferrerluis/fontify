# Optional Recraft · research and setup (checked 2026-11-03)

Fontify is fully usable without Recraft. Generated vectors are **source artwork**:
they have no Unicode map, font metrics, kerning or approved letterform status.
Consistency remains an experiment to assess, not a promised capability.

## Remote MCP versus REST

| | Official remote MCP | API adapter |
|---|---|---|
| Endpoint | `https://mcp.recraft.ai/mcp`, Streamable HTTP | `https://external.api.recraft.ai/v1/images/generations`, JSON POST |
| Auth | OAuth 2.0 through an MCP client | Bearer API token on the server |
| Billing | Recraft plan/Studio subscription credits | Separate prepaid API units; response `credits` reports usage |
| Development | Prefer an existing configured client; inspect its actual schema | Mockable `httpx.Client`; no key during tests |
| Reusable application | Agent's interactive connector, schema can differ | Chosen server-side integration with explicit model and paid-call gate |

The [official remote guide](https://www.recraft.ai/docs/mcp-reference/remote-server)
documents OAuth and subscription billing. The [API quickstart](https://www.recraft.ai/docs/api-reference/getting-started)
documents tokens and API units. An existing Studio subscription is not evidence
of API access or API credit balance. No account, token, purchase or paid call was
created as part of development.

## MCP: documented capabilities and live discovery boundary

The [published tools page](https://www.recraft.ai/docs/mcp-reference/tools) lists
`generate_image`, `create_style`, `vectorize_image`, `image_to_image`,
`remove_background`, `replace_background`, `crisp_upscale`, `creative_upscale`,
and `get_user`. It describes prompt/model/style/size inputs, reference images,
and account information. This is a **documentation inventory, not a discovered schema**.

No configured Recraft tools were exposed in this session. An actual `initialize`
POST on 2026-11-03 returned Cloudflare 403/error 1010 before MCP authentication.
No `tools/list` response was obtained; live fields, tool names and model enums
remain unverified. [The saved result](../docs/research/recraft-mcp-discovery.json)
contains no credentials. Do not substitute REST fields or illustrative documentation
parameter labels for a real MCP `inputSchema`.

Connect the remote URL in an OAuth-capable MCP client when desired; let that
client manage authorization. Export its `tools/list` result for review. For a
network that can reach the endpoint, the read-only helper supports pagination:

```sh
fontify recraft-discover --output build/recraft-live-schema.json
```

It initializes, sends `notifications/initialized`, and calls `tools/list`; it never
calls `tools/call`. It accepts an existing authorized access token through
`RECRAFT_MCP_ACCESS_TOKEN` if your client makes one available; it does not retrieve,
create or refresh tokens, launch OAuth, or bypass blocks. Do not treat API tokens
as interchangeable with OAuth tokens. Discovery fails clearly on 401/403.
Generated schemas store tool names and schemas, not auth headers or session IDs.

## REST adapter's deliberate subset

Current [V4.1 documentation](https://www.recraft.ai/docs/api-reference/models/recraft-v4-1)
names `recraftv4_1_vector`, `recraftv4_1_pro_vector`,
`recraftv4_1_utility_vector` and `recraftv4_1_utility_pro_vector`; all produce SVG.
The adapter explicitly supports those four, defaults to the first, and fixes
`n=1`. V4.1's curated `style`, negative prompt and text-layout parameters are
unsupported, so they are not sent. Other documented model generations require
their own parameter compatibility; they are not assumed to work through this adapter.

Use an existing `style_id` or up to ten HTTPS `style_reference_urls`, never both.
The [styles guide](https://www.recraft.ai/docs/api-reference/styles) says references
create a reusable style and model compatibility matters. These tools can inform
coherence; they do not ensure matching stems, topology or alphabet completeness.
The adapter records the resolved style ID when returned, so it can be reused.

The [API pricing page](https://www.recraft.ai/docs/api-reference/pricing) currently
lists V4.1 vector at $0.08/image and Pro vector at $0.30/image; reference-style
creation adds $0.005/request. $1 buys 1,000 API units. Prices can change; review
the provider's current price before authorizing a specific request. These are
API prices, **not** a conversion of Studio/MCP credits. [Studio credit costs](https://www.recraft.ai/docs/plans-and-billing/credits)
depend on operation/model; check the selected model in Studio.

The [results guide](https://www.recraft.ai/docs/api-reference/image-inputs-and-results)
documents URL, Base64 JSON and multipart responses. The adapter deliberately
requests `b64_json`, saves the SVG locally and refuses unexpected URL responses.
It does not download arbitrary returned URLs. [Provider limits](https://www.recraft.ai/docs/api-reference/appendix)
include temporary image URLs (about 24 hours), 5 requests/second and 100 images/minute;
vector outputs use aspect ratios, not fixed pixel dimensions. Fontify supports a
small ratio subset. SVG has no meaningful fixed "4K" resolution for font quality.

## Plan first; generation only with approval

```sh
pip install -e '.[recraft]'
# No key or network: creates a reviewable request.
fontify recraft-plan examples/recraft/concept.txt --model recraftv4_1_vector > build/recraft-plan.json
```

Review the exact prompt, model, references, count and current cost before
authorizing a paid request. Only then supply an **existing** API token through
`RECRAFT_API_TOKEN` on the server and run:

```sh
fontify recraft-generate build/recraft-plan.json --out build/candidates/concept-01 --allow-paid
```

An agent must obtain the user's authorization for that spend; the flag alone is
not authorization. Do not create credentials or buy credits to make an example
run. On macOS, if an authorized command needs a stored secret, retrieve it once
with `op` using the normal desktop approval, use a short-lived shell variable for
that command, then unset it. Never echo it, put it in a plan or commit it. This
library exposes no browser/client credential path.

`RecraftProvider(client=...)` accepts an injected client, enabling completely
offline `httpx.MockTransport` tests. Network failures and non-2xx responses stop
without retry: a timeout may already have charged credits. Error messages omit
provider bodies and signed URLs. The record includes model, request/artwork
hashes, reported credits and review status; no token, reference URL or prompt text.
The local request plan still contains the prompt/references; keep private plans
out of a public repo. `save_candidate` always creates a fresh review directory.

## One-shot experiment and correction workflow

1. Start with the checked-in concept prompt: one sheet of diagnostic letters
   A H O C G D R S V W, one shared style, black silhouettes, no labels/background.
   One image can share context across letters, but may omit, duplicate or merge
   letters. Status: **planned, not run; paid generation not authorized**.
2. Preserve the raw SVG and provenance. Identify every letter manually; do not
   infer Unicode or accept the sheet as a finished font. For comparison, optionally
   plan a later sheet with all A–Z or isolated glyphs using the same style ID.
   A fixed random seed is an experiment control, not a consistency guarantee.
3. Use a vector editor to split glyphs, remove backgrounds, expand strokes and
   convert shapes/arcs. Review stems, straight edges, bowl/counter curves,
   optical balance and intended asymmetry. Correct individual letters.
4. Put candidates in a new local project/version, explicitly set mappings and
   metrics, build offline, and review compiled-font proofs and shaped words.
5. Compare against the approved release. Keep approved files intact; update only
   intended glyphs, then capture a new baseline after human review. Recraft never
   rewrites existing glyphs through the compiler.

Real API/auth/charge/output behavior still needs an authorized live experiment.
Mocked integration tests establish request/handling behavior, not font quality
or compatibility with an undiscovered live MCP schema.
