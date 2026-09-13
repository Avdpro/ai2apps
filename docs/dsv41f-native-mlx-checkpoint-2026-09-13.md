# DS4.1 Flash native MLX checkpoint — 2026-09-13

Latest: the independent [pure-MLX text forward](dsv41f-pure-mlx-checkpoint-2026-09-13.md)
replaces the remaining CPU tensor operations. Final 2048+32 measurement: 104.81
Prefill TPS, 6.63 Decode TPS, 54.895 GB sampled peak. The historical mixed paths
below remain comparison artifacts; see the new checkpoint for numerical limits.

The user authorized normal floating-point differences while preserving original model weights. This supersedes CPU bitwise equality as a blocker for native MLX exploration. It does not establish model-quality equivalence: record logits, Top-K and generation differences, and retain the CPU reference unchanged.

Research branch: `experiment/moe-cache`; source commit `11b5b9ac537e42b1029d1f0148bbbe6a33307f8e`. Individual experiment source hashes are in each manifest because these research files are uncommitted. Apple M5 Max, 128 GiB unified memory. Target: ~10 Decode tokens/s and ~300 Prefill tokens/s at 2048 input tokens. Neither target has been reached.

## Implementation

- `native_mx.py`: native MXFP8 `quantized_matmul` and MXFP4 `gather_qmm` over original packed checkpoint bytes and UE8M0 scales. Retains activation quantization, router weighting before down projection, and original expert count. Sorted physical slot indices enable grouped dispatch; inverse permutation restores token order.
- `run_native_cached.py`: module-owned ordinary FP8 GPU cache (5,666,242,560 bytes), grouped BF16 `wo_a` cache (2,684,354,560 bytes), and FP32 output head (2,647,654,400 bytes). The head follows the official BF16-checkpoint-to-FP32 arithmetic contract.
- Expert cache remains fixed L1=8 plus LRU L0=24 per layer, 40 layers, ~22.41 GiB slot payload. Cold records use the existing GLM/Qwen C++ `preadv_fused_experts` loader. Pending MLX operations are evaluated and synchronized before native slot overwrite. Router and several backbone operations still execute on CPU.
- `run_native_cached_bf16.py`: native matmul activation operands become BF16 after original FP8 activation quantization/dequantization. Normal-range FP8 × power-of-two values fit BF16; this is not another weight quantization. Different native accumulation paths still change rounding.
- `mlx_attention.py`: GPU block-64 online sparse attention retaining BF16 probabilities and FP32 state.
- `run_native_sdpa.py`: experimental native SDPA using official sparse indices, masked invalid entries, and attention sinks. Inputs, sinks and outputs are BF16; native softmax is FP32. In particular, casting sinks and replacing block-64 probability rounding is an additional numerical difference and is explicitly experimental.

All wrappers import unchanged official model source and preserve the CPU reference harness. They do not constitute a fully GPU-resident runtime. Legacy `cpu_order_fp8` and `batched_cpu_attention` manifest sections describe inherited wrapper scaffolding; `native_mx`, `native_gpu`, `native_cached`, and `native_sdpa` identify actual overrides.

## Measurements

Artifact directories below are under `artifacts/`, all suffixed `-20260913`. Times include trace capture and CPU snapshot serialization, exclude model construction, and have not been corrected for profiling overhead. OS file cache was not flushed. Logical read bytes do not prove physical SSD bandwidth.

| Artifact prefix | Input tokens | Prefill s | Decode forwards s |
|---|---:|---:|---|
| dsv41-metal-batched-attention-prefill2048 | 2048 | 266.920 | 4.243 |
| dsv41-native-cached | 5 | 3.438 | 0.606, 0.411, 0.578 |
| dsv41-native-cached-prefill2048 | 2048 | 66.440 | 60.064 |
| dsv41-native-cached-bf16 | 5 | 4.340 | 0.680, 0.482, 0.638 |
| dsv41-native-cached-bf16-prefill2048 | 2048 | 61.814 | 31.668, 6.214 |
| dsv41-native-sdpa | 5 | 4.226 | 0.615, 0.507, 0.434 |
| dsv41-native-sdpa-profile2048 (cProfile) | 2048 | 60.065 | 33.243, 6.296 |
| dsv41-native-benchmark2048 (reduced capture) | 2048 | 49.858 | 33.037, 6.645 |

The BF16 block-64 run reaches 33.1 Prefill tokens/s. Long-context Decode is unstable and much slower than short-input measurements. High system compressed-memory occupancy was observed, but its causal contribution has not been isolated. Do not describe these as steady-state Decode acceptance numbers. CPU snapshot/serialization overhead and native kernel shape specialization need separate attribution.

