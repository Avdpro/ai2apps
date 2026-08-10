# DeepSeek V4 64-Slot Speed-Only Benchmark

Date: 2026-08-08 (Asia/Shanghai)

The later matched 10-scope comparison of the real oMLX cache pipeline against
DMoE is recorded in `docs/scope-matrix-benchmark-2026-08-08.md`.

## Scope

This run is a performance-only approximation. The router keeps 256 global
expert IDs, while only experts 0-63 are loaded and every routed ID is mapped on
device with `expert_id % 64`. Generated text and logits are intentionally
invalid. These numbers must not be used for parity, quality, hit-rate, or the P1
oracle performance gate.

## Source and environment

- Source commit: `49ec271676ba9c14bbebb75da1912e3fcb5fb0f4`
- Branch: `experiment/moe-cache`
- Model: `/path/to/dmoe/artifacts/deepseek-v4-flash/source`
- Hardware: MacBook Pro, Apple M5 Max, 128 GB unified memory
- Python: 3.13.1
- MLX / MLX Metal: 0.32.0
- mlx-lm: 0.31.3, repository-pinned commit `ab1806e`
- oMLX: 0.5.8.dev1, editable install
- oMLX custom kernels: locally built from this source tree

The safetensors headers account for 148.65 GiB in the full checkpoint:

- Resident experts 0-63: 34.27 GiB
- Dropped experts 64-255: 102.80 GiB
- Non-expert tensors: 11.59 GiB
- Selected 64-slot checkpoint payload: 45.85 GiB

## Load-only memory

Command:

```bash
OMLX_DEEPSEEK_V4_BENCH_EXPERT_SLOTS=64 \
  .venv/bin/python scripts/bench_load_memory.py \
  /path/to/dmoe/artifacts/deepseek-v4-flash/source
```

Result:

- Load time: 5.97 s
- Active MLX memory: 42.67 GiB
- Peak MLX memory: 44.26 GiB
- Reclaimable MLX allocator cache before clear: 35.17 GiB
- MLX allocator cache after `mx.clear_cache()`: 0 GiB

An earlier run incorrectly used `VLMBatchedEngine`, bypassed the selective
mlx-lm loader, and reached 145.46 GiB active memory plus heavy swap. That run
was stopped and is invalid. The standalone benchmark now selects
`BatchedEngine` for text-only configs and `VLMBatchedEngine` only when
`vision_config` is present.

## Standalone throughput

Command:

```bash
OMLX_DEEPSEEK_V4_BENCH_EXPERT_SLOTS=64 \
  .venv/bin/python scripts/bench.py \
  /path/to/dmoe/artifacts/deepseek-v4-flash/source \
  --pp 1024 4096 --gen 64 --warmup 1
```

| Prompt | TTFT | Prefill TPS | Decode TPS | Peak memory |
|---:|---:|---:|---:|---:|
| 1,024 | 1,188 ms | 862 tok/s | 31.5 tok/s | 47.3 GB |
| 4,096 | 5,168 ms | 793 tok/s | 29.6 tok/s | 48.7 GB |

The benchmark script reports peak memory in decimal GB. A short smoke run at
pp=128, gen=16 measured 321 prefill tok/s, 28.9 decode tok/s, and 46.4 GB peak.

## Synthetic cache-miss overhead

This experiment short-circuits storage access: a miss records the expert IDs,
but the expert weights are already present in the 64-slot folded bank. It
therefore measures miss detection, synchronization, route splitting, missed
route computation, and result merging, but no SSD latency or weight upload.

Only the 40 score-router layers participate. The first three hash-router layers
remain unchanged. Exactly half of the score-router layers are designated as
miss layers. A deterministic 100-miss cycle produces the requested expert-count
distribution exactly: 70 x one missed expert, 20 x two, 7 x three, and 3 x
four. Missed IDs are selected from the current token's unique Top-K result, so
the requested number of IDs is always exercised.

The two modes are:

- `cpu`: copy the complete Top-K router result to CPU on every score-router
  layer, detect the synthetic misses there, perform a no-op load, then run the
  unchanged fused MoE computation.
- `gpu`: perform the cache lookup and all-hit flag on device without host
  synchronization. On a designated miss layer, return at most four IDs, compact
  all routes into hit and miss partitions, execute the two partitions
  separately, inverse-permute them, apply router weights, and merge.

The final comparison loads the model once, warms every mode and prompt length,
then runs three measured rounds in a balanced order so every mode appears
first, second, and third once. The table reports per-metric medians. This avoids
both shape-specific Metal compilation and the large thermal drift observed when
the three modes were run as separate processes.

```bash
OMLX_DEEPSEEK_V4_BENCH_EXPERT_SLOTS=64 \
  .venv/bin/python scripts/bench_moe_miss.py \
  /path/to/dmoe/artifacts/deepseek-v4-flash/source \
  --pp 1024 4096 --gen 64 --repeat 3
```

| Mode | Prompt | TTFT | Prefill TPS | Prefill loss | Decode TPS | Decode loss |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | 1,024 | 1,278 ms | 802 | - | 31.0 | - |
| CPU readback | 1,024 | 1,326 ms | 772 | 3.7% | 23.8 | 23.2% |
| GPU split | 1,024 | 1,260 ms | 812 | -1.3% | 26.3 | 15.2% |
| Baseline | 4,096 | 6,884 ms | 595 | - | 29.0 | - |
| CPU readback | 4,096 | 7,320 ms | 560 | 6.0% | 23.3 | 19.7% |
| GPU split | 4,096 | 6,820 ms | 601 | -0.9% | 25.0 | 13.8% |

