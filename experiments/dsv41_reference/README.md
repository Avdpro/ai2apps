# DS4.1 Flash SSD numerical reference

**Current pure-MLX text runner:** [../dsv41_mlx](../dsv41_mlx/README.md)
replaces the remaining CPU tensor forward, retaining SSD expert storage and
Main40/Hot8 caches. See its [measured checkpoint](../../docs/dsv41f-pure-mlx-checkpoint-2026-09-13.md).
The mixed implementations below remain historical comparison paths.

**Latest optimization direction:** normal floating-point differences are now permitted for native MLX exploration. See [native MLX checkpoint](../../docs/dsv41f-native-mlx-checkpoint-2026-09-13.md) for cached native MXFP8/MXFP4, SDPA, measured performance and numerical limitations. The CPU reference below remains unchanged.

`run_matrix_prefill.py --main-slots 40` is the latest text-only performance candidate under a 65 GB sampled process budget; its generated tokens match the gather comparison but logits differ. `run_device_moe.py --main-slots 40` is the matched gather path. `run_context_bounded.py` retains the earlier Main24/Hot8 comparison (Metal activation quantization and 2 GiB idle MLX pool limit). `run_native_owned.py` is the isolated single-owner weight experiment: it removes persistent CPU copies of migrated FP8 weights, head and grouped projection, while retaining the remaining CPU backbone and reduced-capture benchmark harness. See the checkpoint for validated artifacts and memory accounting.

This experiment imports the downloaded official `inference/model.py`, `engram.py`, and model configuration. It does not edit them. All 40 backbone layers execute during both Prefill and Decode. Original FP4 expert weights and FP8 Engram rows remain on SSD; no 2-bit conversion, expert pruning, bounded replay, cache replacement, MTP, or vision execution is used.

**Reference status:** on this Mac, this is the official model code with a **CPU translation of its TileLang kernels**. It is not an independently validated CUDA golden reference. CPU repeatability, storage-byte checks, and small operator tests cannot establish CUDA bitwise parity. The optional CUDA selection is untested and requires an appropriate CUDA/TileLang environment; the validated command below uses CPU.

## Run

From the repository root, with a fresh output directory:

```sh
.venv/bin/python experiments/dsv41_reference/test_reference.py
.venv/bin/python experiments/dsv41_reference/run_reference.py \
  --output artifacts/dsv41-reference-baseline-20260913 --decode 3
```

Default raw completion input is `The capital of France is`, tokenizer IDs `[671, 6102, 294, 8760, 344]`. No chat template is inserted. Greedy Prefill produces one token; three subsequent Decode forwards produce three more. Decode positions 5, 6, 7 cover both complete and incomplete ratio-2 compression groups. The context allocation is 256, batch size 1, CPU threads 4, BF16 default, and FP32 arithmetic at the locations specified by the official source. Config overrides and exact source hashes are recorded.

## Storage and numerical boundaries

- `Store` parses safetensors headers and uses bounded `pread` calls. Modules load their own parameters before forward and replace them with meta placeholders afterward. Only routed experts actually invoked by the official MoE loop are read.
- Token embeddings and Engram tables read only selected rows. Engram hashes and row dequantization match the official CPU operations. Repeated rows are intentionally not cached or deduplicated in this baseline.
- `wo_a` follows official `convert.py`: FP8 weights and block scales are expanded to BF16, then the official grouped einsum runs. The output head is promoted from BF16 to FP32, as specified by the official class.
- FP4 inputs retain packed low-nibble/high-nibble ordering. CPU GEMM accumulates scaled group-32 partial products in FP32 and returns BF16. It preserves activation FP8 quantization and router multiplication **before** the down projection.
- Sparse attention retains block-64 online softmax and BF16 probability rounding before the value product. Sinkhorn follows the official normalization order. CPU reduction/exp/GEMM implementations can still differ from CUDA.
- SSD bytes are logical `pread` bytes, not measured physical SSD traffic. OS file caching can serve those reads. RSS includes the whole process and transient allocations; it is not MLX active memory.
- The official shared-attention state behavior is preserved, including its source ownership behavior on partial compression steps. This experiment does not silently repair suspected upstream issues.