## Numerical evidence

`test_native_mx.py` validates all FP4 nibble encodings and varying UE8M0 scales, plus repeated/unsorted slots with nonzero integer input vectors. Both F32 and BF16 native activation variants passed. Actual checkpoint layer-0 expert probes previously matched strict Metal for sampled inputs.

`audit_native_fp8.py` compared 30 same-input FP8 calls against CPU: observed per-call differences were sparse, typically adjacent BF16 values. However, end-to-end differences amplify through the model. For the five-token BF16 cached run, first-step logits had max absolute difference 6.955, RMSE 1.578, cosine 0.8878 and Top-10 overlap 7/10. The first two greedy output tokens match CPU, then generation differs. This cannot be characterized as bitwise parity or an established negligible quality change.

`assess_numerics.py` verifies checkpoint/config/trace hashes and records full-logit RMSE, cosine, KL, Top-1/Top-10 and output IDs. Comparisons after generated tokens diverge are marked as different contexts. Raw prompt completion after EOS is a harness continuation, not a quality benchmark. Independent CPU validation at 2048 tokens remains absent.

SDPA operator probes at 64 heads × 512 dimensions, lengths 1 and 7, invalid-index masking and random sinks returned finite outputs with RMSE 0.000905 and 0.001043 against CPU. Full-model short-run results are saved separately; operator tests do not establish whole-model equivalence.

## Reproduction

Run from the repository root with a fresh output path and Metal access:

```sh
PYTHONPATH=experiments/dsv41_reference .venv/bin/python \
  experiments/dsv41_reference/run_native_sdpa.py \
  --expert-store artifacts/dsv41-full-expert-store \
  --output artifacts/dsv41-native-sdpa-new --decode 3
```

For the fixed 2048-token prompt, load `artifacts/dsv41-benchmark2048-prompt.json`, put its `prompt` string in the `--prompt` argument, and use `--decode 2`. The file contains token IDs and round-trip checks; do not approximate the length by characters. To profile, call the runner through `cProfile.Profile().runcall(...)` and save `runtime.prof` alongside its manifest.

Next priorities: attribute long-context stalls, use per-expert matrix batches efficiently during Prefill, reduce CPU/GPU transfers, and then tune L0/L1 capacity with measured miss rates and a full memory budget. Cache expansion without measuring memory pressure is premature.

## Capture overhead isolation

The SDPA 2048 profile attributes substantial time to serialization (26.1 seconds internal), batched routed dispatch (26.0 seconds cumulative), native expert reads (11.6 seconds), and ordinary FP8 GEMMs (11.5 seconds). These totals span Prefill and two Decode forwards; nested profiler times must not be added or directly subtracted to claim throughput.

`run_native_benchmark.py` omits only trace hooks whose closures reference the harness `save` function. Load/release hooks and all official arithmetic remain active. It discards buffer serialization and saves logits/Top-K; harness buffer cloning still occurs. This is a performance companion, not a replacement for the full numerical reference. Its manifest explicitly records reduced capture scope.

The reduced-capture run completed at **41.1 Prefill tokens/s**. All three full-logit tensors match the profiled full-capture SDPA run exactly (max absolute difference zero), with identical Top-10 order and generated IDs. Thus the capture reduction preserved sampled computation. Long-context Decode still took 33.0 and 6.6 seconds: serialization is not an adequate explanation for that stall. The current timing remains far below both target gates, and native runtime/memory behavior still needs finer per-step attribution.

## User memory budget including video

The user set a total inference-memory ceiling of 70G including video. Until unit clarification, use the conservative decimal limit of 70,000,000,000 bytes (65.19 GiB). Include CPU and GPU allocations, expert banks, vision/video encoder and activations, KV, scratch and transient peaks. Do not treat the MLX allocator limit alone as the total-process limit.

Current 2048 reduced-capture run reports MLX peak 34.399 GiB and peak RSS 27.126 GiB; short SDPA reports 33.901 GiB MLX and 35.623 GiB RSS. These metrics are different accounting views and must not be added or used as a complete uncompressed footprint. Explicit persistent payloads total approximately 40.60 GiB: expert bank 22.412, ordinary GPU FP8 5.277, grouped wo_a 2.500, FP32 head 2.466, and CPU store 7.938. Runtime and transient storage are additional. CPU/GPU copies coexist in this prototype.

