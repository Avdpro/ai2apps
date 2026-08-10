# AI2Apps Fusion Engine

Status: design specification, not implemented
Date: 2026-08-10
Target branch: `experiment/moe-cache`

## 1. Purpose

Fusion Engine exposes several cooperating inference backends as one model. A
local generator produces the answer and remains useful when every optional
backend is unavailable. A reviewer is invoked adaptively, and an optional
third-stage resolver handles only answers that cannot be repaired reliably by
the first two stages.

The API, WebUI, session, and model registry expose one Fusion model ID. The
model card must still disclose that the model is composite; Fusion must not be
presented as a single trained checkpoint.

The design is model-independent. Qwen3.6 plus DeepSeek V4 Flesh is the first
local profile, not a dependency of the orchestration layer.

## 2. Invariants

- The generator always runs locally.
- Draft generation remains available offline.
- A two-stage profile may use either a local or remote reviewer.
- A three-stage profile uses a local generator and local reviewer; its resolver
  is optional and may be remote.
- The resolver is disabled by default and is called at most once per turn.
- Reviewer and resolver output should be proportional to the required change,
  not to the length of the draft.
- Only the canonical final answer becomes conversation history and committed
  generator KV state.
- There are no unbounded review, repair, or escalation loops.
- Remote disclosure, credentials, cost limits, and failure behavior are
  explicit configuration, never hidden defaults.

## 3. Roles and supported topologies

The names describe responsibilities rather than parameter count:

- **Generator**: a fast local model that streams the provisional answer and
  exposes generation confidence statistics.
- **Reviewer**: a higher-quality model that returns a short structured
  decision, patch, or revision instruction.
- **Resolver**: an optional authority used only for escalation. It returns a
  patch, semantic blueprint, or exact fragments instead of rewriting long
  answers by default.

Supported topologies are:

```text
Local generator -> local reviewer
Local generator -> remote reviewer
Local generator -> local reviewer -> optional remote resolver
```

The third topology is the preferred high-quality configuration: most work
stays local, and only `ESCALATE` or a configured hard failure leaves the
device. To avoid confusion with MoE cache L0/L1/L2, implementation and UI must
use the role names rather than numeric tiers.

## 4. External model surface

A profile registers one normal model ID, for example:

```json
{
  "model": "ai2apps/fusion-quality",
  "messages": [{"role": "user", "content": "..."}],
  "stream": true
}
```

Chat Completions, Responses, WebUI history, and session selection address that
single ID. Provider names, review decisions, and stage timings are optional
observability metadata, not separate user turns.

Changing generator, reviewer, resolver, prompt protocol, or gate calibration
changes the Fusion profile fingerprint. That fingerprint is recorded with
benchmarks and session state.

## 5. Request state machine

```text
begin turn
    |
    v
local generator -> provisional draft + confidence statistics
    |
    v
adaptive gate
    |---------------- SKIP ----------------------|
    |                                             |
    v                                             |
reviewer                                          |
    |--------- PASS ------------------------------|
    |--------- PATCH -> apply + validate ---------|
    |--------- REVISE -> local patch generation --|
    `--------- ESCALATE --------------------------+
                         | resolver enabled       |
                         v                        |
                    resolver patch/blueprint      |
                         |                        |
                    local realization             |
                         |                        |
                         +------------------------+
                                                  v
                                  validate and commit final answer
                                                  |
                                               end turn