## Saved data

Each step saves:

- `NN_layers.L_input.pt`: layer input residual stream, position, incoming mHC mix and mask.
- `NN_layers.L.pt`: layer output residual stream and outgoing mHC mix.
- `NN_layers.L.attn.pt`, `.ffn.pt`: attention and MoE outputs.
- `NN_layers.L.ffn.gate.pt`: `(route_weights, expert_indices)` in official Top-6 order.
- Engram output and `(hash row IDs, dequantized row values)` on layers 1 and 14.
- `NN_logits.pt`, `NN_top10.pt`: full final-position logits and Top-10 IDs/scores.
- `NN_buffers.pt`, `NN_shared_attention.pt`: runtime buffers, Engram history and shared attention state. Tensor values are saved; alias identity is not serialized as a restoration contract.

`manifest.json` records completion/failure, config, input/output IDs, source hashes, trace-file hashes, timings, read counts, and peak RSS. The output directory is never overwritten. Files from a failed run are diagnostic only.

For a fresh-process repeat:

```sh
.venv/bin/python experiments/dsv41_reference/run_reference.py \
  --output artifacts/dsv41-reference-repeat-20260913 --decode 3
.venv/bin/python experiments/dsv41_reference/canonicalize_snapshots.py \
  artifacts/dsv41-reference-baseline-20260913 \
  artifacts/dsv41-reference-repeat-20260913
.venv/bin/python experiments/dsv41_reference/compare_traces.py \
  artifacts/dsv41-reference-baseline-20260913 \
  artifacts/dsv41-reference-repeat-20260913 \
  --output artifacts/dsv41-reference-repeat-comparison.json
```

The canonicalizer zeroes only the unwritten tail of the official `torch.empty` Engram cache in saved snapshots, preserving the first `prompt_length + decode_step` entries. It records before/after hashes and valid lengths in the manifest; it does not change execution or live state. Run it on both completed runs before comparison.

The comparison checks tensor metadata and raw tensor bits, including all layer results, routes, logits, and buffers. It deliberately compares contents rather than `.pt` container bytes. Kernel/source changes fail this repeatability check; use a separately reviewed tolerance-based comparator for future cross-backend validation.

This is a research-only experiment, not part of the Desktop runtime or its publication pipeline. The original model/license terms remain in the downloaded checkpoint directory.

## First storage optimization

`run_cached.py` injects `CachedStore` into the unchanged reference harness. Each layer retains at most eight **complete** routed experts, using LRU replacement; six original weight/scale tensors are loaded before publishing an expert record. CPU references keep any in-flight tensor alive across eviction. No GPU asynchronous lifetime guarantee is implied.

A separate 2 GiB admission-only dense cache avoids cyclic layer-order eviction, and an 8 MiB row LRU stores original embedding/Engram rows. Both preserve original bytes and the harness's dequantization. Cache payload caps exclude transient reads, parameter conversions, Python metadata, KV, activations and OS page cache. Eight experts per layer across 40 layers consume at most about 5.60 GiB, for about 7.61 GiB combined payload with the default dense/row budgets.

```sh
.venv/bin/python experiments/dsv41_reference/test_cached_store.py
.venv/bin/python experiments/dsv41_reference/run_cached.py \
  --output artifacts/dsv41-cached8-20260913 --decode 3 \
  --experts-per-layer 8 --dense-cache-mib 2048 --row-cache-mib 8
.venv/bin/python experiments/dsv41_reference/canonicalize_snapshots.py \
  artifacts/dsv41-cached8-20260913
.venv/bin/python experiments/dsv41_reference/compare_traces.py \
  artifacts/dsv41-reference-baseline-20260913 \
  artifacts/dsv41-cached8-20260913 \
  --output artifacts/dsv41-cached8-parity.json
```

The manifest additionally records cache configuration, actual payload bytes, read counters and the wrapper/store source hashes. `expert_hits` counts individual tensor reads served by a loaded expert record (including the other five segments of a newly loaded expert), **not** a per-token expert hit rate. `expert_misses` counts complete expert loads. Do not derive routing-cache hit rate directly from these two counters.

