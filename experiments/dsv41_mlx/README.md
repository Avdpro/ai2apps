# DS4.1 Flash: independent MLX text forward

This research runner reads the original checkpoint and the existing native SSD
expert store. Its inference process does not import PyTorch. Attention, KV
compression, indexer, router, routed/shared experts, mHC, Engram hash and gating,
normalization, RoPE, and the output head execute as MLX/Metal tensor operations.
The original reference runner remains available for offline comparison.

CPU work remains for tokenization, file reads, sparse row addresses, expert cache
replacement metadata, and output serialization. An all-hit Decode layer only
returns a hit-status scalar; expert route IDs stay on the GPU. Dynamic L1 also
reads frequency metadata at its periodic maintenance boundary. Engram embedding
rows are read on demand from SSD, then dequantized on the GPU.

## Run

From the repository root, with the original downloaded checkpoint, complete
`artifacts/dsv41-full-expert-store`, and compiled native expert loader:

```sh
.venv/bin/python experiments/dsv41_mlx/run.py \
  --prompt-json artifacts/dsv41-benchmark2048-prompt.json \
  --decode 32 --output artifacts/my-pure-mlx-run
```

Output must be a new directory. `--decode 32` runs one Prefill and 32 single-token
Decode forwards, producing 33 greedy output tokens. EOS does not stop this fixed
benchmark. `--trace` saves intermediate layer tensors as safetensors; it is meant
for numerical investigation, not throughput measurements. `--gather-only`
disables the large-group Prefill matrix path.

L1/Main defaults to 40 experts per layer, initially chosen from that input's Prefill
route frequencies, with L0/Hot at 8 experts per layer. **Dynamic L1 is enabled by
default**: Decode frequency updates run on the GPU, and every 16 steps the policy
may replace up to four Main experts per layer, with frequency decay and hysteresis.
Use `--static-l1` to retain the initial Main selection for a comparison run.
Hot uses LRU replacement metadata. Both hold original packed expert bytes. Expert
reads reuse the GLM native loader through the existing Metal bank implementation.
No future generated routes are used to select Main.

The idle MLX allocator cache is capped at 2 GiB. The runner samples process
physical footprint every 20 ms and checks the 65 decimal GB budget at layer and
step boundaries. This is a sampled guard, not an instantaneous OS memory cap.
The receipt records checkpoint and source hashes, memory, timings, route/cache
counts, `l1_policy`, promotion details and `torch_imported: false`.
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
