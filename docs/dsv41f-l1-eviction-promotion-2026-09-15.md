# DS4.1F L0 eviction promotion — 2026-09-15

Historical memcpy-stage results: use `--promotion-copy` with eviction_dual to
reproduce this variant. Current eviction_dual defaults to zero-copy slot exchange.

New `eviction_dual` policy promotes only experts actually about to leave L0.
Ranks use the existing 8/64 half-life, 75%/25% mix. At most four evicted experts
are considered per miss, score >=3 and advantage >2 over a replaceable L1 expert.
Current requested L1 experts are protected. Free L0 slots do not cause promotion.
No standalone periodic maintenance, frequency readback or promotion fence.

Natural miss IDs/ages/scores share one readback (previously two for IDs/ages).
Burst IDs/required/mapping/ages/scores share one readback (previously four).
All-hit routing IDs remain on device. The existing per-layer hit flag readback
is unchanged. Rank updates execute on GPU. Copies and SSD writes share exactly
one existing miss fence; all lazy bank consumers finish before any overwrite.
Payloads are copied before the evicted L0 source is overwritten. No SSD reread
for promotions. Native GLM/Qwen preadv remains the miss loader.

## Paired results

Two cases, two repeats in AB/BA order, eight fresh processes. Exact generated IDs
and every logits hash match across policies. Six small native/bank tests passed,
including one-fence copy-before-overwrite and current-request protection.

| Case | Policy | TPS | Hit % | Requested GB | Cache readbacks | Bank fences | Copy s | I/O s | Peak GB |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| coding-en-train-18 | baseline | 4.496 | 71.097 | 230.834 | 13740 | 4522 | 0.294 | 9.257 | 55.211 |
| coding-en-train-18 | eviction_dual | 4.442 | 73.018 | 212.917 | 9211 | 4171 | 0.746 | 8.974 | 55.237 |
| long-math_logic-zh-test | baseline | 4.859 | 71.995 | 856.444 | 55152 | 17938 | 0.834 | 36.240 | 57.351 |
| long-math_logic-zh-test | eviction_dual | 4.823 | 73.309 | 800.400 | 36967 | 16567 | 2.065 | 35.506 | 57.333 |

Readbacks are cache-path API calls reconstructed from actual miss events and the
inspected call sites, not Metal driver transaction counts. They include the
per-layer `.item()`, miss `.tolist()` calls and baseline periodic score reads.
Unchanged output/logits reads are excluded. Bank fences are instrumented `_fence`
calls including initialization/Prefill, which are identical across each pair.
Both counts must not increase in any pair. These checks prove no added policy
boundary; different routing/cache behavior can still change miss counts on other
prompts, so the paired totals are not a universal guarantee for all workloads.
GPU task execution time can change even with fewer host readbacks.

Requested GB includes initialization/Prefill; I/O and copy times are distinct.
TPS excludes Prefill and includes all Decode forwards. Peak budget is 65 decimal GB. Natural Decode is exact;
Burst remains approximate. Top2/Block1 and Top4/Block4 each passed a 32-step
smoke test with 7680 committed routes, Hot copies and peak <55.116 GB. No model Runtime/Package has been published.

Run `.venv/bin/python experiments/dsv41_analysis/l1_policy/benchmark_eviction.py`.
Receipts and source snapshot: `artifacts/dsv41-l1-eviction-20260915/`.

## Decision and post-benchmark guards

Keep `baseline` as the default reproducible control and expose the new mechanism
with `--l1-policy eviction_dual`. Short/long TPS changed -1.20%/-0.75%; no speedup
is claimed. Fewer readbacks and lower requested bytes are repeatable across both
runs. Copy time still rises (long: 0.834→2.065 s) while native I/O falls only
36.240→35.506 s, so reduced synchronization count alone is insufficient.

After throughput collection, added a host-only guard against float32 metadata
age overflow and rejected the incompatible legacy `--promotion-reread` flag.
These guards add no GPU readbacks or fences and do not change tested arithmetic.
The original and final source snapshots are both retained.
