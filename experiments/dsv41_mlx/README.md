# DS4.1 Flash: independent MLX text forward

This research runner reads our SSD-ready checkpoint and its native expert store. Its inference process does not import PyTorch. Attention, KV
compression, indexer, router, routed/shared experts, mHC, Engram hash and gating,
normalization, RoPE, and the output head execute as MLX/Metal tensor operations.
The original reference runner remains available for offline comparison.

CPU work remains for tokenization, file reads, sparse row addresses, expert cache
replacement metadata, and output serialization. The standard text Decode executor
is `packet`: one native GPU-to-CPU route boundary per layer at all hit rates.
`auto` remains a compatibility alias that resolves to `packet`. Guarded windows remain explicit
experiments until their net performance benefit is established. Expert route IDs stay on the GPU on hits. Miss
packets also carry dynamic-L1 maintenance metadata; no separate maintenance
readback is added. Engram embedding
rows are read on demand from SSD, then dequantized on the GPU.

## Run

From the repository root, with the SSD checkpoint, complete
`artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD/experts`, and compiled native expert loader:

```sh
.venv/bin/python experiments/dsv41_mlx/run.py \
  --prompt-json artifacts/dsv41-benchmark2048-prompt.json \
  --decode 32 --output artifacts/my-pure-mlx-run
```

The standalone CLI defaults to `--inference-mode packet` for the validated
L1=40/L0=8 `eviction_dual` configuration. Build its isolated backend once:

```sh
.venv/bin/python experiments/dsv41_analysis/miss_resume/build.py
```

`--inference-mode legacy` selects the original executor. `packet` is the standard
per-layer packet boundary, and `guarded` is the older expensive ICB diagnostic.
A missing new backend produces an actionable error, not a silent substitution.
Auto resolves to the native packet adapter for vision/chat input, tracing/route capture,
alternate L1 capacities or policies, alternate Burst tails and experimental
dispatch settings. Their existing mathematical forward and cache maintenance are
preserved; only the miss boundary is replaced. These combinations no longer fall
back to legacy. Explicit guarded windows still reject combinations requiring the
packet adapter. The actual selection/reason is printed and saved in the manifest.
Existing input/parameter validity rules remain in force.
Imported benchmark modules retain their injected Model; this selector applies to
the standalone command. This is not a published Runtime/Worker integration.

Output must be a new directory. `--decode 32` runs one Prefill and 32 single-token
Decode forwards, producing 33 greedy output tokens. EOS does not stop this fixed
benchmark. `--trace` saves intermediate layer tensors as safetensors; it is meant
for numerical investigation, not throughput measurements. Per-layer blocking
evaluation and progress logs are disabled by default. `--layer-progress` restores
them for diagnostics; `--trace` also enables them. Router math and expert buffer overwrite fences are preserved. `--gather-only`
disables the large-group Prefill matrix path.

L1/Main defaults to 40 experts per layer, initially chosen from that input's Prefill
route frequencies, with L0/Hot at 8 experts per layer. **Dynamic L1 is enabled by
default**, using `eviction_dual`: GPU short/long frequency estimates score L0
eviction candidates; promotion uses zero-copy slot-role exchange at the existing
miss boundary. There is no separate periodic maintenance readback.
Use `--static-l1` to retain the initial Main selection for a comparison run.
Hot uses LRU replacement metadata. Both hold original packed expert bytes. Expert
reads reuse the GLM native loader through the existing Metal bank implementation.
No future generated routes are used to select Main.

The idle MLX allocator cache is capped at 2 GiB. The runner samples process
physical footprint every 20 ms and checks the 65 decimal GB budget at step
boundaries (also at layer boundaries with `--layer-progress` or `--trace`). This is a sampled guard, not an instantaneous OS memory cap.
The receipt records checkpoint and source hashes, memory, timings, route/cache
counts, `layer_progress`, `trace_enabled`, `l1_policy`, promotion details and `torch_imported: false`.
The frozen v1 archive retains the original static behavior. No layers are made
fully resident; the text-only 65 GB budget remains in effect.

## Optional Burst and speculative layer blocks

