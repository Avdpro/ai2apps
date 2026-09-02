# Qwen3.8 Flash Next Cached-MoE checkpoint — 2026-08-28

## Scope

- Checkpoint: `Vontra/Qwen3.8-Flash-Next-MLX-4bit`
- Revision: `de597762aa61387c89590a46582222a261ce0387`
- Architecture: Qwen4-Exp, 48 MoE layers, 512 routed experts, exact Top-10
- N-gram PLE execution is preserved exactly through SSD mmap; PLE caching and
  Lightning MTP acceleration are intentionally outside this checkpoint.

## Implemented

- Pinned `mlx-vlm` Qwen4-Exp compatibility module and scoped MLX-format
  sanitizer.
- Direct-gamma RMSNorm checkpoint compatibility.
- Fixed-shape Top-N `SwitchGLU` L1 and persistent Hot tier.
- Expert-major Q4 records with gate/up already fused and every record aligned
  to 4 KiB. Decode requires one direct read and no reshape, transpose,
  concatenation, or dequantization.
- Native direct SSD-to-unified-memory Decode and Prefill load.
- Original Top-10 route-order reduction for strict numerical parity.
- Canonical Prefill grouping with direct reuse of L1/Hot records in their
  canonical scratch slots. Prefill retains the session/Scope L1 across chunks
  so repeated experts are not reread or pointlessly reshuffled. Resident-first
  Prefill remains an opt-in A/B because changed QMM batch shapes can alter
  later tokens.
- Scope-selected L1 priming at the first decode token followed by the existing
  dynamic cache policy.
- Request-local Hot invalidation and reusable L1 session state.
- Runtime-selectable Boost routing for Prefill and Decode. Natural remains the
  default exact mode. Turbo protects the five highest-weight Top-10 routes
  and Blast protects the highest three; explicit Top7, Top6, and Top4
  experiment modes are also available. Only eligible low-weight misses are replaced by the
  best currently resident L1/Hot experts on device. Original route weights
  and the fixed Top-10 compute shape are retained.

## Checkpoint-format verification

`scripts/verify_qwen38_next_expert_store.py` compared experts
`0,127,255,511` in every one of the 48 layers directly against their source
safetensors rows:

- checked bytes: 589,824,000
- mismatches: 0
- report: `benchmarks/results/qwen38_next/expert-store-byte-verification.json`

## Formal pinned-runtime baselines

Identical prompt, temperature 0, 256 generated tokens, prefill step 512:

| Runtime | Decode TPS | MLX peak | Token parity |
|---|---:|---:|---|
| Full resident Q4 + PLE mmap | 33.58 | 75.17 GiB | reference |
| Top224 + Hot10 + pinned Scope | 20.01 | 49.45 GiB | exact, 257/257 |

The Cached-MoE result retains 59.6% of full-resident Decode TPS while saving
25.71 GiB of MLX peak memory. It recorded 11,203 all-hit layer calls and 1,085
miss calls out of 12,288 decode-layer calls.

The simple production promotion gate now keeps L1 promotion disabled through
the first 128 decode tokens of every request and enables the configured limit
(default four per layer) from token 129. Every Prefill resets the per-layer
decode counters, so a new turn starts in the low-overhead mode. The gate is
configured with `OMLX_QWEN4_L1_PROMOTION_ENABLE_AFTER` and passes a per-call
limit into the shared tiered executor rather than mutating the global GLM
promotion setting.

A 160-token real-model smoke crossed the threshold, performed 810 lossless L1
promotions after the gate opened, and matched the static-L1 reference for all
160 reported generation tokens. Peak MLX memory remained 49.45 GiB. At the
current 3,072,000-byte expert record size, Top224 occupies 30.76 GiB and Hot10
occupies 1.37 GiB across 48 layers; the remaining approximately 17.32 GiB is
the dense/shared model, PLE, runtime workspaces, prompt/KV state, and other MLX
allocations. Promotions reuse the existing Top224 slots and add no resident
capacity.

Artifacts:

- `benchmarks/results/qwen38_next/full-q4-vendored-pinned-decode256.json`
- `benchmarks/results/qwen38_next/top224-hot10-scope-decode256-vendored-pinned-trained.json`
- `benchmarks/results/qwen38_next/scope-general-top224-decode256-vendored-pinned.json`

## Prefill status

The accepted optimization preserves the original route order and QMM grouping,
but fills canonical scratch slots from L1/Hot whenever a matching expert is
already resident. The session/Scope L1 is held fixed while all Prefill chunks
run. Both switches default on for Qwen and remain independently reversible via
`OMLX_QWEN4_PREFILL_CANONICAL_REUSE=0` and
`OMLX_QWEN4_PREFILL_RETAIN_L1=0`.

Top160 + Hot10, Natural routing, 3,861 prompt tokens, 32 generated tokens:

| Chunking | Runtime | Prefill TPS | SSD reads | Peak | Parity |
|---|---|---:|---:|---:|---:|
| 2 × 2,048 | canonical baseline | 233.74 | 110.19 GB | 44.08 GiB | reference |
| 2 × 2,048 | canonical reuse + retained L1 | 295.25 | 89.46 GB | 44.08 GiB | 32/32 |
| 4 × 1,024 | canonical baseline | 183.42 | 171.74 GB | 44.08 GiB | reference |
| 4 × 1,024 | canonical reuse + retained L1 | 264.59 | 110.12 GB | 44.08 GiB | 32/32 |

The accepted path improves the normal 2,048-token-chunk case by 26.3% and the
four-chunk stress case by 44.3%, while reducing expert SSD reads by 18.8% and
35.9% respectively. A longer 128-token decode check produced exact 128/128
token parity, improved Prefill from 237.07 to 294.16 TPS, and slightly improved
Decode from 11.75 to 12.17 TPS.

Rejected experiments:

- Canonical reuse without retaining L1 reached 257.34 TPS but preserved only
  31/32 generated tokens.
- Resident-first execution reached 257.73 TPS but preserved only 27/32 tokens.
- A single 4,096-token chunk reported 431.53 TPS but generated immediate EOS;
  it is invalid rather than a speedup.
- Two 256-slot scratch arenas reached 290.11 TPS, below the accepted single
  arena, used 0.18 GiB more peak memory, and diverged after token 27.

Artifacts:

- `benchmarks/results/qwen38_next/prefill4k-top160-canonical-baseline-v2.json`
- `benchmarks/results/qwen38_next/prefill4k-top160-canonical-reuse-retain-v1.json`
- `benchmarks/results/qwen38_next/prefill4k-top160-canonical-baseline-128-v1.json`
- `benchmarks/results/qwen38_next/prefill4k-top160-canonical-reuse-retain-128-v1.json`
- `benchmarks/results/qwen38_next/prefill4k-top160-step1024-baseline-v1.json`
- `benchmarks/results/qwen38_next/prefill4k-top160-step1024-reuse-retain-v1.json`
- `benchmarks/results/qwen38_next/prefill4k-top160-resident-first-v2.json`
- `benchmarks/results/qwen38_next/prefill4k-top160-single-chunk-v2.json`
- `benchmarks/results/qwen38_next/prefill4k-top160-dual256-reuse-retain-v1.json`

### Experimental N-gram PLE ablation

`OMLX_QWEN4_PLE_MODE=disabled` is available only for explicit A/B testing.
The default remains `auto`, which resolves to SSD mmap on the 128 GiB test
machine. Disabled mode omits the PLE residual at its decoder layer and does not
load the 29.80 GiB mapped N-gram table. This is a lossy architecture ablation,
not an inference optimization or supported quality mode.

Top160 + Hot10, Natural/Exact MoE routing:

| Case | PLE mmap | PLE disabled | Change |
|---|---:|---:|---:|
| Long Decode TPS | 14.48 | 14.16 | -2.2% |
| 3,093-token Prefill TPS | 254.25 | 261.98 | +3.0% |
| Long Decode expert SSD reads | 166.93 GiB | 187.22 GiB | +12.2% |
| MLX peak | 44.08 GiB | 44.08 GiB | unchanged |