The small negative GPU prefill losses should be treated as no measurable
regression, not as a guaranteed speedup. Splitting changes route grouping in
the fused kernels and the sustained runs still show thermal variance. The
stable conclusion is that device-side detection plus split execution recovers
about 5-7 percentage points of decode throughput relative to copying every
router result to CPU, while neither prototype includes real storage latency.
The remaining roughly 14-15% decode loss is the next optimization target; a
fused kernel that emits hit accumulation and a compact missed-route worklist
could remove Python-level compaction and the second general SwitchGLU launch.

## Expert-major SSD format

The original direct loader fetches six independently located safetensors
regions per expert and then creates six MLX arrays.  A cache-specific format
was generated under `artifacts/moe-expert-major` with one file per layer and
one fixed, page-aligned record per expert:

- 43 layer files, 256 records per layer.
- 13,369,344 bytes (12.75 MiB) per record, divisible by 4 KiB.
- Tensor order: gate weight/scale, down weight/scale, up weight/scale.
- One 4 KiB self-describing header per layer.
- Total generated bytes: 147,169,914,880 (about 137.1 GiB).
- All 43 payloads passed post-write SHA-256 verification.

The converter reads the existing DMoE offset manifest by explicit path and
does not import or modify the DMoE runtime:

```bash
.venv/bin/python scripts/convert_moe_expert_store.py \
  /path/to/dmoe/artifacts/deepseek-v4-flash/dmoe-direct/offset-manifest.json \
  artifacts/moe-expert-major --layers 0 1 2 ... 42 --verify
```

Layer 42 was written with Darwin `F_NOCACHE` and benchmarked with 64 random
expert reads.  The safe executable path uses one reusable CPU staging buffer,
one contiguous `preadv`, one vectorized Metal copy into an MLX-owned
allocation, and six typed views of that allocation:

| Path | Mean per expert | Median | P90 | Effective bandwidth |
|---|---:|---:|---:|---:|
| Cold `preadv`, reusable staging | 1.081 ms | 1.033 ms | 1.044 ms | 12.36 GB/s |
| Cold `preadv` + six MLX wrappers | 1.261 ms | 1.254 ms | 1.292 ms | 10.60 GB/s |
| Cold `preadv` + vectorized Metal record copy/views | 1.241 ms | 1.072 ms | 2.100 ms | 10.78 GB/s |
| Warm `preadv` + MLX wrappers | 0.698 ms | 0.678 ms | 0.755 ms | 19.15 GB/s |

The raw mmap wrapper result is intentionally excluded: creating an MLX view
does not force Metal to touch every mapped page, so it substantially
understates executable latency.  The explicit record-copy kernel provides a
safe ownership boundary and forces the complete payload to be materialized.

At the historical 42.875 expert misses per generated token, 1.241 ms/expert
plus the measured roughly 40.8 ms/token no-I/O GPU path projects to about
10.6 TPS with serialized I/O.  If prediction hides the previously observed
62.1% of I/O, the projection is about 16.4 TPS.  These are component-model
estimates; an end-to-end cache run is still required.

## Real-SSD timing simulation

The synthetic miss benchmark can optionally perform real `F_NOCACHE` reads
from the expert-major files and run the vectorized Metal record-copy kernel at
the miss boundary.  Routed computation deliberately continues to use the
resident 64-slot folded bank.  This measures real detection, synchronization,
SSD wait, materialization, route splitting, missed-route computation and merge
timing without implementing an L1/L2 replacement policy or requiring correct
model output.  SSD misses are Decode-only because the Decode 1-5 expert
distribution is not valid for Prefill.

The historical profile replays the measured 128-token Top60+rollingTop8
aggregate: 65.49% score-layer miss rate and conditional miss counts
55.98%/32.18%/9.78%/1.88%/0.18% for one through five experts.

```bash
OMLX_DEEPSEEK_V4_BENCH_EXPERT_SLOTS=64 \
  .venv/bin/python scripts/bench_moe_miss.py \
  /path/to/dmoe/artifacts/deepseek-v4-flash/source \
  --pp 128 --gen 64 --repeat 3 \
  --ssd-store artifacts/moe-expert-major --ssd-no-cache \
  --miss-profile historical
```

Balanced three-run medians:

| Mode | Prefill TPS | Decode TPS | Decode loss |
|---|---:|---:|---:|
| Baseline | 337 | 31.4 | - |
| CPU readback + real SSD timing | 234 | 9.2 | 70.7% |
| GPU split + real SSD timing | 240 | 9.4 | 70.1% |

Every measured CPU/GPU run loaded exactly 2,700 experts for 64 requested
generated tokens.  The engine performs 65 Decode forwards, giving 41.54
experts/forward, close to the historical 41.414.  GPU runs spent
3.988-4.001 seconds inside SSD read plus Metal materialization, or about
1.48 ms/expert.  The measured 9.4 TPS validates the serialized-I/O component
model.  CPU and GPU detection differ by only 0.2 TPS once SSD dominates;
prefetch overlap and fewer misses are required for a material improvement.

## Prediction-free same-layer I/O overlap