`--burst-top 2` or `--burst-top 4` enables approximate **Decode only**. Prefill
remains exact. Top-N means the first N entries of the native router's biased
Top-6 ranking, before sorting expert IDs for execution. These experts must be
loaded and evaluated. Remaining Top-6 contributions are retained if resident,
otherwise zeroed; original routing weights are not renormalized. The shared
expert always executes. This does not guarantee parity with full-expert inference.

```sh
.venv/bin/python experiments/dsv41_mlx/run.py \
  --burst-top 2 --block-layers 4 \
  --prompt-json artifacts/dsv41-benchmark2048-prompt.json \
  --decode 128 --output artifacts/my-burst-run
```

`--block-layers 1` is the sequential Burst control and the default. Values 2/4
enable speculative blocks only with Burst; requesting them without `--burst-top`
is rejected. Burst currently uses dynamic L1 and rejects `--static-l1`.

Every layer boundary retains hidden/mHC and model-state snapshots. A block
collects required-miss flags on-device and validates them together. On failure,
it commits only the prefix before the **first** required miss, restores that
layer's entry state, loads its required misses, completes that layer, then opens
a new block at the following layer. Later speculative routes are discarded.
Engram token history advances once outside the block loop. Dynamic L1 frequency,
LRU ages, and cache statistics update only for committed layers. Native bank
overwrite fences remain enabled. Speculative output is materialized before any
recovery write.

`burst.json` records block acceptance, first-miss offsets, discarded layers,
required loads and omitted tail contributions. `--trace` in Burst Decode records
accepted router IDs and logits; speculative intermediate layers are not exported.
The runner's 20 ms footprint sampling and step-boundary 65 GB guard remain active;
Burst Decode does not run the usual per-layer output logging/guard callback.

Neither Burst nor block execution is enabled by default. Predictive L2 is not
implemented. See the [Burst benchmark](../../docs/dsv41f-burst-block-checkpoint-2026-09-13.md)
for numerical comparisons and measured costs.

### Experimental resident tail substitution

With Burst and Block1, `--burst-tail fixed-top` replaces cold tail experts with
the highest biased-router-score resident candidates not already selected. Native
Top-N and resident members of the original Top-6 are retained. Top-N weights stay
unchanged; the original tail weight mass is distributed among the final tail
experts according to their unbiased scores.

`--burst-tail renorm` chooses the same way but normalizes unbiased scores across
all six final experts, so it can also change Top-N weights. When no replacement
is needed, both policies preserve the original weights exactly. Substitutes cause
no additional SSD loads. Dynamic L1 frequencies continue to observe the true
native Top-6; LRU ages track experts actually executed.

`--burst-tail zero-renorm` performs no substitution: cold tails remain zero,
and retained expert weights are rescaled to sum to the original route scale
(1.5). All-hit weights remain unchanged. This changes Top-N weights too;
the measured accuracy benefit varies by input.

The default remains `--burst-tail zero`. Non-default tail policies with Block2/4 are currently
rejected. See [tail-policy measurements](../../docs/dsv41f-burst-tail-checkpoint-2026-09-13.md)
before selecting an approximate policy.

## Validation and scope

```sh
PYTHONPATH=experiments/dsv41_mlx .venv/bin/python experiments/dsv41_mlx/test_kernels.py
PYTHONPATH=experiments/dsv41_mlx .venv/bin/python experiments/dsv41_mlx/test_core.py
.venv/bin/python experiments/dsv41_mlx/compare.py REFERENCE_DIR CANDIDATE_DIR
```

Tests and the offline comparator import Torch in separate processes. Inference
does not. The comparator accepts the earlier Torch-serialized CPU/mixed reference
artifacts. It reports logits, KL, Top-10 overlap and generated IDs; identical
short generation does not establish general numerical equivalence.

Current scope is batch-one pure text: a full initial Prefill followed by
single-token Decode. Chunked Prefill, MTP, multimodal processing and production
oMLX integration are not implemented here. This is a translation of the local
official implementation; attribution/license is in `LICENSE.DeepSeek`.

See [the measured checkpoint](../../docs/dsv41f-pure-mlx-checkpoint-2026-09-13.md).

### Experimental Prefill double buffering and Burst

