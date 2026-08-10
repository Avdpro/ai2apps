# DeepSeek V4 Flesh engine

DeepSeek V4 Flesh is the scope-cached DeepSeek V4 backend served by the normal
oMLX/AI2Apps model surface. It is not a separate HTTP server. Model discovery,
OpenAI and Anthropic APIs, streaming, tool calling, structured output, model
LRU management, and the other LLM/VLM/audio engines remain owned by the common
server.

## Request path

```text
OpenAI/Anthropic request
        |
        v
render complete conversation with the model chat template
        |
        v
16-layer target-backbone + shared-expert Top6 probe
        |
        v
select a scope from the configured profile
        |
        v
activate that scope's physical Top60 bank when it changed
        |
        v
normal BatchedEngine Prefill and Decode
        |
        v
content-addressed, scope-namespaced prefix/KV cache
```

The probe reads every scope name and layer bank dynamically from the profile.
It does not contain a hard-coded ten-class classifier. The default depth is 16
total transformer layers and can be changed to 43. It reads prompts up to 1024
tokens in full. For longer conversations it samples 128 leading tokens and the
most recent 896 tokens, preserving both initial instructions and the current
turn. The shared-only Router scores are accumulated over independent 128-token
windows rather than relying on one long shallow hidden-state trajectory.

## Configuration

```bash
export OMLX_DEEPSEEK_V4_SCOPE_PROFILE=/path/to/tiered-top60.json
export OMLX_DEEPSEEK_V4_SCOPE_NAME=general
export OMLX_DEEPSEEK_V4_EXPERT_STORE=/path/to/moe-expert-major
export OMLX_DEEPSEEK_V4_SCOPE_PROBE_DEPTH=16
export OMLX_DEEPSEEK_V4_SCOPE_PROBE_MAX_TOKENS=1024
export OMLX_DEEPSEEK_V4_SCOPE_LOSSY_MODE=exact
export OMLX_DEEPSEEK_V4_ADAPTIVE_L1=1
export OMLX_DEEPSEEK_V4_ADAPTIVE_L1_EARLY_CHECK=128
export OMLX_DEEPSEEK_V4_ADAPTIVE_L1_EARLY_MIN_SSD_RATE=0.55
export OMLX_DEEPSEEK_V4_ADAPTIVE_L1_INTERVAL=256
export OMLX_DEEPSEEK_V4_ADAPTIVE_L1_PINNED=20
export OMLX_DEEPSEEK_V4_ADAPTIVE_L1_MAX_PER_LAYER=40
export OMLX_DEEPSEEK_V4_ADAPTIVE_L1_MAX_LAYERS=40
```

`SCOPE_NAME` is the initial physical bank, not a fixed request classification.
The online selector can switch away from it on the first request. Set
`OMLX_DEEPSEEK_V4_SCOPE_PROBE_DEPTH=43` to run the complete shared-only
backbone.

Start the common server:

```bash
omlx serve \
  --model-dir /path/to/model-parent \
  --paged-ssd-cache-dir /path/to/kv-cache \
  --max-concurrent-requests 1
```

When a discovered model has `model_type=deepseek_v4` (or its MTP variant) and
the three scope paths above are configured, `EnginePool` automatically creates
`DeepseekV4FleshEngine`. Other discovered models keep their normal engines.

The scope-aware discovery estimate subtracts nonresident routed experts. On
the tested checkpoint it reports 53.59 GiB instead of the full checkpoint's
156.09 GiB; the observed process increase was 54.18 GiB.

## OpenAI chat

No custom endpoint is required:

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "deepseek-v4-flesh",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Write an LRU cache in Python."}
    ],
    "stream": true
  }'
```

The inherited server also exposes `/v1/completions`, `/v1/responses`,
`/v1/messages`, and `/v1/models`.

Pass a stable AI2Apps Session ID on multi-turn Chat Completions:

```json
{"ai2apps_session_id":"chat_123"}
```

Queue an immediate L1 review during Decode:

```bash
curl http://127.0.0.1:8000/v1/ai2apps/l1/optimize \
  -H 'Content-Type: application/json' \
  -d '{"model":"deepseek-v4-flesh","session_id":"chat_123"}'
