# Choose a generation method from the brief

This is the agent's creative workflow, not an automatic style classifier. The
compiler and provider adapter do not inspect references or judge prompt
compliance. Existing Recraft request defaults select a model only after the agent
has chosen to try vector generation.

## 1. Inspect before choosing

Read the user's actual request and inspect the reference images. Identify the
features that make the design recognizable: proportions, stroke contrast,
terminals, curves, texture, irregularity, ornament, case relationship and overall
tone. Separate essential qualities from optional details. Consider evidence from
earlier attempts at the same brief instead of resetting the experiment in a new
session.

Decide whether native-vector generation is appropriate to try at all. Clean,
bounded silhouettes and a reference whose key qualities can plausibly survive
that model's shape vocabulary may justify one trial. Brush texture, distressed
edges, irregular ink or intricate expressive detail can favor image generation
directly. These are clues, not bans on whole font categories: inspect the actual
reference and request. Do not choose vector merely because Recraft is connected,
because the final font uses outlines, or because the model is called Pro.

Record the chosen route and concrete reference-based reasons in the project's
working notes. Preserve supplied approved artwork; it does not require a new
generation experiment. Respect an explicit choice of another provider. A
"native vector only" or "no raster" restriction is a boundary, not permission
to silently substitute a different source method.

## 2. One vector pilot before a batch

If trying vector generation, run one pilot iteration, with one output (`n=1`),
even when several design options were requested. This is one initial generation
call for the brief, not one unreviewed trial per requested option, glyph, prompt
variation, model or session. Check saved attempts first; do not reset a failed
pilot by renaming the task. A single sheet may contain the requested repertoire,
but do not batch A/B/C alternatives
inside the trial as a way around the one-output limit.

Use a prompt that actually tests the defining reference qualities and requested
coverage. For Recraft, follow [recraft.md](recraft.md), prefer Vector Pro only
after selecting this route, and pass the model and `n=1` explicitly to MCP.
Preserve the exact request, raw output and provider/model provenance. The REST
adapter already fixes `n=1`; this workflow also covers direct MCP calls.

The single trial is not permission to spend. Obtain the required approval for
the exact paid request, reference transmission and any authentication or account
changes. Missing approval, a timeout, rate limit or authentication failure is
not visual evidence of model unsuitability. Check an uncertain request's outcome
before doing anything that could duplicate its charge. Do not retry a vector
request automatically or treat an operational error as a completed visual review.

## 3. Review compliance before further option work

Inspect the actual returned artwork, not just a success response, model name,
file extension or SVG validity. Compare it with the prompt and references at a
useful scale. Record concrete observations for:

- **Style identity:** the defining mood, construction and recognizable features.
- **Letterform behavior:** proportion, stroke contrast, terminals, curves,
  ornament, texture and intentional irregularity where requested.
- **Consistency and coverage:** coherent case relationships and repeated motifs;
  omissions, duplicates, merged letters and obvious wrong characters.
- **Repair scope:** whether defects are isolated, bounded corrections or would
  require redesigning most letters to recover the brief.

A result is **systemically off** when the defining style is missing or replaced
across much of the sheet, the model repeatedly simplifies essential traits into
generic geometry, or recovering the requested character would mean rebuilding
most letterforms. Technical validity and a superficially polished sheet do not
make such a result compliant. Conversely, one uneven curve or a small number of
local defects is not automatically a systemic mismatch. Record which important
features passed, failed or remain uncertain; do not invent a numerical confidence
score as a substitute for looking.

If systemically off, stop the vector route and fall back to image generation.
Preserve the failed trial and comparison notes. Do not run more vector prompts,
switch vector models or hand-code replacement letters to disguise the mismatch.
If genuinely uncertain, inspect the saved result more closely; do not buy another
vector sample as the review step. If the user requires native-vector-only output,
ask before relaxing that restriction rather than silently falling back.

A compliant vector result can remain a design option. After it passes, generate
the remaining requested options through the vector route within the existing
authorization and budget; do not ask again for calls already covered. Review
those outputs too, and stop rather than repeat vector attempts if a systemic
mismatch appears. The single iteration is a pilot gate, not a lifetime cap or a
reason to deliver fewer options. Local corrections belong to Fontify's normal
review workflow. Passing this review is not the user's design selection, not
approval of every glyph, and not font release.

## 4. Image generation and selection

For a direct raster route or an allowed fallback, use the built-in image-generation
tool without inventing an API key requirement. Carry forward the original brief
and references, not the failed vector model's simplifications. Generate fresh
raster artwork; do not rasterize the failed SVG and call that a fallback. Fulfil the
requested design-option count without treating it as permission to retry a
systemically failed vector pilot. Calls already covered by the user's request and
budget do not need repeated approval. Additional spend, reference sharing or
material changes of provider, data destination or scope outside that authorization
still need the applicable approval. Do not spend beyond an existing limit.

Keep already liked or selected concepts intact. Unselected concepts stay
unselected; praise is not an A/B/C choice. When the user is choosing among
concepts, wait for their selection before cleanup, tracing or font construction.
Do not regenerate or replace existing options merely because this routing policy
changed. Later user instructions can explicitly change the failed-route decision
or the selection gate; record that change rather than inferring it from a broad
request for more options.

After selection, preserve raster originals and use
[raster-preparation.md](raster-preparation.md) only for bitmap sources. Native
vector sources stay vector through extraction and construction. A traced SVG or
finished outline font does not turn a raster source into native-vector-generated
artwork. Final-font raster proofs are display QA, not source conversion.

## 5. Provenance and user-facing communication

Always retain the actual source method, provider/model, exact prompt, raw outputs,
trial assessment and any fallback in project provenance. Be accurate in filenames,
artifact descriptions and answers; never label traced raster artwork as native
vector generation. Record whether a generation actually ran rather than implying
that rebuilding old artwork was a new call.

Volunteer the generation method only if the user specifically requested vector
generation. In that case, briefly state the actual outcome, for example: "The
vector trial missed the reference's letterforms, so these options use image
generation. The selected design will be traced into font outlines." If no vector
trial was appropriate, say that directly instead of implying one ran.

Otherwise, routine messages should focus on the options, design findings and
results without a provider or method recap. This is not permission to conceal
facts: answer direct questions truthfully and disclose costs, required approvals,
unmet source restrictions and material blockers when needed. Do not let an
earlier vector request leave the user with a false impression after fallback.

This routing policy does not weaken [spacing](spacing.md),
[style rubrics](style-rubrics.md), [preflight](preflight.md) or
[intended-size proofs](size-proofing.md). Every selected source route still needs
the same construction, visual review and release checks.
