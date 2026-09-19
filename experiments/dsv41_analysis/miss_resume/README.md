# DS4.1F GPU miss / resume — experimental, default off

This experimental Decode executor has a lightweight native-dispatch packet path
and a GPU-predicated cross-layer path. It is isolated from the installed MLX wheel
and the existing default model/Runtime. The original guarded backend had a large
performance regression; auto now stays on native packets at every hit rate.

## Optimized Burst windows

Window admission is now adaptive: cold/low-hit tokens use the native packet
boundary; at most two required-miss layers in the preceding token admits a window.
The first window miss returns the remaining token to packet execution.
`DSV41_WINDOW_FORCE=1` retains unconditional windows for diagnostic reproduction;
it is excluded from the all-miss cost-floor claim. See
`docs/dsv41f-allmiss-cost-floor-2026-09-16.md` for tests and the first-transition caveat.

`DSV41_ASYNC_WINDOW=1` adds per-layer asynchronous submission inside native
windows, overlapping graph construction with GPU execution without a new host
wait. It remains opt-in. See `docs/dsv41f-allhit-pipeline-isolation-2026-09-16.md`
for the zero-miss diagnostic and the separate real-miss paired benchmark.

`--resume-mode window --resume-burst-top 2 --resume-block 2` selects native
speculative windows with exact rollback to the first missing layer's MoE.
It computes and discards an invalid suffix instead of stopping those GPU kernels.
`guarded` retains true GPU stop and now uses native dispatch before the first Gate.
Both executors retain only layer-local rollback state. Forced windows regroup
after a miss; adaptive windows return the remaining token to native packets.
Auto still uses packet execution; high-miss workloads can lose with windows.
See `docs/dsv41f-burst-window-optimization-2026-09-16.md` for measurements.

## Run

From the repository root, using the repository Python environment:

```sh
.venv/bin/python experiments/dsv41_analysis/miss_resume/build.py
.venv/bin/python experiments/dsv41_analysis/miss_resume/launch.py \
  --resume-mode auto --resume-block 4 --prefill-slots 64 --decode 64 --logits-mode hash \
  --output artifacts/my-miss-resume-run
```

`--resume-mode auto` (default) starts with one native GPU packet boundary per layer.
The packet includes required miss IDs/ages/promotion scores, so a miss does not
need a second metadata readback. There are no ICBs, extra per-operator barriers,
whole-state snapshots or donation restrictions on this path. Slots remain on GPU
on hits; the original SSD loader/fence is retained on misses.

Auto does not automatically enter guarded windows. The historical 2048/128
Top2 check found no net benefit from that policy, so the automatic transition was
removed. `guarded` remains explicitly selectable for research. Diagnostic
transition tests still exercise first-miss native-tail recovery.

`--resume-mode packet` always uses the lightweight path. `--resume-mode guarded`
uses the optimized ICB executor for diagnostics. `--resume-block`
defaults to 4 and controls explicitly requested guarded windows only; it does not
change native packet boundaries. Auto currently stays on packets even at high hit
rates.

`--resume-burst-top 2` or `4` selects the same required Top-N / cold-tail-zero,
original-weight policy as the existing Burst implementation. `--resume-eager-control`
runs the existing algorithm using the same isolated backend for attribution.
`--resume-block` accepts 1, 2, 4, or 40. A resumed Block1 includes the saved MoE and
the following layer's router; it does not submit a resume-only block unless at the
end of the model. Block40 permits the full layer chain plus final logits to
complete without intermediate host checks on an all-hit token. Large windows are
expensive when misses are frequent.

Guarded windows support batch-one text Decode after Prefill, 384 routed experts /
Top6, Main40/Hot8 and eviction_dual, Natural and Burst Top2/4 with zero cold tails.
The native packet adapter additionally preserves Static/Adaptive/Burst forwards
for vision/chat inputs, tracing and route capture, other L1 shapes/policies,
Burst tail policies, Prefill Burst and alternate expert/attention dispatch. Auto
selects this adapter for those combinations; it does not revert to legacy.
Prefill uses the existing implementation. Concurrent requests/streams, L2
prediction and Runtime packaging remain outside this entry point.

## GPU execution and continuation

- The pinned MLX 0.32.0 backend wraps dispatches in immutable Metal indirect
  commands. The GPU writes their execution range to zero on the first required
  miss, so later kernels are not dispatched. No placeholder result is accepted.
- Pipeline state is explicitly encoded in each ICB. Inheriting it produced zero
  GEMM outputs in the initial probe. Buffers use explicit resource declarations;
  the encoder preserves native concurrent dispatch/data barriers, with a predicate
  publication barrier at each Gate.