This experiment does not predict misses or inspect a future layer. After the
current router has returned exact miss IDs, it submits the current layer's hit
routes and shared-expert graph with `mx.async_eval`, performs the same real
`F_NOCACHE` SSD reads on the CPU, materializes the missed records, computes the
miss routes and merges them. Layer-to-layer execution remains strictly
dependent; folded experts still make benchmark values semantically invalid.

```bash
OMLX_DEEPSEEK_V4_BENCH_EXPERT_SLOTS=64 \
  .venv/bin/python scripts/bench_moe_miss.py \
  /path/to/dmoe/artifacts/deepseek-v4-flash/source \
  --pp 128 --gen 64 --repeat 3 \
  --ssd-store artifacts/moe-expert-major --ssd-no-cache \
  --miss-profile historical --compare-overlap
```

| Mode | Decode TPS | Decode loss | Median SSD callback |
|---|---:|---:|---:|
| Baseline | 30.1 | - | - |
| GPU split, serialized | 8.8 | 70.8% | 4.108 s |
| GPU split, same-layer overlap | 9.4 | 68.8% | 4.076 s |

Both arms loaded exactly 2,700 experts per run. The median TPS improvement in
this balanced run is about 6.8%, but the callback interval fell only about
0.8%. Therefore only a small part is proven direct I/O hiding; graph-submit
timing, deferred hit/shared work and thermal ordering can explain the rest.
The result justifies retaining this opt-in path, not claiming a stable 6.8%
production gain yet.

Unlike predictive prefetch, this cannot overlap across a layer boundary, so
its hard ceiling is the resident hit/shared computation available after the
current router fence. Earlier DMoE experiments with the old loader found that
asynchronous resident compute could slow M5 Max because GPU compute and CPU
materialization contend for unified-memory bandwidth. The packed 1.5-ms loader
improves the tradeoff, but the same contention remains relevant.

## Deferred layer-output evaluation A/B

The real-SSD simulation naturally has no explicit `mx.eval(layer_output)`;
the next score-router ID fence materializes the prior layer. To measure the
historical DMoE Stage3 claim in this pipeline, the control arm explicitly
evaluates every Decode layer output, while the defer arm leaves evaluation to
the next router fence or final logits. Both arms enable the same prediction-
free same-layer overlap and load the same 2,700 experts per run.

```bash
OMLX_DEEPSEEK_V4_BENCH_EXPERT_SLOTS=64 \
  .venv/bin/python scripts/bench_moe_miss.py \
  /path/to/dmoe/artifacts/deepseek-v4-flash/source \
  --pp 128 --gen 64 --repeat 3 \
  --ssd-store artifacts/moe-expert-major --ssd-no-cache \
  --miss-profile historical --compare-defer
```

| Mode | Decode runs | Median TPS | Median SSD callback |
|---|---|---:|---:|
| Forced layer sync | 9.4 / 9.3 / 9.3 | 9.3 | 4.121 s |
| Deferred output | 9.3 / 9.3 / 9.3 | 9.3 | 4.130 s |

The approximately 3% historical gain does not reproduce. Within displayed
precision the benefit is zero, and defer is slightly slower in TTFT, Prefill
and SSD callback time. The likely reason is that this pipeline already has a
miss-ID/materialization fence at most score layers and the next router fence
naturally completes the prior layer. Removing a separate layer-end fence adds
no meaningful overlap window. Do not include deferred output as an independent
TPS multiplier in projections for the packed-loader path.

## Real Scope Top60 + rolling Top8 pipeline

The first exact end-to-end cache pipeline now consumes the DMoE scope profile
by explicit path. The three hash-router layers retain all 256 experts. Each of
the 40 score-router layers loads the selected scope's immutable Top60 bank.
Prefill computes nonresident routes with a one-layer transient bank and seeds
Decode from the final prompt token. Decode retains a per-layer rolling Top8;
only IDs absent from both Top60 and Top8 are read from the expert-major store.
Hit, hot and L3 routes use the original quantized `SwitchGLU` kernels and are
inverse-permuted and router-weighted before the HC residual merge. There is no
expert-ID folding or approximate fallback in this path.

Selective load completed in 16.6 seconds with 47.85 GiB active MLX memory and
54.17 GiB peak memory. The end-to-end benchmark uses:

```bash
OMLX_DEEPSEEK_V4_SCOPE_PROFILE=/path/to/dmoe/artifacts/deepseek-v4-flash/scope-study/phase-long128-v1/tiered-top60-global4.json \
OMLX_DEEPSEEK_V4_SCOPE_NAME=coding \
OMLX_DEEPSEEK_V4_EXPERT_STORE=artifacts/moe-expert-major \
OMLX_DEEPSEEK_V4_SCOPE_HOT_SLOTS=8 \
  .venv/bin/python scripts/bench.py \
  /path/to/dmoe/artifacts/deepseek-v4-flash/source \
  --pp 16 --gen 32 --warmup 0
```

An exact A/B changes only `OMLX_DEEPSEEK_V4_SCOPE_HOT_SLOTS`:

| Policy | Decode TPS | L3 experts | L3 payload | Load + publish | Peak memory |
|---|---:|---:|---:|---:|---:|
| Top60 + L3 (`0`) | 3.8 | 7,221 | 89.91 GiB | 8.503 s | 52.5 GB |
| Top60 + rolling Top8 (`8`) | 5.4 | 3,596 | 44.77 GiB | 6.369 s | 56.0 GB |

