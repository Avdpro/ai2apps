# Session-Adaptive L1 Roadmap

Status: **experimental implementation / opt-in**  
Decision date: 2026-08-09

## Decision

The first session-owned adaptive L1 implementation is available behind
`OMLX_DEEPSEEK_V4_ADAPTIVE_L1=1`. It remains opt-in while real quality and
long-session performance gates are evaluated.

The current trace experiment remains useful evidence and tooling, but it is
not authorization to mutate production L1 banks. Existing Scope JSON files
remain immutable inputs selected by explicit path.

## Implemented architecture

1. A Session owns its logical Top60 layout, counters, utility, epoch, and bank
   fingerprint. The model owns one physical bank and restores the selected
   Session layout when requests switch.
2. Top20 remains pinned by default and the trailing 40 slots are adaptive. Set
   `OMLX_DEEPSEEK_V4_ADAPTIVE_L1_PINNED=0` for a completely replaceable bank.
   Rebuild cost is charged per changed layer, because the current implementation
   rebuilds the same contiguous Top60 `SwitchGLU` whether one or forty IDs
   change.
3. Decode route frequency and L1-miss events accumulate in device-resident
   `40 x 256` histograms. Counter kernels are submitted with `mx.async_eval`;
   the host reads about 41 KiB once at a policy checkpoint rather than reading
   telemetry every token. This adds no telemetry-specific host wait. The exact
   fallback path still has its pre-existing per-layer miss decision sync and is
   a separate optimization target.
4. Physical commits run on the model MLX executor between scheduler steps.
   New switches and lookup tables are prepared before the live mapping is
   published.
5. Exact mode keeps KV reusable across physical layouts. Lossy mode includes
   the adaptive fingerprint in its KV namespace; a mid-Decode commit marks the
   mixed-epoch response as non-storeable.

## Triggers

- Manual: `POST /v1/ai2apps/l1/optimize` queues a forced review at the next
  safe Decode boundary. The WebUI exposes the same action while streaming.
- Early correction: reviews once after the first 128 generated tokens. It may
  commit without a prior TPS baseline only when at least 55% of routed expert
  selections miss L1 and the remaining-token payback justifies the
  switch. This is a gross-misclassification path, not ordinary tuning.
- Periodic: every 256 generated tokens, configurable by environment. A commit
  requires poor TPS/cache behavior and an estimated remaining-token I/O saving
  at least 1.5 times its measured or estimated switch cost.
- Post-commit hysteresis: skip the next automatic checkpoint, then require
  1.35 times the normal miss threshold and 1.5 times the normal payback at the
  following checkpoint.
- Turn end: the final token is delivered first. Maintenance runs asynchronously
  under the same serialized bank lock and commits only when TPS, L1-miss rate,
  and projected next-turn payback justify a large update.

## Per-Session control

The OpenAI extension field `ai2apps_l1_mode` accepts `auto` or `off`.
The WebUI exposes `auto / off / trigger`:

- `auto`: device telemetry plus gated automatic reviews;
- `off`: no telemetry, mid-Decode update, or turn-end update;
- `trigger`: queue a large review after the next generated token, then return
  the menu to `auto`.

An Exact-mode isolated telemetry A/B disabled all commits with a 1.0 miss
threshold and alternated modes in the same warm Session. The adjacent 64-token
samples measured 9.246 s with GPU telemetry and 9.226 s with it off, a 0.22%
difference. This is a single short-run sanity check, not yet a broad TPS claim.

The observed two-turn smoke rebuilt four layers in 0.39--0.40 seconds per
turn. The next turn loaded 2.4% fewer Decode experts (1063 to 1037). This is a
functional result, not yet a broad performance claim.

A legacy Head2 300-token A/B on the same HTML-generation prompt measured
26.65 s with adaptive L1 enabled and 26.50 s with it disabled (11.3 tok/s in
both cases). It established only that the old host-boundary observer had little
incremental overhead in that lossy mode; it is not an Exact default-performance
claim. New performance gates must use Exact mode. The physical compute path
remains one contiguous Top60 kernel; retained and adaptive slots describe
replacement policy, not separately dispatched MoE kernels.