All these runs set vision_n_layers=0: there is no measured video-inclusive peak yet. Reserve the video and transient budget before expanding Main/L1. The 70G requirement is recorded, not yet validated or enforced by this research runner.

## Single-owner MLX weight migration

`run_native_owned.py` removes the 290 FP8 Linear weight/scale parameters from the CPU harness parameter templates after model construction, binds each module to its checkpoint key, and lazily loads original packed bytes once into owned MLX arrays. It preserves the same activation quantization and native BF16 QMM as the preceding SDPA runner. The Store bypasses CPU dense admission for those keys, the output head and grouped wo_a. It does not merely disable caching and reread weights per token. Remaining CPU backbone operations are unchanged.

Validated short artifact: `artifacts/dsv41-native-owned-short-v2-20260913`. All four logits tensors and Top-10 orders exactly match the preceding native SDPA run. There are 290 module loads for 1,160 calls; 661 raw bypass reads cover 580 FP8 tensors, 80 grouped wo_a tensors and one output-head tensor. CPU dense payload falls from 8,522,859,968 to 355,640,768 bytes: **7.61 GiB removed**, leaving **0.331 GiB**. GPU ordinary FP8 payload remains 5,666,242,560 bytes, rather than gaining another copy.

Short Prefill takes 2.689 s; Decode takes 0.484/0.400/0.331 s. These timings use reduced trace capture and therefore are not a controlled speed comparison against the earlier full-capture short run. Peak RSS is 29.138 GiB and MLX peak is 33.901 GiB, different accounting views that must not be summed.

The first `native-owned-short` artifact predates explicit SDPA binding in the early model import; it is diagnostic and is not the accepted SDPA comparison. `short-v2` explicitly binds and records 160 SDPA calls. L1/L0 remain 8/24 during this ownership experiment so that cache-capacity changes do not confound it. Video remains disabled.

The 2048-token single-owner run also passed: `artifacts/dsv41-native-owned2048-20260913` has exactly equal full logits and Top-10 order for all three steps against `native-benchmark2048`. Prefill is 45.870 s (**44.65 tokens/s**), versus 49.858 s previously; Decode is 19.852/5.702 s versus 33.037/6.645 s. These are separate runs without controlled OS cache/pressure, so timing changes are observations rather than an isolated causal speedup. Peak RSS is 22.349 GiB and MLX peak 34.399 GiB. Persistent CPU dense payload remains 0.331 GiB, with 290 GPU loads across 870 FP8 forwards and 661 raw bypass reads total. The 7.61 GiB persistent-payload reduction is independently established by cache ownership/counts.

Remaining work includes long-context stall attribution, GPU-native residual/router/activation flow, larger adaptive Main/L1 with a small Hot/L0, and measured video-inclusive acceptance below 70 GB. Current success is numerical parity to the preceding native path for weight-ownership migration, not independent CPU/CUDA quality equivalence or completion of the 10/300 TPS targets.

## Allocator accounting correction

Per-forward allocator instrumentation in `dsv41-gpu-act2048-20260913` revealed **35,611,574,272 active bytes plus 74,054,797,858 cached bytes** after Prefill (~102.14 GiB total allocator occupancy). `get_peak_memory()` reported only 36,935,401,472 bytes, so earlier active-peak observations did not establish compliance with the total 70 GB budget. CPU and other runtime allocations are additional. The large idle allocator pool is a plausible contributor to memory pressure; causality requires an A/B run.

The GPU activation version uses the validated group32 Metal quantizer for ordinary FP8 linears and raw BF16 host transfer, preserving original activation quantization. Short timings are 3.834 s Prefill and 0.541/0.446/0.380 s Decode; 2048 timings are 42.506 s Prefill and 16.056/5.443 s Decode. Full-logit comparisons are retained separately. `run_bounded_allocator.py` will bound the idle MLX pool to 2 GiB for the controlled follow-up. This is not a whole-process hard memory limit.

## Context-selected Main24/Hot8

`run_context_main.py` keeps the same 32 physical slots per layer but assigns 24 to Main and 8 to Hot. Once the current layer has routed the full Prefill, its observed expert frequencies select Main24 (ascending ID tie-break); these records are loaded directly into Main slots. Decode tokens are never used to select the initial Main. Remaining Prefill experts pass through Hot8. Main remains fixed during the short Decode test; per-token promotion is not implemented in this experiment.