Rolling Top8 improves this real 32-token Decode run by about 42%, halves L3
payload, and costs 3.5 GB of peak memory. A 64-token run with Darwin
`F_NOCACHE` enabled sustained 5.3 TPS, loaded 4,806 experts (59.84 GiB), spent
9.846 seconds in read plus publish, and peaked at 56.0 GB. Thus the 5.4 TPS
result is not merely a short-run page-cache effect.

The phase-separated Prefill path also completed a real `pp=128, gen=8` run:
11.650-second TTFT, 11 prefill tok/s, 6.8 decode tok/s, and 55.9 GB peak. It
loaded 3,206 transient Prefill experts and 469 Decode experts. The low Prefill
rate is expected from exact on-demand materialization of a large per-layer
tail and is the largest remaining performance problem.

Current limitations:

- A scalar miss-count synchronization remains at every score layer. Global
  router IDs remain on device; only actual missed IDs cross to the host.
- The first version uses one explicit scope and disables the separate MTP
  routed stack. Scope classification and MTP cache policy remain future work.
- End-to-end generation is operational and all expert weights are exact, but
  the required full-resident Top-10 parity gate has not yet been run because
  the full checkpoint exceeds this machine's practical resident-memory limit.
- The generic synthetic benchmark prompt is not representative of coding
  scope affinity. Per-scope workload medians are needed before treating 5.3
  TPS as a product-level expectation.

### Prediction-free parallel reads within the current layer

The packed loader now issues the current layer's exact missed-expert reads to
four reusable staging buffers with four `preadv` workers. This does not predict
a future miss, cross a layer dependency, or overlap Metal weight publication
with MoE compute. The latter was tested and reverted because unified-memory
contention reduced Decode from 5.2 to 4.8 tok/s.

A balanced A/B loaded the model once, reused exactly the same 16-token prompt,
cleared rolling Top8 between requests, enabled `F_NOCACHE`, and alternated
1/4-worker order over two rounds. Every arm loaded exactly 3,391 experts:

| Read workers | Median Decode TPS | Median read + publish | Experts |
|---:|---:|---:|---:|
| 1 | 4.90 | 6.775 s | 3,391 |
| 4 | 5.05 | 6.281 s | 3,391 |

Four workers reduce the measured storage boundary by 7.3% and improve Decode
by 3.1%. The absolute TPS varies substantially with the generated route trace:
a separate 64-token four-worker run selected 5,212 Decode L3 experts and
sustained 4.4 TPS. Therefore the matched-route +3.1% result, rather than a
cross-process absolute-TPS comparison, is the valid optimization claim.

The four-worker path is now the default. It can be changed with
`OMLX_DEEPSEEK_V4_SCOPE_IO_WORKERS`; `scripts/bench_scope_io.py` reproduces the
balanced comparison.

### Scope-cache Prefill startup warmup

Source commit: `49ec271676ba9c14bbebb75da1912e3fcb5fb0f4` plus the working-tree
scope-cache changes recorded in this document.

The matched `coding-zh-validation-05` run showed that the low short-Prefill
rate was dominated by one-time Metal/JIT work rather than expert I/O. A
different coding prompt used as warmup improved the target prompt from about
5.1 to 18.1 tok/s while keeping Decode at 9.1 tok/s. The production path now
runs one scope-affine 32-token, one-output-token request during
`BatchedEngine.start`, disables prefix-cache storage for it, and clears the
rolling Top8 plus reclaimable MLX allocator cache before accepting traffic.
It is strictly gated on the DeepSeek V4 model type and all three scope-cache
environment variables.

Matched automatic-warmup result:

| Mode | Model start | TTFT | Prefill TPS | Decode TPS | Prefill L3 | Decode L3 | Peak |
|---|---:|---:|---:|---:|---:|---:|---:|
| Cold control | 16.37 s | 4.750 s | 5.3 | 9.1 | 916 | 1,006 | 55.9 GB |
| Auto warmup 32 | 25.81 s | 1.648 s | 15.2 | 8.8 | 916 | 1,006 | 55.9 GB |

The warmup improves request-level short Prefill by 2.87x and TTFT by 66.5%,
with identical measured expert counts and no material peak-memory change. It
moves roughly nine seconds into model startup; it does not reduce total cold
load-plus-first-request work. A 128-token synthetic follow-up reached 20
Prefill tok/s versus the historical cold result of about 11 tok/s, but is not
a matched publication-grade A/B. The scope-matched 32-token Decode result
remains in the established 8.8--9.1 tok/s range.

The warmup length defaults to 32 and can be changed or disabled:

```bash
OMLX_DEEPSEEK_V4_SCOPE_WARMUP_TOKENS=16  # shorter startup warmup
OMLX_DEEPSEEK_V4_SCOPE_WARMUP_TOKENS=off # retain cold-request behavior
```

Reproduction command (ordinary page cache, no `F_NOCACHE`):