```

The gate can skip review, but it cannot silently bypass a profile's configured
high-risk or structural-validation rules. A turn executes no more than one
local revision, one resolver request, and one final local realization.

## 6. Adaptive gate

The gate consumes prompt-side, generation-side, and policy-side evidence.

Prompt-side features include:

- task risk and task type;
- prompt length and explicit constraint count;
- requests for exact numbers, citations, complete code, or fixed schemas;
- generator scope and scope confidence;
- local structural checks available before generation.

Generation-side features include:

- output length and `max_tokens` truncation;
- mean and tail negative log likelihood;
- high-percentile uncertainty rather than only average perplexity;
- low-confidence token ratio and Top-1/Top-2 logit margins;
- uncertainty spikes, repetition, malformed tool calls, and failed code/JSON
  validation.

Statistics should be accumulated on device during generation and transferred
once at the end of the draft. The gate must not add a per-token GPU-to-CPU
synchronization. Confidence thresholds are calibrated separately by generator,
quantization, language, task class, scope, and sampling configuration.

The gate returns:

- `SKIP`: commit without reviewer inference;
- `REVIEW`: run the configured reviewer;
- `FORCE`: review regardless of confidence because policy or validation
  requires it.

Initial calibration must run the reviewer on every evaluation sample while
recording the hypothetical gate decision. Skipping is enabled only after the
false-negative and cost curves are measured.

## 7. Review protocol

The reviewer emits a constrained object with one action:

- `PASS`: the draft is canonical without modification;
- `PATCH`: return deterministic minimal edits;
- `REVISE`: return at most a few exact instructions for the local generator to
  turn into a patch;
- `ESCALATE`: the core answer is unusable, the reviewer is uncertain, or local
  repair failed.

`ESCALATE` may carry a local fallback blueprint so a resolver-disabled profile
does not require a second reviewer call.

```json
{
  "action": "PASS | PATCH | REVISE | ESCALATE",
  "summary": "short reason",
  "risk": "low | medium | high",
  "confidence": 0.0,
  "patches": [],
  "instructions": [],
  "blueprint": {
    "conclusion": "",
    "key_points": [],
    "exact_fragments": [],
    "must_remove": [],
    "recommended_structure": []
  }
}
```

Protocol parse failure is not `PASS`. It follows the configured retry or
failure policy and may be an escalation trigger.

## 8. Minimal patching

Long code and prose must not be regenerated merely to correct a small region.
Every patch identifies the exact draft with `base_sha256` and targets a stable
code-block or paragraph ID.

Preferred code edits use exact anchors:

```json
{
  "base_sha256": "...",
  "target": "code_block_0",
  "operation": "replace",
  "before": "button.addEventListener('click', launch);",
  "after": "button.addEventListener('click', () => { if (!running) launch(); });",
  "expected_occurrences": 1
}
```

Supported operations are `replace`, `insert_before`, `insert_after`, and
`delete`. Unified diffs may also be accepted when their context applies
cleanly. The server, not the client, is authoritative for applying patches and
constructing the canonical answer.

A patch is rejected when its base hash differs, an anchor does not match the
expected number of times, validation fails, or its changed region exceeds the
profile limit. The initial suggested limit is 30 percent of the draft. Large
or interdependent changes become `ESCALATE`, not an oversized patch disguised
as a revision.

## 9. Streaming and draft capability negotiation

Fusion supports three stream modes:

| Mode | Behavior |
|---|---|
| `draft` | Native phase events; the client can commit, patch, or supersede an existing draft. |
| `reasoning` | Draft tokens use the thinking/reasoning channel; canonical content is emitted after review. |
| `final` | The server buffers all provisional work and emits only canonical content. |

A native client declares support with a request extension or header:

```json
{"ai2apps_stream_mode": "draft"}
```

```http
X-AI2Apps-Draft-Protocol: 1
```

Native events include a `draft_id` and the phases `draft_begin`, `draft_end`,
`review_begin`, `draft_commit`, `draft_supersede`, `patch`, `final_begin`, and
`final_end`. On `PASS`, the client promotes the existing draft without a second
text transfer. On repair, it applies the server-confirmed patch or replaces the
draft with the final stream.

Compatibility clients receive the draft as reasoning (or a profile-enabled
`<think><draft>...</draft></think>` transport). The complete canonical answer
is still emitted in `content`; a passing draft is replayed from memory rather
than inferred again. Clients that cannot safely separate reasoning use
`final` mode.

Non-streaming responses contain only the canonical answer plus optional Fusion
metadata.

## 10. Transactional session and KV semantics

Each assistant turn has provisional and committed state:

```text
Fusion session
|- canonical conversation
|- generator committed KV
|- generator provisional KV / rollback boundary
|- reviewer state and cache namespace
|- resolver request metadata
`- stage metrics and profile fingerprint
```