`--prefill-slots 64` enables two model-wide SSD-direct scratch banks. Main40 and
Decode Hot8 are unchanged. Values consuming a scratch bank finish before that
bank is overwritten; the other bank can compute during the native read. Scratch
is released after Prefill. Slots 32/64/96 are available; 0 preserves the original
serial path and remains the default while this experiment is evaluated.

`--prefill-slots 64 --prefill-top 2` (or 4) independently enables approximate
Prefill. Keep every token's original Top-N plus original tail routes whose expert
is resident or required by another token in the batch. Omitted routes are zero,
without renormalization or substitution. Decode stays exact unless `--burst-top`
is also supplied. Prefill changes affect subsequent hidden/KV state; compare the
first prediction as well as fixed-reference Decode logits.

The manifest records `prefill_report` scratch reads separately from legacy bank
reads. `expert_total_read_bytes` and `expert_total_io_seconds` include both in
new runs. Early experiments lacking the total fields require adding the scratch
and legacy counters. Benchmark/quality results are recorded in
[the Prefill checkpoint](../../docs/dsv41f-prefill-optimization-2026-09-13.md).

`--shared-dispatch` enables experimental Prefill expert scheduling reuse. It
quantizes the common gate/up input once and shares the matrix/gather partition,
slot permutation, inverse permutation and gather indices across all three
projections. Down still quantizes its own weighted activation. Decode and the
128-row matrix threshold are unchanged. This switch is independent of scratch
size and Prefill Burst, and remains opt-in pending throughput evidence.

`--fused-gate-up` also implies shared dispatch and concatenates original packed
gate/up output rows for one Prefill projection. It packs only the used slot
prefix, does not rewrite SSD weights, and leaves Decode unchanged. **This
experiment regressed Prefill throughput and remains disabled by default.** See
[the fusion measurements](../../docs/dsv41f-fused-gate-up-2026-09-13.md).

With double buffering, the final Hot8 experts are now loaded directly into Hot
and computed there, eliminating the scratch-read-plus-Hot-reread handoff. The
complete Hot working set and LRU expert order are preserved. Use
`--prefill-hot-reread` for the tagged v2 handoff control. This saves logical SSD
reads but has not demonstrated a significant end-to-end TPS gain.

`experiments/dsv41_analysis/profile_prefill.py` records synchronized nested
Prefill timings by layer, including attention, expert projections, weight/row
loading and cache loads. These diagnostic timings disable normal overlap and
must not be compared as throughput results. Normal runs also report host submit,
scratch reuse wait, final drain, Hot handoff and assembly wall times under
`prefill_report.layers[].timing`; submit time is not GPU execution time.
See [Hot handoff and profiling](../../docs/dsv41f-hot-direct-profile-2026-09-13.md).

### Experimental dense vision

`--image <local-path>` enables the original 32-layer BF16 ViT and aligner, kept
resident (970,536,960 weight bytes). Repeat the flag for multiple images; all
images precede the text question in one official chat-encoded user message.
`--vision-max-tokens 256|512|1024` sets the per-image span cap, including newline
and delimiter tokens. The actual span depends on image dimensions.

```sh
.venv/bin/python experiments/dsv41_mlx/run.py \
  --image artifacts/chat-checkpoint-migration-20260914/DeepSeek-V4.1-Flash-SSD/inference/examples/images/carrots.jpeg \
  --prompt '请简短说明图片里是什么食材。' \
  --vision-max-tokens 1024 --prefill-slots 64 --decode 32 \
  --output artifacts/<fresh-vision-output>
```

The visual tower is dense; image tokens still traverse the main MoE with the
original `bias_vl`. Image spans block Engram history and receive no Engram
contribution. Pixel normalization, 2D RoPE, non-causal vision attention, 3x3
channel-major unfold and aligner use the official layout. The MLX runner never
imports Torch; a separate CPU reference verifies the vision port.

Vision initially requires full Top6; Prefill/Decode Burst is rejected. Text-only
behavior and the 65 GB sampled footprint guard remain unchanged. This is a
single-sequence image experiment, not video, a serving engine or a validated
multiturn session path. Fixed-step benchmarks continue after EOS; assess the
first completion before EOS. Details and measurements:
[vision checkpoint](../../docs/dsv41f-vision-checkpoint-2026-09-13.md).