Both runs produced coherent text, but their token trajectories diverged as
expected. Removing PLE changed downstream expert routing enough to increase
MoE misses and made long Decode slower despite eliminating PLE row lookups.
Keep PLE enabled; optimize its mmap gather/cache path instead.

## Current recommended experiment configuration

```text
OMLX_QWEN4_DYNAMIC_SLOTS=160
OMLX_QWEN4_HOT_SLOTS=10
OMLX_QWEN4_L1_PROMOTIONS_PER_LAYER=4
OMLX_QWEN4_L1_PROMOTION_ENABLE_AFTER=128
OMLX_QWEN4_DYNAMIC_IO_WORKERS=4
OMLX_QWEN4_PREFILL_RESIDENT_FIRST=0
OMLX_QWEN4_PREFILL_CANONICAL_REUSE=1
OMLX_QWEN4_PREFILL_RETAIN_L1=1
OMLX_QWEN4_BOOST_MODE=natural
OMLX_QWEN4_SCOPE=<current scope>
OMLX_QWEN4_SCOPE_PROFILE=<matching pinned-runtime profile>
```

## Ten-Scope profile v1

The shared DMoE `scope-dataset.v2.json` was reused by explicit path. No DMoE
runtime code or dataset copy was added to this repository. The ten scopes are:

- business/finance, coding, data/AI, general, humanities/social
- legal/policy, math/logic, medical/health, science/engineering,
  writing/creative

Training used all 40 train samples per scope (20 Chinese and 20 English), four
packs per scope, and 64 decode tokens per pack. Evaluation used the disjoint
10-sample test split per scope, split into five packs, with 32 decode tokens
per pack. Runtime A/B used one further disjoint validation prompt per scope and
128 decode tokens.

Held-out router coverage for Top224:

| Bank | Route coverage | All-hit layer steps |
|---|---:|---:|
| Per-Scope Top224 | 96.25% | 74.09% |
| Global Top224 | 96.55% | 77.09% |
| Per-Scope Top224 + previous Top10 | 96.87% | 77.49% |

The ten per-Scope banks have 81.20% mean pairwise overlap. At this wide L1
capacity, a global regularized core is slightly stronger on the held-out
router trace than independently ranked banks. This is a candidate for v2; v1
keeps the requested ten explicit Scope banks.

Real validation A/B, temperature 0, exact Top10, Top224 + Hot10:

| Runtime | Aggregate Decode TPS | Miss calls | SSD expert reads | Peak |
|---|---:|---:|---:|---:|
| Dynamic L1, no Scope | 11.22 | 37,764 | 380.46 GiB | 49.45 GiB |
| Ten-Scope profile | 16.30 | 24,245 | 350.10 GiB | 49.45 GiB |

Scope improves aggregate Decode TPS by 45.3%, cuts miss calls by 35.8%, and
cuts expert SSD reads by 8.0%. All ten generated token sequences are exact
(10/10, 128/128 tokens each). The short-prompt first-token path is slower
because the current implementation primes Scope L1 at the first decode token;
moving this prime to session setup or overlapping it with Prefill is the next
latency optimization.

### Long Decode L1-promotion A/B

Source commit `66736ccaed462e6f366b03d15c10aec5b43213ff` on
`experiment/moe-cache`. Identical prompt, general Top224 Scope, Hot10,
temperature 0, and a 1,024-token generation cap. The answer naturally ended
at 686 tokens in both runs.

| L1 promotions/layer | Decode TPS | Miss calls | SSD expert reads | Read time | Peak |
|---:|---:|---:|---:|---:|---:|
| 0 | 13.16 | 24,078 | 199.33 GiB | 19.26 s | 49.45 GiB |
| 4 | 17.35 | 14,319 | 111.19 GiB | 10.90 s | 49.45 GiB |