On `SKIP` or `PASS`, provisional generator KV becomes committed. If any text is
patched, revised, or replaced, the engine rolls back to the assistant-turn
boundary, prefills the canonical final answer, and commits that KV. It must not
leave rejected draft text in the next turn's context.

Reviewer and resolver do not own canonical conversation KV. A local reviewer
may retain an internal review session and its own scope/L0/L1 state; a remote
reviewer or resolver is normally stateless. Cancellation, timeout, disconnect,
or patch failure either commits a configured fallback atomically or restores
the pre-turn state.

## 11. Optional resolver

The resolver is a profile option and defaults to disabled:

```yaml
resolver:
  enabled: false
```

When enabled, it receives only configured escalation classes, for example
`reviewer_escalate`, low reviewer confidence, patch application failure, or a
high-risk structural failure. It is called no more than once per turn and
returns a short patch, blueprint, or exact fragments by default.

When disabled or unavailable, the profile chooses one explicit policy:

- `local_rebuild`: realize the reviewer's fallback blueprint locally;
- `return_draft`: commit the draft with an internal unverified status;
- `error`: do not deliver an answer that failed review;
- `ask_user`: request permission or a different quality mode.

Ordinary and high-risk requests may use different policies. No resolver
credential or network failure may corrupt the local session transaction.

## 12. Configuration examples

Local two-stage profile:

```yaml
fusion:
  model_id: ai2apps/fusion-local
  generator:
    backend: local
    model: qwen3.6-35b-a3b-4bit
  reviewer:
    backend: local
    model: deepseek-v4-flesh-2bit
  gate:
    policy: adaptive
  resolver:
    enabled: false
    unavailable_policy: local_rebuild
```

Local generator with remote reviewer:

```yaml
fusion:
  model_id: ai2apps/fusion-cloud-review
  generator:
    backend: local
    model: local-generator
  reviewer:
    backend: openai-compatible
    model: high-quality-reviewer
    base_url: https://provider.example/v1
    credential_ref: fusion-review-key
```

Optional three-stage profile:

```yaml
fusion:
  model_id: ai2apps/fusion-quality
  generator:
    backend: local
    model: qwen3.6-35b-a3b-4bit
  reviewer:
    backend: local
    model: deepseek-v4-flesh-2bit
  resolver:
    enabled: true
    backend: openai-compatible
    model: high-quality-resolver
    base_url: https://provider.example/v1
    credential_ref: fusion-resolver-key
    triggers: [reviewer_escalate, reviewer_uncertain, patch_failed]
    max_calls_per_turn: 1
    max_output_tokens: 384
    timeout_seconds: 30
    failure_policy: local_rebuild
```

Credentials are references to Keychain, environment, or AI2Apps credential
storage. They are never embedded in an exportable profile.

## 13. Privacy, cost, and failure behavior

Any remote reviewer or resolver may receive the user prompt, relevant
conversation context, draft, and local diagnosis. WebUI must disclose the
provider, data classes, triggers, token limit, and fallback before enabling
remote inference. The default is local-only.

Profiles may expose `Fast`, `Balanced`, `Quality`, `Always Review`, and `Local
Only` policies. The adaptive decision balances estimated error probability and
severity against latency, token cost, and remote-disclosure policy. Cost never
overrides a configured mandatory high-risk review.

Remote timeouts, rate limits, invalid payloads, and cancellation follow the
same atomic fallback rules as local failures. Production telemetry must not
store prompt, draft, patch, or blueprint text unless explicitly enabled.

## 14. Implementation boundaries

The orchestration layer depends on role interfaces, not model classes:

```python
class GeneratorBackend:
    def generate_draft(...): ...
    def rollback_turn(...): ...
    def prefill_final(...): ...
    def commit_turn(...): ...

class ReviewerBackend:
    def review(...): ...

class ResolverBackend:
    def resolve(...): ...
```

The first implementation should be an in-process orchestrator with injectable
fake backends. It must not require HTTP between AI2Apps and its local engines.
Remote providers are adapters around the same structured protocol.

## 15. Observability

Per turn, record at least:

- profile fingerprint and backend identities;
- gate features, score, and `SKIP/REVIEW/FORCE` result;
- review action and confidence;
- draft, reviewer, resolver, patch, and final token counts;
- stage TTFT, Prefill TPS, Decode TPS, wall time, and queue time;
- patch changed ratio, application result, and validation result;
- local model scope, L1 actions, SSD traffic, active memory, and peak memory;
- remote request count, latency, timeout/rate-limit status, and estimated cost;
- final path such as `skip`, `pass`, `patch`, `revise`, `escalated`, or
  `fallback`.

Standard usage fields remain compatible with the external API. Fusion-specific
compute and provisional-token accounting lives in optional metadata.

## 16. Validation and release gates

Before enabling adaptive skipping, compare generator-only, reviewer-only,
review-all Fusion, and adaptive Fusion on the same fixed corpus. Include
correct drafts, local errors, fundamentally wrong answers, high-confidence
wrong answers, long code, long prose, structured output, multilingual prompts,
and remote failure injection.

The initial implementation is acceptable only when:

1. `PASS` preserves draft text and KV exactly.
2. Patched/replaced turns never leak provisional text into later conversation
   KV.
3. Patch application is deterministic and hash/anchor protected.
4. Native draft, reasoning fallback, and final-only streams produce the same
   canonical answer.
5. Resolver-disabled operation is complete and fully offline.
6. Resolver enablement requires explicit configuration and disclosure.
7. Timeout, cancellation, malformed protocol, and patch failure have bounded,
   tested outcomes.
8. Quality, false-negative rate, latency, memory, network calls, and cost are
   reported rather than inferred.

The concrete Qwen3.6 plus DeepSeek V4 Flesh profile and its earlier review
budget discussion remain in
[`qwen-dsf-review-cascade.md`](qwen-dsf-review-cascade.md).

## 17. First implementation status (2026-08-10)

The first in-process implementation now provides:

- typed generator, reviewer, and optional resolver role interfaces;
- adaptive/off/always gating with bounded reviewer and resolver calls;
- deterministic, hash- and anchor-protected structured patches;
- `PASS`, `PATCH`, `REVISE`, and `ESCALATE` execution paths;
- draft-native, reasoning-compatible, and final-only stream modes;
- OpenAI chat streaming transport through optional `delta.ai2apps` events;
- serializable profiles, local oMLX adapters, an OpenAI-compatible remote
  adapter, and an in-process `build_omlx_fusion_engine(...)` factory;
- atomic protocol-level commit/abort semantics and failure-injection tests.

This version deliberately has the following boundaries:

- Fusion profiles are built programmatically and are not yet auto-discovered
  or registered by `EnginePool` or the WebUI.
- The oMLX generator adapter marks the draft `skip_cache_store=True`. The
  protocol has commit hooks, but the current adapter does not yet promote or
  prefill the canonical answer into a reusable KV transaction. A subsequent
  request safely rebuilds canonical context from client-provided history.
- Existing generation output does not yet expose batched NLL/logit-margin
  statistics, so the live adapter initially gates on prompt risk, output
  length, finish reason, and any signals supplied by a custom backend.
- Tool calling is rejected explicitly in Fusion v1. Chat text streaming is the
  supported API path; Anthropic and Responses-native phase transports remain
  follow-up work.
- Token accounting reports generator draft tokens. Reviewer/resolver compute,
  detailed timings, cache metrics, and remote cost still require telemetry
  plumbing before quality/performance claims can be made.

These constraints keep the first version correct and testable without
claiming zero-copy KV promotion or automatic deployment integration that is
not implemented yet.