```bash
OMLX_DEEPSEEK_V4_SCOPE_PROFILE=/path/to/dmoe/artifacts/deepseek-v4-flash/scope-study/phase-long128-v1/tiered-top60-global4.json \
OMLX_DEEPSEEK_V4_SCOPE_NAME=coding \
OMLX_DEEPSEEK_V4_EXPERT_STORE=/path/to/ai2apps/artifacts/moe-expert-major \
OMLX_DEEPSEEK_V4_SCOPE_HOT_SLOTS=8 \
  .venv/bin/python scripts/bench_scope_once.py \
  /path/to/dmoe/artifacts/deepseek-v4-flash/source \
  /path/to/dmoe/configs/scope-dataset.v2.json \
  coding-zh-validation-05 --gen 32 \
  --output /tmp/omlx-prefill-autowarm.json
```

Two attempted runtime changes were rejected and not enabled: fixed-size
Prefill expert banks measured 5.2/8.9 Prefill/Decode tok/s versus 5.3/9.1 for
dynamic sizing, and merging the per-layer miss fences measured 5.1/9.0. These
results do not support either change as an independent optimization.

### 10k-token Prefill

The default 32-token startup warmup followed by a synthetic coding
`pp=10000, gen=8` run completed without memory pressure:

| Prompt | TTFT | Prefill TPS | Decode TPS | Prefill L3 | L3 payload | Read + publish | Peak |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 10,000 | 71.615 s | 140 | 5.3 | 36,871 | 466.51 GiB | 54.549 s | 59.4 GB |

Command:

```bash
OMLX_DEEPSEEK_V4_SCOPE_PROFILE=/path/to/dmoe/artifacts/deepseek-v4-flash/scope-study/phase-long128-v1/tiered-top60-global4.json \
OMLX_DEEPSEEK_V4_SCOPE_NAME=coding \
OMLX_DEEPSEEK_V4_EXPERT_STORE=/path/to/ai2apps/artifacts/moe-expert-major \
OMLX_DEEPSEEK_V4_SCOPE_HOT_SLOTS=8 \
  .venv/bin/python scripts/bench.py \
  /path/to/dmoe/artifacts/deepseek-v4-flash/source \
  --pp 10000 --gen 8 --warmup 0
```

The 36,871 Prefill loads are far above the at-most 7,840 distinct
nonresident layer/expert pairs for Top60. The default 2,048-token Prefill
step processes the prompt in about five chunks and rebuilds each layer's
transient bank per chunk. This makes repeated chunk I/O the dominant 10k
bottleneck. Decode is reported for completeness only: this synthetic prompt
is not a scope-matched Decode workload.

### 10k larger-prefill-step comparison

The standalone benchmark now accepts `--prefill-step-size`. With the same
model, synthetic 10k prompt, coding scope, eight generated tokens, and startup
warmup, increasing the step size reduces repeated transient-expert loads:

| Prefill step | Chunks | TTFT | Prefill TPS | vs. 2,048 | Prefill L3 experts | L3 payload | Load + publish | Peak |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2,048 | 5 | 71.615 s | 140 | baseline | 36,871 | 466.51 GiB | 54.549 s | 59.4 GB |
| 4,096 | 3 | 50.445 s | 198 | +41% | 22,628 | 288.53 GiB | 33.811 s | 60.0 GB |
| 5,120 | 2 | 40.060 s | 250 | +79% | 15,290 | 197.18 GiB | 22.983 s | 63.0 GB |

The measured memory growth was much smaller than the conservative DeepSeek V4
prefill admission estimate: only 0.6 GB for 4,096 and 3.6 GB for 5,120 relative
to the measured 2,048 peak. The 5,120 setting is therefore the best tested 10k
single-request throughput point: compared with 4,096 it adds another 26% TPS
for about 3 GB. Decode TPS from this synthetic, non-scope-matched prompt remains
diagnostic only (5.3, 5.5, and 5.6 TPS respectively).

Reproduce either larger-step run by appending one of the following to the 10k
command above:

```bash
--prefill-step-size 4096
--prefill-step-size 5120
```

### DeepSeek V4 memory-safe adaptive prefill

DeepSeek V4 now selects its Prefill step from the total context length while
leaving the scheduler's global 2,048 default unchanged for every other model:

| Total context | DeepSeek V4 step | Conservative transient target |
|---:|---:|---:|
| <=128K | 5,120 | <=18.3 GiB |
| <=256K | 4,096 | <=17.4 GiB |
| <=512K | 3,072 | <=17.8 GiB |
| >512K | 2,048 | <=18.3 GiB at 1M |

The policy counts an existing prefix-cache base when choosing the band and is
shared by external and interleaved chunked Prefill. Above 128K, a final query
chunk that is not divisible by 64 is split into a 64-aligned native-indexer
chunk plus at most 63 tokens. At shorter contexts it deliberately keeps one
unaligned tail: a tested `5,120 + 4,864 + 15` 10k split rebuilt the MoE bank for
the tiny third chunk and regressed from 250 to 140 TPS. Restricting tail
alignment to long contexts preserves the two-chunk 10k fast path.

With no explicit step argument, the real 10k scope-cache benchmark confirms
that the automatic policy is active:

| Policy | TTFT | Prefill TPS | Prefill L3 | L3 payload | Load + publish | Peak |
|---|---:|---:|---:|---:|---:|---:|
| Auto (`5,120 + 4,879`) | 40.200 s | 249 | 15,299 | 200.28 GiB | 23.423 s | 63.1 GB |

For controlled A/Bs, passing `--prefill-step-size N` disables the model policy
and runs the requested fixed step. Production/default benchmark runs omit the
flag and use the adaptive schedule. Existing physical-footprint prediction,
the 256-token emergency floor, pre-submit OOM guard, and per-chunk Metal cache
reclaim remain active underneath this proactive schedule.