Promotion=4 is exact for all 686 tokens and improves Decode TPS by 31.8% while
reducing misses by 40.5% and SSD expert reads by 44.2%. This reverses the
short-generation result: immediate promotion overhead is not recovered on
short answers, but repeated misses amortize it on a long answer. The runtime
policy should therefore keep promotions off initially and enable them after a
token-count/repeated-miss threshold, rather than use one fixed setting for all
requests.

The implemented 128-token delayed gate was then compared at three L1
capacities using the same 686-token deterministic answer, General Scope,
Hot10, and promotion limit four:

| Top | Decode TPS | Prompt TPS | Peak | Miss calls | SSD reads | Promotions |
|---:|---:|---:|---:|---:|---:|---:|
| 224 | 16.54 | 7.31 | 49.45 GiB | 16,548 | 128.52 GiB | 5,075 |
| 160 | 14.48 | 8.76 | 44.08 GiB | 20,491 | 166.93 GiB | 6,974 |
| 128 | 13.26 | 9.89 | 41.15 GiB | 23,338 | 203.11 GiB | 9,019 |

All three runs match exactly for 686/686 generated tokens. Top160 saves 5.37
GiB versus Top224 at a 12.5% Decode TPS cost. Top128 saves 8.30 GiB at a 19.9%
Decode TPS cost. Top160 is the stronger memory/performance tier; Top128 is a
lower-memory fallback and spends substantially more time on SSD reads and L1
promotion churn.

### Boost A/B

Top160 + Hot10, General Scope, four delayed L1 promotions from token 129, and
the same deterministic explanation prompt were used for all modes. Natural is
the exact Top-10 baseline. A protected Top-N mode keeps the N highest-weight
original routes exact and replaces only lower-weight misses with resident
experts; it does not reduce the fixed Top-10 Metal compute shape.

| Mode | Protected routes | Decode TPS | vs Exact | SSD reads | vs Exact | Peak |
|---|---:|---:|---:|---:|---:|---:|
| Natural | 10 | 14.48 | — | 179.2 GB | — | 44.08 GiB |
| Top7 experiment | 7 | 14.95 | +3.2% | 126.9 GB | -29.2% | 44.08 GiB |
| Top6 experiment | 6 | 15.90 | +9.8% | 110.9 GB | -38.1% | 44.08 GiB |
| Top5 / Turbo | 5 | 16.50 | +14.0% | 97.2 GB | -45.8% | 44.08 GiB |
| Top4 experiment | 4 | 17.19 | +18.7% | 87.1 GB | -51.4% | 44.08 GiB |
| Top3 / Blast | 3 | 17.92 | +23.8% | 67.9 GB | -62.1% | 44.08 GiB |

Every Boost answer was complete, coherent, and directly answered the prompt.
Generated lengths differ because Boost is intentionally lossy, so exact token
parity is neither expected nor claimed. This one-prompt smoke is sufficient
for the performance ranking, but not for selecting a production quality tier.
Top5 is evaluated below as the product Turbo setting. Top3 is the product
Blast setting; Top7, Top6, and Top4 remain explicit experiment modes.

The same modes were also tested on an independently cold 3,093-token Prefill:

| Mode | Prefill TPS | vs Exact | SSD reads |
|---|---:|---:|---:|
| Natural | 254.25 | — | 68.4 GB |
| Top7 | 258.87 | +1.8% | 67.1 GB |
| Top6 | 262.59 | +3.3% | 66.7 GB |
| Top5 / Turbo | 262.33 | +3.2% | 66.3 GB |
| Top4 | 264.94 | +4.2% | 65.8 GB |
| Top3 | 263.04 | +3.5% | 65.5 GB |

Prefill gains are modest because a long prompt already amortizes reads across
many tokens and the device-side replacement selection adds work. Top4 was the
best measured Prefill point; Top3 read slightly less SSD but was slower.

#### Top4 L1-capacity scan

The same Top4 Boost policy was then tested at Top224, Top160, and Top128. Each
row used Hot10 and the same delayed promotion and General Scope settings.