## Metal routed experts + native L0/L1 checkpoint

See `docs/dsv41f-metal-l0-l1-checkpoint-2026-09-13.md` for precision fixes, measured results and scope. This is a **hybrid CPU backbone / Metal routed-expert** replay, not a general chat engine. Each layer uses eight oracle-selected fixed L1 experts and six mutable L0 slots. The host router remains on CPU; device-only routing and asynchronous overlap are pending.

The native binding directly builds the existing GLM/Qwen `expert_loader.cpp` without editing or replacing the production extension:

```sh
cmake -S experiments/dsv41_reference/native -B artifacts/dsv41-native-build \
  -DPython_EXECUTABLE="$PWD/.venv/bin/python" -DCMAKE_BUILD_TYPE=Release
cmake --build artifacts/dsv41-native-build -j 4
```

The Metal commands require a session with GPU access (the agent filesystem sandbox did not expose Metal; GPU runs used approved execution outside that sandbox). Unit validation:

```sh
.venv/bin/python experiments/dsv41_reference/test_metal_path.py
```

Prepare compact fixtures from the existing baseline, using a fresh fixtures directory; this reads/writes about 18 GiB of expert records without changing their quantization:

```sh
mkdir -p artifacts/dsv41-metal-fixtures
for layer in {0..39}; do
  .venv/bin/python experiments/dsv41_reference/prepare_metal_fixture.py \
    --layer "$layer" --output "artifacts/dsv41-metal-fixtures/layer-$layer.bin"
done
```

Then run, normalize the unused snapshot tails, and compare:

```sh
.venv/bin/python experiments/dsv41_reference/run_metal_moe.py \
  --output artifacts/dsv41-metal-moe-silu-20260913 --decode 3
.venv/bin/python experiments/dsv41_reference/canonicalize_snapshots.py \
  artifacts/dsv41-metal-moe-silu-20260913
.venv/bin/python experiments/dsv41_reference/compare_traces.py \
  artifacts/dsv41-reference-baseline-20260913 \
  artifacts/dsv41-metal-moe-silu-20260913 \
  --output artifacts/dsv41-metal-moe-silu-parity.json
```

Existing fixtures/output directories must not be overwritten. The harness manifest's base `backend` identifies its CPU backbone; the supplemental `metal_moe` object records the hybrid override, native I/O, GPU time, device, and exact source hashes. Sum base CPU `read_bytes` and native `native_read_bytes` for total logical reads. Neither is a physical SSD cold-read measurement.

GPU SiLU uses a 256 KiB table generated once from the CPU reference across BF16 gate bit patterns. This preserves the CPU rounding exposed by full-model comparisons; CUDA SiLU parity is not implied. The initial sigmoid-expression version failed at layer 6 and is preserved only as diagnostic source/data.

## Strict inner FP8 GEMMs and complete expert storage

`run_metal_dense.py` additionally executes inner FP8 GEMMs on Metal. It retains every attention `wo_b` and shared-expert `w2` projection on CPU to preserve exact recorded sublayer boundaries. This rule applies to all layers. An initial all-FP8-Metal attempt had four one-BF16-step sublayer differences even though layer boundaries and logits matched; that attempt is diagnostic, not the strict default.

Prepare the complete 40-layer, 384-expert-per-layer layout once:

```sh
.venv/bin/python experiments/dsv41_reference/prepare_full_expert_store.py
```

This creates `artifacts/dsv41-full-expert-store/`, using **268.945 GiB** of additional disk. It preserves all original FP4/UE8M0 bytes, hashes while writing, fsyncs each layer and publishes it with metadata. Complete matching layers are skipped on repeat; inconsistent partial publication is rejected for inspection. The runtime validates source index identity, expert count and layer file sizes before admitting new prompts.

With this complete store, an arbitrary raw text prompt can use the current hybrid path:

```sh
.venv/bin/python experiments/dsv41_reference/run_metal_dense.py \
  --expert-store artifacts/dsv41-full-expert-store \
  --output artifacts/my-dsv41-run \
  --prompt 'The opposite of hot is' --decode 2
```