## Prefill versus Decode router parity

`scripts/bench_router_parity.py` replays exactly the same fixed token IDs in
two modes with fresh KV caches: one full Prefill forward and one token at a
time. It temporarily wraps each loaded MoE gate, records the real Top6 and
weights, and computes Top10 for the 40 score-router layers. The wrappers are
removed after each run and do not change the Top6 returned to the model.

The final run used 512 tokens from the Python benchmark corpus:

```bash
OMLX_DEEPSEEK_V4_SCOPE_PROFILE=/path/to/dmoe/artifacts/deepseek-v4-flash/scope-study/phase-long128-v1/tiered-top60-global4.json \
OMLX_DEEPSEEK_V4_SCOPE_NAME=coding \
OMLX_DEEPSEEK_V4_EXPERT_STORE=/path/to/ai2apps/artifacts/moe-expert-major \
OMLX_DEEPSEEK_V4_SCOPE_HOT_SLOTS=8 \
  .venv/bin/python scripts/bench_router_parity.py \
  /path/to/dmoe/artifacts/deepseek-v4-flash/source \
  --tokens 512 \
  --text-file omlx/admin/bench_corpora/code_python.txt \
  --output artifacts/router-parity-coding-512.json
```

| Metric | Result |
|---|---:|
| Top6 exact set rate | 71.42% |
| Top6 mean membership overlap | 5.640/6 (94.01%) |
| Weight-ranked Top5 mean overlap | 4.707/5 (94.15%) |
| Top10 exact set rate | 52.49% |
| Top10 mean membership overlap | 9.299/10 (92.99%) |
| Per-layer route-frequency cosine, mean | 99.925% |
| Per-layer route-frequency cosine, minimum | 99.849% |
| Prefill/Decode Top60 overlap, mean | 57.55/60 (95.92%) |
| Prefill/Decode Top60 overlap, minimum | 54/60 |
| Decode Top60 self-coverage | 81.917% |
| Prefill Top60 coverage of Decode routes | 81.732% |
| Prefill replacement coverage loss | 0.186 percentage points |
| Instrumented Prefill / Decode replay | 10.35 s / 82.75 s |

For a fixed causal sequence the two modes are mathematically equivalent, but
the current Prefill and M=1 Decode kernels are not bit-exact. Differences grow
through the deeper layers and primarily exchange experts near the TopK cutoff;
the final-logit Top1 rate was 97.66%. Consequently Prefill should not replace
real Decode traces for rolling Hot8, route transitions, or exact per-token miss
replay. For the scope-level Top60 bank, however, the aggregate frequency vector
is effectively the same and loses only 0.186 points of Decode-route coverage in
this experiment. Large Prefill replays are therefore suitable as the primary
Scope profiler, ideally replaying both prompt text and previously generated
continuations so the sampled token distribution matches serving traffic.

## Isolated hierarchical Scope Prefill experiment

`scripts/profile_scope_prefill.py` builds one dotted leaf Scope from real
Prefill routes without importing anything into the normal inference path. It
uses exclusive file creation, refuses to target the active input profile, and
checks the input profile SHA-256 both before and after collection. The runtime
continues to select a profile explicitly at process startup with
`OMLX_DEEPSEEK_V4_SCOPE_PROFILE`, and accepts dotted names such as
`OMLX_DEEPSEEK_V4_SCOPE_NAME=code.python`.

The first trustworthy leaf uses four evenly spaced 4,096-token windows from
the dedicated Python corpus. The real scheduler internally runs a singleton
Prefill tail and a final singleton forward; the collector retains the former
and excludes only the last singleton for each request and layer.

```bash
OMLX_DEEPSEEK_V4_SCOPE_PROFILE=/path/to/dmoe/artifacts/deepseek-v4-flash/scope-study/phase-long128-v1/tiered-top60-global4.json \
OMLX_DEEPSEEK_V4_SCOPE_NAME=coding \
OMLX_DEEPSEEK_V4_EXPERT_STORE=/path/to/ai2apps/artifacts/moe-expert-major \
OMLX_DEEPSEEK_V4_SCOPE_HOT_SLOTS=8 \
  .venv/bin/python scripts/profile_scope_prefill.py \
  /path/to/dmoe/artifacts/deepseek-v4-flash/source \
  --scope code.python \
  --text-file omlx/admin/bench_corpora/code_python.txt \
  --sample-tokens 4096 --samples 4 \
  --output artifacts/scope-prefill-v1/code.python-16k-prefill-v1.json
```

| Metric | Result |
|---|---:|
| Profiled Prefill tokens | 16,384 |
| Top6 routes per score layer | 98,304 |
| Excluded final singleton forwards per layer | 4 |
| Mean instrumented Prefill throughput | 224.9 tok/s |
| `code.python` Top60 self-coverage | 64.851% |
| Old `coding` Top60 coverage on the same routes | 31.733% |
| Coverage gain | 33.118 percentage points |
| New/old Top60 overlap | 19.7/60 mean, 15/60 minimum |
| Artifact SHA-256 | `da143be45728322f180b60b6d1f53d743ec914355d6e0f6d5a82f7d8bc5998cc` |