### Multi-turn history replay

`--messages-json <history.json> --stop-at-eos` accepts the full chronological
user/assistant message list using the official encoder. Historical local image
blocks are expanded in their original positions. Each CLI invocation recomputes
the complete history; it does not reuse KV from an earlier process. The flag is
exclusive with `--image` and `--prompt-json`. Without `--stop-at-eos`, fixed-step
benchmark behavior is preserved. Actual and requested Decode counts are recorded
separately in the manifest.

Nine text/image conversation turns passed the recorded semantic checks; repeated
final turns were logit-identical. A separate append-only KV diagnostic had 41/41
sampled Top1 agreement, but nonzero logit differences and max KL 0.104, so exact
KV reuse is not certified. New image spans still require full replay. See
[multi-turn validation](../../docs/dsv41f-multiturn-validation-2026-09-13.md).

## Decode dispatch experiments

`--decode-dispatch legacy` remains the default. `shared` reuses a single
route-sort plan across all three projections and shares gate/up activation
quantization. `unsorted` also shares that quantization but skips sorting for
small Decode requests. Neither changes Prefill dispatch. The 2026-09-14
2048/128 full-logits A/B passed, but neither candidate showed a meaningful
throughput benefit; see `docs/dsv41f-decode-dispatch-ab-2026-09-14.md`.

## Attention query grouping

`--attention-chunk {64,128,256}` controls Prefill query grouping, independently
of expert Prefill slots. The default remains 64. The 2048/128 experiment found
only about 1.3% mean Prefill improvement at 256 and no Decode benefit. Full-model
logits matched on that fixture, but a synthetic partial-group edge had a 4.8e-7
maximum absolute difference. See `docs/dsv41f-attention-profile-ab-2026-09-14.md`
for measurements and the separate synchronized attention/indexer profiler.

### Hot promotion reuse (2026-09-15)

Natural and Burst Decode now promote Hot-resident experts by native byte copy
inside the existing MLX bank. Only nonresident promotions read SSD. The current
lazy-consumer materialization and GPU synchronization fence remains in place;
expert maps are published after the copy/read operations complete. No full bank
is allocated or dequantized. This is unified-memory memcpy, not a CPU model
forward or a new Metal compute kernel.

Rebuild `artifacts/dsv41-native-build` with CMake before using this source. Missing
native copy support fails explicitly; it does not silently reread SSD. The
`--promotion-reread` flag is an explicit legacy diagnostic control. Copy counts,
bytes and seconds are recorded in `adaptive_l1.promotion_reuse`. Route diagnostics
record `copies` separately from `reads`; old frozen replay data retains its old
reread accounting. Use `experiments/dsv41_analysis/promotion_reuse.py` for the new
SSD/copy event comparison and `promotion_reuse_burst.py` for Burst checks.

See `docs/dsv41f-hot-promotion-reuse-2026-09-15.md` for exactness, saved SSD request
bytes, memory and measured throughput. No throughput gain is claimed from the
small validation batch, and this experimental extension is not a Runtime release.

### Adaptive L1 policies (2026-09-15)

`--l1-policy baseline|dual_fast75|probation32_8|eviction_dual` selects replacement policy.
All use the same expert bank, router, payload format, and default Hot promotion
memory reuse. The earlier periodic-policy comparison retained `baseline`: 12 paired runs improved
hits/SSD requests but did not improve TPS. The current default is `eviction_dual`
with zero-copy slot promotion, as described below. See `docs/dsv41f-l1-runtime-policies-2026-09-15.md`.

- `baseline`: existing 16-step frequency decay, at most four promotions/layer.
- `dual_fast75`: 8/64-token half-life frequencies, weighted 75%/25%; maintenance
  every eight tokens, at most four promotions/layer, score >=3 and advantage >2.
- `probation32_8`: same dual frequencies, eight trial slots within Main (32
  protected slots with Main40). Logical protection swaps do not copy payload.
  Only Hot experts observed at least twice in the last 32 committed routes may
  enter trial slots, with score >=3 and advantage >1. Every admission reuses Hot
  data in memory unless the diagnostic `--promotion-reread` flag is set.