`dsv41-context-main2048-20260913` reports Prefill 41.430 s and Decode 13.404/0.614 s. The two Decode steps have 192/2 Main/Hot hits out of 240 requests, then 180/7: **80.83% and 77.92%** hit rates, versus old bootstrap Main8/Hot24 at 27.50% and 50.42%. All three logits and Top-10 orders exactly match the single-owner baseline. Expert payload stays 22.412 GiB. The initial Main priming reads are separately reported (960 records); Prefill cache counters do not include those as misses.

This completed run still used the unbounded/default idle allocator configuration and cannot be used to claim the total 70 GB budget. A bounded-allocator combination is being tested separately.

## Bounded idle-pool A/B result

`dsv41-bounded-allocator2048-20260913` sets the MLX idle cache to 2,147,483,648 bytes (previous default: 130,567,005,798). Prefill is **34.784 s / 58.88 TPS**, Decode **0.614/0.413 s**, compared with the otherwise matching GPU-activation run at 42.506 s and 16.056/5.443 s. All three full logits and Top-10 orders are exactly equal. This strongly implicates allocator-pool memory pressure in the earlier long Decode stalls, though OS state was not controlled independently.

After Prefill: active 35,611,459,584 bytes plus cached 2,086,027,370 bytes (~35.11 GiB). Observed active peak is 36,935,286,784 bytes; adding the 2 GiB cache ceiling gives a conservative allocator-only upper bound of ~36.40 GiB. CPU/Python buffers and video remain outside this bound. Video-inclusive <=70 GB acceptance still requires an actual video workload and process-footprint tracking.

## Combined bounded context cache

`run_context_bounded.py` composes single-owner FP8 weights, Metal activation quantization, context-selected Main24/Hot8, per-forward allocator observation and the 2 GiB idle pool limit. `dsv41-context-bounded2048-20260913` reports Prefill **35.466 s / 57.75 TPS**, Decode **0.530/0.370 s**, identical full logits and Top-10 for all three steps relative to the preceding single-owner path. Actual Decode hit rates remain 80.83%/77.92%. After Prefill active+cached is 37,369,577,470 bytes (~34.80 GiB). Active peak+idle ceiling is an allocator-only bound of ~36.07 GiB, not a video-inclusive process peak.

A 32-Decode extension uses the same 2048 input and changes only requested Decode count plus derived max_seq_len allocation. Its cache manifest reports every Decode phase. This extension has no independent CPU reference at that length.

## 32-step Decode validation of the combined path

Artifact: `dsv41-context-bounded2048-decode32-20260913`. Fixed input length 2048; 32 one-token Decode forwards after Prefill. Prefill **35.510 s / 57.67 TPS**. Aggregate Decode **2.656 TPS** (32 divided by total Decode time), median step 0.369 s, first step 0.537 s. Excluding only the first step gives 2.693 TPS. Actual Main+Hot hits are **5,935 / 7,680 = 77.28%**. These are one-run measurements, not a multi-prompt performance guarantee.

All steps completed with finite trace logits. The first three logits match the shorter combined run exactly; that is a prefix comparison with a different derived max_seq_len allocation, not full-configuration CPU/CUDA parity. No independent reference exists for all 32 steps.

Maximum observed step-boundary active+cached occupancy is **34.797 GiB**. Active peak plus the cache ceiling is **36.067 GiB** as an allocator-only bound; peak RSS is **36.085 GiB** and is not added to the allocator metric. CPU/Python and video accounting still require a real video workload. The earlier oversized idle-pool behavior is corrected in this runner.

Current practical baseline is `run_context_bounded.py`: Main24/Hot8, ~22.41 GiB expert slots, ~0.33 GiB remaining CPU dense cache, GPU activation quantization and 2 GiB idle allocator cap. Remaining throughput gap is substantial: 2.66/57.7 versus targets 10/300. Future experiments should keep the allocator cap and measure larger context-selected Main capacity, promotion and per-expert Prefill batching without changing routing or weight precision.

## Current user scope: text-only 65 GB

The user deferred multimodal work and set a **65,000,000,000-byte pure-text process peak target**. This supersedes the earlier 70 GB video-inclusive budget for the current optimization phase. `run_text_budget.py` sets an MLX allocator memory limit of 60 GB, retains the 2 GiB idle pool limit, and samples macOS `rusage_info_v2.ri_phys_footprint` every 20 ms using the current process PID. Crossing 65 GB aborts at subsequent model/layer boundaries and marks the receipt failed. This is sampled enforcement, not an instantaneous OS hard limit; RSS and active-allocator peaks are not substitutes for process footprint.