L1 still uses the same fixed eight-expert bootstrap selected from the original baseline Prefill; it is not retuned for the new prompt. L0 fetches any of the other experts through the original GLM/Qwen native loader. This removes the compact-fixture routing restriction, but does not imply long-context, chat-template, multi-session or full-MLX-engine validation. `--checkpoint` remains unsupported for alternate checkpoints in this prototype.

Additional GPU tests:

```sh
.venv/bin/python experiments/dsv41_reference/test_metal_dense.py
```

## Current checkpoint: ordered FP8 and bounded residency

Latest entry point: **`run_metal_batched_attention.py`**, extending the all-FP8 path below with 32-query CPU attention batching. It passes all three short CPU goldens and a 2048-token hybrid A/B (not an independent CPU golden at 2048). Measured 2048 Prefill fell from 347.3 s to 266.9 s (7.67 tokens/s), still below the 300 target. Short Decode is about 0.9 tokens/s, below 10. See `docs/dsv41f-2048-prefill-checkpoint-2026-09-13.md` for the current result, exact test scope and reproducible commands. Native MLX MXFP8 is diagnostic only because it still differs at rounding boundaries.

The underlying all-FP8 entry point is **`run_metal_cpu_order.py`**. It uses shape-dependent CPU-compatible FP8 reduction order (single-token GEMV differs from prefill GEMM), moves all ordinary FP8 projections onto Metal, and removes the CPU packed final-projection cache. It retains bounded ordinary CPU weight residency, L1=8/LRU L0=24 native expert slots and expert-grouped prefill. Three prompts (5, 5 and 26 tokens) pass complete bitwise CPU trace comparisons. The throughput targets remain **10 tokens/s Decode and 300 tokens/s Prefill at 2048 input tokens**, not yet achieved. See `docs/dsv41f-all-fp8-metal-cpu-order-2026-09-13.md` for that stage's measurements and commands; test with `test_metal_cpu_order.py`.

Earlier inner FP8 SIMD-tree kernels passed the two short prompts but failed the 26-token case; they are historical experiments, not a general strict-precision default. Compensated summation also failed the full case. Preserve matrix M/N when testing CPU rounding: collapsing a matrix into a scalar dot can change the CPU reduction.

See `docs/dsv41f-throughput-target-checkpoint-2026-09-13.md` for current commands, artifacts, memory, timing limits, and rejected experiments. `test_metal_ordered.py` covers two small real rounding fixtures (original DeepSeek license), finite FP8 codes and scales. The current route still uses CPU attention/router and host indices; it is not a full MLX engine.

## Strict packed CPU final projections

`run_metal_packed.py` extends the strict Metal path by arranging CPU final-projection weights as contiguous `[K/32,N,32]` before their group32 GEMMs. It retains the reference arithmetic sequence and does not persist the expanded weights between calls. L1/L0 and the native SSD loader are unchanged. Two short prompts passed bitwise trace comparisons; see `docs/dsv41f-packed-projection-2026-09-13.md` for timings and limits.

Use a fresh output directory:

```sh
.venv/bin/python experiments/dsv41_reference/test_packed_projection.py
.venv/bin/python experiments/dsv41_reference/run_metal_packed.py \
  --expert-store artifacts/dsv41-full-expert-store \
  --output artifacts/my-dsv41-packed-run --decode 3
.venv/bin/python experiments/dsv41_reference/canonicalize_snapshots.py \
  artifacts/my-dsv41-packed-run
.venv/bin/python experiments/dsv41_reference/compare_traces.py \
  artifacts/dsv41-reference-baseline-20260913 artifacts/my-dsv41-packed-run \
  --output artifacts/my-dsv41-packed-run/parity.json
```

For the second validated prompt, add `--prompt 'The opposite of hot is' --decode 2`, use a fresh directory, and compare against `artifacts/dsv41-reference-heldout-20260913`. The supplemental `packed_projection` manifest records pack/GEMM timings and exact source hashes.