```

## Engine Boost

The Chat UI exposes three session-owned acceleration modes:

| UI mode | Routing policy | Behavior |
|---|---|---|
| Natural | Exact | Full router fidelity; every miss uses the exact expert |
| Turbo | Tail2 | Replace nonresident misses among the two lowest-weight routes |
| Blast | Head2 | Protect the two highest-weight routes and replace lower misses |

Chat Completions accepts `ai2apps_engine_boost` with `natural`, `turbo`, or
`blast`. Natural is the default. A live change can be queued with:

```bash
curl http://127.0.0.1:8000/v1/ai2apps/engine/boost \
  -H 'Content-Type: application/json' \
  -d '{"model":"source","session_id":"chat_123","mode":"turbo"}'
```

During Decode, the new policy is published after the next generated token on
the scheduler's existing safe boundary. It changes Python policy references
only: no expert reload and no GPU-to-CPU synchronization are added. If a mode
or lossy L1 layout changes after Prefill, the completed KV is stored in a
Session-owned namespace. The next turn can reuse that mixed-policy history,
while unrelated Sessions cannot mistake it for globally exact/Tail2/Head2 KV.

The Chat status panel also exposes a momentary **Rush** control for Cache-MoE
models. Holding it queues Blast/Head2 at the next safe Decode boundary;
releasing it restores the Session's previously selected Engine Boost mode.
Pointer cancellation, window blur, page hiding, and generation completion all
release Rush defensively. It is disabled when the base mode is already Blast
and hidden, together with Scope/SSD telemetry, for non-Cache-MoE engines.

The Chat performance panel reports model-normalized SSD pressure over the
latest 10 Decode tokens. It divides actual expert bytes read from SSD by the
model's routed-expert parameter bytes for the same window, accounting for MoE
layer count, per-layer Top-K, and expert size. Up to 16.7% is healthy,
16.7–25% is elevated, and 25% or more is critical. The tooltip retains raw
expert count and MiB. The Scope card appends `*` when the current Session has
committed at least one adaptive-L1 optimization.

## Conversations, sessions, and KV reuse

OpenAI Chat Completions remains stateless at the protocol level: the caller
sends the complete message history on each turn. The Responses endpoint can
use its existing response-chain store. The inference cache itself is
content-addressed, so it does not need an exclusive mutable KV object per
session:

- extending a conversation reuses matching blocks from its prior turns;
- switching between sessions leaves both conversations' blocks available;
- identical system prompts can share KV blocks across sessions;
- the runtime namespace includes the selected scope and lossy policy, so KV
  produced by different effective expert banks cannot be mixed.

In the real two-session smoke test, both requests contained the same 730-token
prompt. The second session restored 512 cached tokens. Short prompts below the
DeepSeek-aligned cache block size do not report a hit.

## Real smoke results

- Two-turn conversation: automatic `writing_creative` selection; one bank
  activation; the second turn reused the active bank.
- Cross-session system prompt: 512/730 prompt tokens restored from KV cache.
- Cross-domain switch: `coding` then `math_logic`, with two correct physical
  Top60 activations.
- Warm 16-layer probe: about 52--97 ms in the online smoke runs.
- Cold physical bank activation: about 3.0 seconds per scope switch.
- `/v1/chat/completions`: returned a standard OpenAI response through
  `EnginePool` and `DeepseekV4FleshEngine`.

## Concurrency policy

A physical expert bank is mutable model-wide state. The engine therefore holds
one async lock from scope selection through the end of generation. Concurrent
HTTP clients remain supported, but their Flesh inference requests queue and
enter the model one at a time. This preserves correctness across session/scope
switches and gives a future access-driven L1 policy one unambiguous stream of
promotion and eviction events. Use `--max-concurrent-requests 1` for
predictable server-level queueing.

Same-scope continuous batching is intentionally not a requirement. Future
throughput work should instead focus on reducing the serial critical path:
retain/promote genuinely hot experts in L1, evict cold experts by observed
access, keep reusable scope material in L2, and overlap safe bank I/O with the
current request. Hierarchical scopes and a low-confidence Top-K refinement pass
remain follow-up accuracy work.