The artifact also preserves all 256 per-expert Top6 counts, Top10 counts, and
routed weight sums for each of the 40 score layers, so later samples can be
merged or re-ranked without rerunning this trace. A short real inference run
loaded this new JSON as `code.python` and completed successfully. The old DMoE
profile remained read-only with SHA-256
`66a83a5af4abb541482052f814330fdf359d7a6580d5a394b18e1dfaf8cf2855`.

`configs/scope-prefill-leaves.v1.json` records the current artifact as a
source-only seed, not a complete `code.python` profile.
`code.cpp` and `science.math` remain blocked on dedicated corpora; the mixed
oMLX source corpus is intentionally not relabeled as C++.

### `code.python` versus `coding` on Python dialogue

The source-code-trained `code.python` profile was compared with the existing
dialogue-trained `coding` profile on the same 128-token Python conversations:
`coding-en-validation-16` was run twice in alternating order and
`coding-zh-validation-11` once. Both profiles used identical Hot8 and expert
store settings. The leaf alias was passed with `bench_scope_once.py
--runtime-scope code.python`; the DMoE dataset remained read-only.

| Metric, mean across EN and ZH dialogue | `coding` | `code.python` | Change |
|---|---:|---:|---:|
| Decode TPS | 8.875 | 7.100 | -20.0% |
| L1 Top60 all-hit layer rate | 21.35% | 1.49% | -19.85 pp |
| L1+Hot8 no-SSD layer rate | 42.72% | 19.81% | -22.91 pp |
| SSD experts per Decode token | 35.39 | 65.63 | +85.5% |
| Expert-loader time per request | 9.236 s | 12.942 s | +40.1% |

The English repeat was deterministic in cache activity: old `coding` loaded
4,971 Decode experts and ran at 8.5--8.6 tok/s; `code.python` loaded 8,381 and
ran at 7.0 tok/s in both orders. The Chinese sample showed the same direction,
9.2 versus 7.2 tok/s and 4,088 versus 8,420 loaded Decode experts.

This does not indicate a global-ID mapping fault. The profiler records global
router IDs and the runtime lookup consumes the same IDs. Instead it is a token
distribution mismatch: raw Python source alone is not representative of the
full Python workload. `code.python` should remain one semantic Scope, trained
from a balanced mixture of source reading/completion, code generation and
modification, debugging, natural-language questions and explanations, tests,
packaging/dependency/project context, and generated continuations. The failed
artifact is only a source-only seed and must not be used as the final
`code.python` profile.

### Mixed-context `code.python` rebuild

A second candidate kept `code.python` as one semantic Scope and sampled equal
token budgets from Python source and complete chat-template conversations.
Sixteen held-out-topic training prompts covered generation, modification,
debugging, testing, explanation, performance, packaging, review, and project
architecture in English and Chinese. Each included a real 96-token generated
continuation. The profiler drew 8x1,024-token windows from each corpus, for
8,192 source plus 8,192 conversation/continuation tokens.

The route audit produced exactly 98,304 Top6 routes per score layer. On the
mixed training trace, the candidate Top60 covered 67.856% of routes versus
47.060% for old `coding`. The decisive held-out conversation A/B was:

| Mean across held-out EN and ZH Python dialogue | `coding` | source-only `code.python` | mixed `code.python` |
|---|---:|---:|---:|
| Decode TPS | 8.875 | 7.100 | 8.050 |
| L1 Top60 all-hit layer rate | 21.35% | 1.49% | 10.19% |
| L1+Hot8 no-SSD layer rate | 42.72% | 19.81% | 31.24% |
| SSD experts per Decode token | 35.39 | 65.63 | 48.07 |
| Expert-loader time | 9.236 s | 12.942 s | 10.805 s |

The mixed data recovers 13.4% Decode TPS over the source-only seed and cuts
SSD expert loads by 26.8%, confirming that the data distribution is more
accurate. It still trails the old broad `coding` profile by 9.3% Decode TPS,
so it remains a candidate rather than a production default. The next dataset
iteration should retain the unified `code.python` label while adding more
diverse contexts and longer continuations and reducing raw-source dominance.

### Mixed-context v3 and parent regularization

V3 added 16 new English/Chinese contexts across 13 categories and increased
their generated continuations to 160 tokens. Together with v1, the dialogue
pool contains 32 contexts and 4,096 generated continuation tokens. The route
trace retained the same 16,384-token budget but changed the mix to 25% source
and 75% chat-template prompt/continuation.

The raw v3 profile reached 69.306% self-coverage on its training routes. A
single predeclared regularization candidate retained the first 40 ranked old
`coding` experts per layer and filled the remaining slots from raw v3. This
kept an average 43.05/60 old experts while preserving 65.587% v3 training
coverage. No further values were tuned on the two validation prompts.

| Held-out EN/ZH Python dialogue mean | `coding` | v2 | raw v3 | v3 keep40 |
|---|---:|---:|---:|---:|
| Decode TPS | 8.875 | 8.050 | 8.200 | 8.500 |
| L1 Top60 all-hit layer rate | 21.35% | 10.19% | 13.01% | 17.97% |
| L1+Hot8 no-SSD layer rate | 42.72% | 31.24% | 34.38% | 37.29% |
| SSD experts per Decode token | 35.39 | 48.07 | 44.02 | 40.91 |
| Expert-loader time | 9.236 s | 10.805 s | 10.383 s | 9.949 s |