- The bridge captures selected IDs, required misses, existing slots, ages and
  promotion scores in the same miss packet. Router IDs stay on GPU on all-hit
  paths. Actual SSD reloads use the existing `LRUMetalBank.prepare` and native
  GLM-derived `preadv_fused_experts` implementation.
- A continuation owns the HC residual/mixes, normalized FFN input, router IDs and
  weights, and the state after the current attention. Resume starts at that MoE;
  it does not rerun attention or update the token hash twice.
- Snapshots use independent native array handles rather than `mx.array(value)`:
  that constructor creates a lazy copy. Every saved dependency and tracked bank
  consumer is included in the guarded evaluation, and completed consumers are
  retired before loading. Skipped graph outputs must never be evaluated after
  disabling the predicate or committed to model/cache state.
- Slot contents/mappings remain stable for a submission. Updates are published
  only after the submission completes and the existing bank loader finishes.
  Frequency/age/counter state from the skipped suffix is discarded. A miss cannot
  recur at the same layer within a token; unexpected progress raises an error.
- Engram row addresses are resolved before submission; the row tensors become
  dependencies of the first gate. There is no added host wait to materialize the
  token's initial tensors. The final normalization/head is inside the final
  guarded submission, and invalid candidate logits are never returned.

## Reproducibility

The MLX source commit is `7a1d4f5c12ac82f4b4d0a6e71538d89ca0605247`.
`mlx0320-miss-resume.patch` is applied only to its isolated artifact checkout.
The build uses `MLX_METAL_JIT=OFF` and directly reads the installed wheel's original
`mlx.metallib`. Recompiling all kernels through JIT changed the Prefill baseline;
those early results are diagnostic artifacts, not valid performance comparisons.
The bridge requires an exported backend ABI marker, so it cannot silently use the
unpatched library. The launcher sets the library search path only for its child.

`smoke.py`, `pause_stress.py`, and `opcheck.py` are backend checks; `compare.py`
compares all saved tensor bytes, including BF16, without loading a GPU runtime.
`benchmark_final.py` checks every logit against the corresponding installed-engine
reference. Benchmarks run one GPU process at a time and count the first Decode in
reported total TPS; tail32 is a separate metric. No OS file-cache purge is claimed.

## Native-packet validation

`packet_smoke.py` checks hit/miss/optional-tail metadata and shared-buffer reuse.
`benchmark_packet.py` runs paired eager/native-packet benchmarks sequentially.
`--resume-stress-all-miss` is a diagnostic only: it invalidates all expert tags
before each Decode layer in both reference and candidate, causing all six routed
experts to reload through the real loader. It is supported only for Natural
packet/auto or eager control. Its manifest is explicitly marked; this artificial
cache setup must not be quoted as normal product TPS.

`transition_check.py` alternates packet and guarded entry for correctness testing;
it retains auto's immediate first-miss exit to a native tail. It is not a speed
benchmark; normal auto does not enter guarded windows.

## Preserve existing variants through the packet hook

`route_packet.py` supplies the packet implementations of `routes_all_hit`,
`miss_metadata` and `burst_miss_metadata`. Everything before/after these hooks
remains in the selected original StaticModel, AdaptiveModel or BurstModel. This
preserves each variant's frequency observation order, maintenance policy, tail
weights, vision Prefill and diagnostic callbacks. Static L1 has no promotion
score; policies that maintain outside a miss keep their existing maintenance
boundaries. The adapter does not add maintenance readbacks.

Sequential Burst uses its own original tail implementation. `--block-layers 2/4`
with standard zero-tail Burst maps to the new guarded window setting; a selected
packet adapter uses sequential boundaries and records the requested old block
size separately. The old rollback executor remains available via explicit legacy.
`validate_combinations.py` records old/new logits, cache/SSD/promotion parity,
diagnostic tensors and collected routes for representative supported variants.

## Report performance against the right workload

`recheck_historical_workload.py` anchors current old/new comparisons on the saved
historical 2048-token input with 128 Decode steps. `recheck_anchor_followup.py`
checks native-only auto and the historical baseline-L1/Prefill0 Top2 settings.
Always identify input fixture, input/Decode lengths, L1/Prefill policy, full Decode
TPS including first Decode, and separately labelled tail throughput. A 32-token
coding fixture's TPS must not replace the historical high-hit benchmark number.
See `docs/dsv41f-tps-anchor-recheck-2026-09-16.md` for the remaining startup gap.