The Main48/Hot8 capacity experiment (`dsv41-main48-budget65-20260913`) reached **90.87%** aggregate Decode hits over 32 steps, with **2.530 Decode TPS** and Prefill 36.282 s. Sampled physical footprint peak was **63,660,108,376 bytes**, within the sampled budget but with little headroom. It did not improve aggregate Decode throughput over Main24. All 33 logits were checked against the Main24 32-step run through the numerical report. Main40 is being tested as a less memory-constrained candidate.

Relevant existing designs reviewed: DS4F `switch_layers.py` keeps expert sorting/scatter and routed arithmetic on MLX and prefers native gather_qmm for M5 Prefill-sized work. GLM `dynamic_cache.py::_prefill_direct_locked` groups resident work separately from cold expert work and compares dispatch counts; Qwen uses the shared tiered executor with retained Main and canonical reuse. `device_prefill.py` adopts resident-first grouping, uploads input/routing once per layer, retains grouped expert results on device until route-order restoration and FP32 summation, then transfers one MoE result per layer. It retains the existing native loader and lazy-consumer fences. Its short-input four-step logits match the preceding single-owner path exactly.

## 65 GB Main40 and GPU accumulation results

Main40/Hot8 (`dsv41-main40-budget65-20260913`) reached **87.27%** hit rate over 32 Decode steps, **2.717 Decode TPS**, Prefill 35.380 s, sampled physical-footprint peak **57.629 GB**. All 33 logits exactly match the Main24 baseline. Main48 improved hits further but had worse aggregate throughput and a 63.660 GB sampled peak; Main40 is the more conservative current allocation.

`run_device_moe.py` adds ordered FP32 route summation on GPU for Decode to the resident-first device Prefill implementation. In `dsv41-device-moe-main40-20260913`, Prefill dispatched 516 expert groups but returned only 40 host result tensors, one per layer. Across 32 Decode steps, host expert-result elements fell from 39,321,600 to 6,553,600 (sixfold reduction). All 33 logits match Main40 exactly. Prefill is **34.868 s / 58.74 TPS**, Decode **2.703 TPS**, sampled peak **57.462 GB**. Removing these transfers alone did not yield a material throughput gain. Router, attention boundary tensors and much of the backbone remain CPU-bound interfaces; this is not a full device-resident graph.

A real-weight layer-0 microbenchmark compares gathered MXFP4 with per-expert matrix GEMM. At 128 and 512 tokens per expert, GEMM is substantially faster in this small probe, with sparse BF16 rounding differences. At 8–64 tokens, larger discrepancies occur, and padding to 64 does not resolve them. The follow-up `run_matrix_prefill.py` therefore uses matrix GEMM only for >=128-token expert batches and retains the existing gathered path for smaller batches. This experimental arithmetic variant needs its own full-model numerical assessment and is not yet accepted as a replacement.

## Mixed matrix/gather Prefill candidate

`dsv41-matrix-prefill-main40-20260913` completed fixed 2048 input plus 32 Decode forwards, Main40/Hot8, under the 65 GB sampled process budget. Prefill **29.256 s / 70.00 TPS**, versus device-gather Main40 at 34.868 s / 58.74 TPS (about 19.2% higher throughput). Decode **2.714 TPS**, sampled physical-footprint peak **57.328 GB**. Kernel counters include all three expert projections: 2,910 matrix expert-projection calls and 1,121,667 matrix rows, with 352,893 gathered rows. Original checkpoint bytes, activation quantization and expert routes are retained; native matrix accumulation differs.

All **33 generated token IDs match** the device-gather run. This is **not logit/Top-K exactness**: first Prefill logits have max absolute difference 3.943, RMSE 0.559, cosine 0.98656, KL 0.00001691 and Top-10 overlap 9/10. Full 33-step metrics are in `numerics.json`; no general quality equivalence is claimed. Under the user-authorized normal floating-point-difference policy this is a performance candidate, while `run_device_moe.py` retains the exactly matched gather comparison path.

Current reproduction, with a fresh output directory, is `PYTHONPATH=experiments/dsv41_reference .venv/bin/python experiments/dsv41_reference/run_matrix_prefill.py --main-slots 40 --expert-store artifacts/dsv41-full-expert-store --output <fresh-path> --prompt <fixed-2048-prompt> --decode 32`. Obtain the exact prompt from `artifacts/dsv41-benchmark2048-prompt.json`. The benchmark still runs original CPU-backed attention/residual/router scaffolding around MLX kernels; full GPU backbone migration and SSD/GPU prefetch overlap remain outstanding. Targets of 10 Decode / 300 Prefill TPS remain unmet.