Statistics update on GPU; maintenance transfers scores to the CPU every eight
steps for the new policies. Burst maintains before transactions and records only
committed routes. These policies do not predict routes or add an L2 cache.
Use Natural Decode for exact cross-policy logits checks: Burst's approximate
outputs can change when a different cache retains different tail experts.

### Eviction-only L1 promotion (2026-09-15)

Use `--l1-policy eviction_dual` for the new L0 eviction admission policy.
Explicit `--l1-policy baseline` selects the legacy-policy control on current code; the older
`dual_fast75`/`probation32_8` periodic policies are historical comparisons.

**Constraint: cache-policy maintenance must not introduce another GPU-to-CPU
readback or synchronization boundary.** Natural/Burst keep their existing hit
checks. Only on a miss, concatenate scores with the already required metadata
and use one readback instead of two/four. Admit only L0 experts actually being
evicted, exclude currently requested L1 victims, and copy before overwriting the
L0 source. Copy and native preadv share the existing miss fence. Do not call
`load_promotions` here: that would introduce a second fence. No all-hit host route
IDs, periodic score readbacks, or standalone promotion fences are added.

Eight paired runs had exact logits and fewer cache readbacks/fences in every
pair. Long Decode: 55,152→36,967 cache readback calls; 17,938→16,567 bank fences;
56.045 GB fewer expert requests; 4.859→4.823 TPS. This is a synchronization/I/O
reduction, not a demonstrated speedup. See
`docs/dsv41f-l1-eviction-promotion-2026-09-15.md`.

Packed float32 metadata rejects ages outside its exact integer range before
readback. `--promotion-reread` is incompatible with this policy; select baseline
explicitly for that legacy diagnostic. The checkpoint and expert-bank size do
not change.

### Zero-copy slot promotion (2026-09-15)

`--l1-policy eviction_dual` now defaults to zero-copy promotion. L0/L1 are logical
roles within the same six expert buffers. A promoted expert stays in its physical
slot; the new miss is loaded into the displaced L1 slot. GPU gather_qmm continues
to use physical-slot indices. A small GPU role mask replaces physical-range tests
for Main/Hot statistics, including pre-replacement Burst records.

No promotion memcpy, GPU copy dispatch, extra expert buffer, or additional
GPU-to-CPU synchronization is required. The existing miss fence still protects
the slot written by native preadv. Add `--promotion-copy` to reproduce the prior
same-policy memcpy variant. The overall L1-policy default is now `eviction_dual`.
Historical eviction benchmark scripts explicitly select `--promotion-copy`.
See `docs/dsv41f-zero-copy-promotion-2026-09-15.md` for paired results.

### Current default cache configuration (2026-09-15)

Standard Natural inference uses 40 L1 slots and 8 L0 slots per layer, with
`eviction_dual` short/long-frequency admission on L0 eviction and zero-copy
slot exchange. Native packet performs one GPU-to-CPU route decision per layer.
Fixed-layer expansion, predictive L2, Burst, and speculative blocks remain off.
Both the runner and direct AdaptiveModel construction select this policy.
Use `--l1-policy baseline` explicitly for the former policy; this does not restore
the archived old source. Historical unqualified benchmark commands must now add
that flag to retain their former policy. `--promotion-reread` also requires it.

This default reflects the selected memory/accuracy tradeoff, not a claim of a
universal TPS win. L0=12/16 raised hit rates but did not yield a clear throughput
benefit; see `docs/dsv41f-l0-capacity-2026-09-15.md`. The tested optimized Prefill
setting still requires `--prefill-slots 64`; its CLI default was not changed.
This is the frozen DS4.1F engine profile for the future Runtime/Package; no
published Runtime/Package contains it yet.


### Burst native windows (opt-in)

`--inference-mode window --burst-top 2 --resume-block 2` runs native Metal
speculative windows. The first required miss is repaired at its saved MoE;
subsequent invalid states are discarded, without replaying that layer's attention.
The original Burst zero-tail policy and SSD loader are preserved. This is a
performance experiment for high-hit text Decode; `packet` remains standard and explicit
`guarded` remains the GPU-stop research path. See
`docs/dsv41f-burst-window-optimization-2026-09-16.md` for full/tail TPS and limits.