| L1 | Exact TPS | Top4 TPS | Boost gain | Top4 SSD reads | Peak |
|---:|---:|---:|---:|---:|---:|
| Top224 | 16.54 | 17.86 | +8.0% | 66.04 GiB | 49.45 GiB |
| Top160 | 14.48 | 17.19 | +18.7% | 81.10 GiB | 44.08 GiB |
| Top128 | 13.26 | 15.85 | +19.6% | 90.82 GiB | 41.15 GiB |

Top224 is only 3.9% faster than Top160 under Top4 Boost while consuming 5.37
GiB more peak memory. Top128 is 7.8% slower than Top160 but saves 2.93 GiB.
This makes Top160 the strongest balanced Boost configuration. Top128 is a
credible low-memory tier; Top224 has a weak memory/performance return once
Boost has already removed most low-weight SSD misses.

Artifacts:

- `benchmarks/results/qwen38_next/boost-long1k-top7-top160-hot10-delayed-p4-v1.json`
- `benchmarks/results/qwen38_next/boost-long1k-top6-top160-hot10-delayed-p4-v1.json`
- `benchmarks/results/qwen38_next/boost-long1k-top4-top160-hot10-delayed-p4-v1.json`
- `benchmarks/results/qwen38_next/boost-long1k-top3-top160-hot10-delayed-p4-v1.json`
- `benchmarks/results/qwen38_next/boost-long1k-top4-top224-hot10-delayed-p4-v1.json`
- `benchmarks/results/qwen38_next/boost-long1k-top4-top128-hot10-delayed-p4-v1.json`
- `benchmarks/results/qwen38_next/boost-long1k-turbo-top5-top160-hot10-delayed-p4-v1.json`
- `benchmarks/results/qwen38_next/boost-prefill4k-turbo-top5-top160-v1.json`
- `benchmarks/results/qwen38_next/boost-prefill4k-{natural,top7,top6,top4,top3}-top160-v1.json`

Commands:

```text
./.venv/bin/python scripts/benchmark_qwen38_next_cached.py CHECKPOINT STORE \
  --slots 224 --hot-slots 10 --promotions 0 --io-workers 4 \
  --max-tokens 1024 --prefill-step-size 2048 --single-short \
  --scope-profile benchmarks/results/qwen38_next/scope-ten-runtime-top224-v1.json \
  --scope general --output benchmarks/results/qwen38_next/long1k-top224-hot10-p0-scope-general-v1.json

./.venv/bin/python scripts/benchmark_qwen38_next_cached.py CHECKPOINT STORE \
  --slots 224 --hot-slots 10 --promotions 4 --io-workers 4 \
  --max-tokens 1024 --prefill-step-size 2048 --single-short \
  --scope-profile benchmarks/results/qwen38_next/scope-ten-runtime-top224-v1.json \
  --scope general --output benchmarks/results/qwen38_next/long1k-top224-hot10-p4-scope-general-v1.json
```

Artifacts:

- `benchmarks/results/qwen38_next/scope-ten-train-top224-v1.json`
- `benchmarks/results/qwen38_next/scope-ten-runtime-top224-v1.json`
- `benchmarks/results/qwen38_next/scope-ten-test-routes-top224-v1.json`
- `benchmarks/results/qwen38_next/scope-ten-top224-heldout-analysis-v1.json`
- `benchmarks/results/qwen38_next/scope-ten-live-noscope-validation-v1.json`
- `benchmarks/results/qwen38_next/scope-ten-live-top224-validation-v1.json`

Scripts:

- `scripts/profile_qwen38_next_scope.py`
- `scripts/compact_qwen38_scope_profile.py`
- `scripts/analyze_qwen38_scope_profiles.py`
- `scripts/benchmark_qwen38_scope_suite.py`

## Remaining gates

1. Implement layer-major/chunk-reuse Direct Prefill and re-run 4K parity.
2. Regularize the ten Scope banks with a shared global core and scan
   Top192/224/256 on the same held-out routes.
3. Exercise AI2Apps session save/restore, multi-turn prompts, cancellation, and
   concurrent request boundaries.
4. Add the model Package only after the Runtime integration tests pass.