An intentionally aggressive follow-up demonstrated why early correction needs
a separate gross-miss gate. At 32 tokens the unconstrained policy replaced 79
experts across 35 layers in 3.259 s; a same-Session second turn then generated
300 tokens in about 26.0 s before its turn-end maintenance, versus the 26.5 s
static reference. With the 60% early gate enabled, the same prompt reported a
0.252 SSD-fallback layer rate and correctly skipped the early rebuild. The
turn-end 40-layer rebuild still cost 3.895 s in the old synchronous prototype.
The current implementation sends both streaming and non-streaming results first
and performs gated maintenance asynchronously.

## Current evidence

The real-route replay used two 128-token English and Chinese Python dialogue
traces. With L1 Top60 + Hot8, a policy that reviews every 16 tokens, pins the
first 40 Scope experts, requires 8 observations, margin 3, ratio 1.5, and a
32-token per-layer cooldown produced:

| Metric | Static | Dynamic |
|---|---:|---:|
| SSD experts per Decode token | 35.625 | 34.965 |
| L1 route hit rate | 74.40% | 75.70% |
| Replacements per 128-token response | 0 | 97.5 |

The full grid and source traces are under
`artifacts/dynamic-l1-2026-08-09/`. These are offline simulation artifacts;
they do not change default inference behavior.

## Intended Session architecture

Each Session owns logical state:

- conversation tokens and compressed KV-cache;
- selected Scope/profile identity and version;
- dynamic L1 and L2 expert IDs;
- frequency counters, recency, decay state, and policy epoch.

The model owns shared physical state:

- immutable model weights and the fixed Scope bank;
- one active dynamic L1 bank and Hot L2 bank;
- optionally one standby bank for the most recently active Session;
- the canonical expert-major SSD store.

Session switches restore logical state into the shared physical bank. They do
not duplicate every expert weight for every Session.

At the current 12.75 MiB expert-record size across 40 score layers, a private
Dynamic40 bank would cost about 19.92 GiB per Session and a private Hot8 about
3.98 GiB. Nearly 24 GiB per Session is not a viable multi-user design even
when KV-cache itself is compact.

## KV-cache residency

Start with in-memory Sessions. DeepSeek V4's current cache path already uses a
128-token `RotatingKVCache` plus ratio-compressed `PoolingCache` state instead
of retaining an expanded conventional K/V history at every layer. This makes
multiple moderate-length Session KV states plausible in 128 GiB.

Do not assume an unlimited Session count from the model structure alone.
Before setting admission limits, measure actual resident cache bytes at 10K,
100K, and 1M context, including pool buffers, index pools, allocator slack,
and prefix-cache duplication.

SSD Session swap is an optional later tier for extreme context or many idle
Sessions. If added, KV must be paged and incrementally written; expert weights
remain canonical in the shared expert store, while a Session persists only
expert IDs and policy metadata.

## Turn-boundary promotion protocol

1. During Decode, collect route frequencies without changing physical slots.
2. When generation ends, compute a bounded set of promotions for that Session.
3. While the user reads or types, prepare replacement slots from Hot L2 or the
   canonical expert store.
4. Keep the old expert-to-slot mapping valid until all Metal work completes.
5. Before the next Prefill, atomically publish the new mapping and policy epoch.
6. If preparation is incomplete when the next request arrives, retain the old
   mapping rather than delaying or corrupting inference.

The implementation keeps a fixed Top20 by default and can replace the other 40
slots in one layer when a gross early miss or a manual trigger justifies it.
Ordinary tuning still uses observation thresholds, payback, hysteresis, and
decay. A complete policy reset remains useful when the topic changes.

## Remaining promotion gates

Do not enable adaptive L1 by default until all of the following are available:

- actual KV memory measurements and a Session admission/eviction policy;
- bounded Session-state eviction and cancellation;
- a split-bank or persistent-slot prototype that reduces the current
  per-changed-layer Top60 rebuild cost;
- identical output versus the exact fallback path;
- an A/B benchmark showing positive end-to-end TPS or TTFT benefit after
  telemetry, copying, mapping, and Metal contention are included.

Until those gates are met, keep `OMLX_DEEPSEEK_V4_ADAPTIVE_L1` disabled in
general deployments.