V3 improves every metric over v2; parent regularization improves them again.
The best candidate is nevertheless 4.2% below old `coding` Decode TPS and
therefore remains non-default. Further work needs a larger independent Python
training and validation matrix instead of tuning replacement counts against
the same two held-out conversations.

## Decode expert-frequency review overhead

`scripts/bench_scope_review.py` measures frequency tracking without performing
promotion or replacement. It leaves the original Gate installed in `off`. In
`on`, it retains the score layers' existing Top6 arrays and, every 16 Decode
tokens, packs 16x40x6 uint8 IDs into one 3,840-byte review, synchronizes once,
and updates complete per-layer expert counters on CPU.

The controlled run used a full 128-token warmup for each mode followed by
three runs per mode in `off/on/on/off/off/on` order. Every on-run reviewed
exactly 30,720 IDs in eight reviews and produced the same counter checksum.
Fallback calls, Hot8 hits, loaded expert counts, bytes, and all other cache
activity were identical across every run.

| Metric | Review off | Review every 16 |
|---|---:|---:|
| Median Decode TPS | 9.5 | 9.5 |
| Mean Decode TPS | 9.500 | 9.467 |
| Median measured TPS loss | - | 0.0% |
| Mean measured TPS loss | - | 0.35% |
| Review time per 128-token request | - | 16.42 ms |
| Review time per review | - | 2.05 ms |
| Review time per Decode token | - | 0.128 ms |

An earlier 32-token-warmup run reported a 2.08% median loss, but its first
measured request spent roughly one extra second in the SSD loader. The full
warmup removes that cold-state bias. The controlled conclusion is that a
16-token review has no median-visible Decode regression and roughly 0.35%
mean overhead in this real scope-cache workload.

## Dynamic L1 replacement trace experiment

The first replacement experiment is deliberately offline and non-invasive.
`scripts/capture_scope_routes.py` captures the real Top6 Decode routes after a
normal model run, and `scripts/simulate_dynamic_l1.py` replays them through an
exact static-L1/LRU-L2 cache. Neither script changes the default inference
path or the existing Scope JSON. Two independent 128-token English and
Chinese Python validation conversations contributed 61,440 expert selections.

Every 16 tokens, each layer considers the hottest resident L2 expert and the
coldest unpinned L1 expert. A replacement requires a minimum observation
count, an absolute margin, a ratio margin, and a per-layer cooldown. The L1
victim moves into L2, so subsequent eviction and reload costs are included in
the simulation rather than treating promotion as free.

| Configuration (mean of EN/ZH) | SSD experts/token | Change vs static same-size cache | L1 route hit | Replacements / 128 tokens |
|---|---:|---:|---:|---:|
| Static L1 60 + L2 8 | 35.625 | - | 74.40% | 0 |
| Dynamic L1 + L2 8, min 8, cooldown 32 | 34.965 | -1.85% | 75.70% | 97.5 |
| Static L1 60 + L2 12 | 32.273 | - | 74.40% | 0 |
| Dynamic L1 + L2 12, min 5, cooldown 64 | 31.754 | -1.61% | 75.53% | 79.5 |
| Static L1 60 + L2 16 | 29.445 | - | 74.40% | 0 |
| Dynamic L1 + L2 16, min 5, cooldown 64 | 29.156 | -0.98% | 75.52% | 80.0 |

For every listed dynamic policy the absolute margin is 3, the ratio is 1.5,
and the first 40 profile-ranked experts per layer are pinned. The aggressive
L2-8 setting with minimum count 5 and cooldown 32 saves 2.59% SSD reads but
performs 137.5 replacements, so it is not the first real-runtime candidate.

Dynamic replacement alone is positive but modest. Increasing L2 from 8 to
12 reduces simulated SSD reads by 9.4% before replacement at a cost of about
1.99 GiB; L2 16 reduces them by 17.3% at about 3.98 GiB. To isolate the value
of replacement, the first physical-slot prototype should retain Hot8 and use
minimum count 8, margin 3, ratio 1.5, pin 40, and cooldown 32. Its acceptance
test must include the measured 0.35% review overhead and the actual cost of
copying persistent expert slots; a mapping-only replay is not sufficient to
claim a TPS gain.

This work was subsequently deferred to the Session/Thread phase. Dynamic L1
state must be conversation-owned and installed at a turn boundary rather than
mutating a global cache during Decode. See
[`session-adaptive-l1-roadmap.md`](session-adaptive-l1-roadmap.md) for the
recorded architecture and re-entry gates.

## Validation

- DeepSeek V4 plus MTP regression: 205 passed, 1 skipped.
- The current Scope policy, expert store, and DeepSeek patch focused run passes
  109 tests, including the startup-warmup isolation checks.
- Reduced-bank loader, sanitizer, router preservation, and device modulo tests
  are included in `tests/test_deepseek_v4_patch.py`.
- With locally built native kernels enabled, the pre-existing affine block MoE
  exact-equality test differs from stock `gather_qmm` by 0.0078125 in FP16. The
  new reduced-bank tests pass; this native-kernel discrepancy is recorded for
  separate investigation.
- An expanded run including DSpark native-kernel exact-equality tests produced
  5 failures (289 passed, 1 skipped). They are in ring GEMM/sparse-attention
  tests and do not touch the MoE files changed here; the printed BF16 values
  match at normal display precision but fail bitwise equality.
