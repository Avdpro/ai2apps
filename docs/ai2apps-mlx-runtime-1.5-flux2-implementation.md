# MLX Runtime 1.5.1 and FLUX.2 Klein implementation

Status: development build; not production-signed or published.

Further optimization is frozen after 0.1.2. The restart criteria and prioritized
roadmap are recorded in `docs/ai2apps-flux2-mlx-next-optimization-plan.md`.

## Scope

MLX Runtime 1.5.1 adds a versioned image-model contract and an MLX-only FLUX.2
execution layer. The first model package exposes FLUX.2 Klein 4B and 9B for
text-to-image, image-to-image, and multi-reference editing.

The image contract is `ai2apps.image-capabilities/v1`. It declares operations,
input/output formats, geometry limits, defaults, quantization modes, compiled
denoising, edit KV caching, and per-device concurrency. Older image packages
without this object continue to receive conservative defaults.

## Runtime changes

- Runtime version: `1.5.1`.
- Bundled mflux: `0.19.0`, wheel SHA-256
  `3214044d36dc9e3a371f40ac5206f4449974ad57bc7bd3763385c8ed5abf5e47`.
- Removed PyTorch and `safetensors.torch` imports from the packaged inference
  path. PyTorch checkpoint conversion fails explicitly instead of pulling a
  second tensor runtime into the package.
- PiD decode is imported lazily and is outside the default generation path.
- Runtime capabilities: `image-generation`, `image-edit`, `flux2-klein`.

## Weight acquisition

Native checkpoint installation uses this order:

1. Download only the required VAE, transformer, text encoder, tokenizer, and
   model-index files from ModelScope when its mirror is marked preferred.
2. Reconcile the local tree with the immutable Hugging Face commit recorded by
   the model package.
3. Import the checkpoint into the AI2Apps content-addressed store only after
   the pinned tree is complete; otherwise fall back to the normal pinned
   Hugging Face path.

ModelScope uses parallel ranged downloads for files above 256 MiB. A
ModelScope branch name is a transport hint, never the trust anchor.

## Model package

Package ID: `ai2apps.model.flux2-klein-mlx`, version `0.1.2`.

- 4B upstream commit: `e7b7dc27f91deacad38e78976d1f2b499d76a294`.
- 9B upstream commit: `92196c8e11f7b6cf2b7493e037d8c5345c559216`.
- Execution modes: BF16, Q8, Q4.
- Default generation: 1024 x 1024, four steps, guidance 1.0.
- Editing: up to four reference images with transformer KV caching.
- Optimization: a persistent compiled-denoiser callable, an evaluated
  eight-entry prompt-embedding LRU cache shared by generation and editing,
  and atomic revision-keyed native Q8/Q4 checkpoint caching. Derived weights
  live in the service data directory and are never written into the pinned
  source checkpoint.
- The package contains an experimental Apple Metal LayerNorm/AdaLN and gated
  residual/LayerNorm/AdaLN path. It is disabled by default after full-pipeline
  A/B showed no gain over MLX's already-compiled graph; CUDA/CPU are untouched.
- The optimized edit pipeline uses a private model-config copy to activate
  mflux's existing FLUX.2 extract/cached KV implementation. This avoids MLX
  compiling Python cache objects and leaves mflux's shared configs untouched.

The catalog surfaces upstream license and gating metadata but does not block a
user from choosing or installing the 9B package.

## Spark parity protocol

The comparison uses one DGX Spark and preserves the running MiniMax H3 service.
The harness under `benchmarks/flux2` records:

- identical prompts, seeds, dimensions, four denoising steps, and guidance;
- MLX upstream-mflux baseline versus the AI2Apps optimized MLX pipeline;
- Q8/Q4 and BF16 where available;
- Diffusers BF16 on CUDA as the numerical reference;
- load time, cold generation, steady generation, and peak memory;
- CLIP ViT-L/14 prompt alignment plus a human-review contact sheet.

### Benchmark receipt

Spark: NVIDIA GB10, 119 GiB unified memory. MLX and `mlx-cuda-13` were both
upgraded to 0.32.0. MLX 0.31.1 failed FLUX Q4/Q8 because its CUDA backend had no
quantized-matmul implementation for a required shape; 0.32.0 fixed that issue.

4B, 1024 x 1024, four steps, fixed four-prompt suite:

| Backend | Steady median | Peak accelerator memory | Load time |
| --- | ---: | ---: | ---: |
| AI2Apps optimized MLX Q8, native cached weights | 8.358 s | 12.42 GiB | 1.055 s |
| AI2Apps optimized MLX Q8, online-quantized weights | 8.757 s | 15.80 GiB | 0.870 s |
| upstream mflux MLX Q8 | 10.141 s | 15.78 GiB | 0.865 s |
| Diffusers CUDA BF16 | 3.356 s | 17.32 GiB | 84.167 s |

Retaining mflux's compiled denoiser callable across requests reduces the
online-quantized steady median from 9.941 s to 8.757 s (11.9%). Loading the
one-time native Q8 derived checkpoint reduces it again to 8.358 s and lowers
peak memory from 15.80 GiB to 12.42 GiB. Combined, this is 15.9% faster and
21.4% lower peak memory than the first AI2Apps implementation, or 17.6% faster
than upstream mflux. CUDA BF16 remains 2.49x faster in steady generation on
this Spark, while MLX retains much lower process startup/load latency.

The native cached Q8 quality rerun scored 0.3455 CLIP ViT-L/14 mean prompt
alignment versus 0.3593 for Diffusers BF16 (0.0137 absolute / 3.8% relative
gap), so the storage optimization introduces no measured quality regression.
The earlier online-quantized run scored 0.3366. MLX CUDA output is not
pixel-deterministic for a fixed seed on this Spark, so the difference between
the two Q8 scores is treated as run variance, not a claimed quality gain. The
layout prompt remains the largest gap because small poster text is fragile.

Machine receipts are stored on Spark under `$HOME/flux2-bench/results/4b`,
including `mlx-prequantized-predict-cache-q8-1024` and
`quality-prequantized-vs-bf16`.

The product adapter itself was also exercised, rather than only the benchmark
pipeline. Its first 4B Q8 load, materialization, atomic commit, and native
reload took 11.608 s and produced an 8,569,653,128-byte derived tree. A fresh
adapter then loaded that tree in 0.634 s. The cached edit adapter loaded in
0.616 s; one-reference 1024 x 1024 four-step editing took 12.067 s with KV
reuse, while the paired text generation took 8.022 s.

### 9B benchmark receipt

The filtered ModelScope snapshot completed at 33 GB. The downloader now
validates every shard named by the transformer and text-encoder indexes before
writing its success receipt; this caught and resumed one partial-success CDN
download that ModelScope had otherwise returned without raising.

9B, 1024 x 1024, four steps, fixed four-prompt suite:

| Backend | Steady median | Peak accelerator memory | Load time |
| --- | ---: | ---: | ---: |
| AI2Apps optimized MLX Q8, native cached weights | 19.691 s | 20.27 GiB | 1.689 s |
| upstream mflux MLX Q8, native cached weights | 19.838 s | 20.24 GiB | 1.104 s |
| Diffusers CUDA BF16 | 6.255 s | 34.74 GiB | 169.963 s |

The one-time product-adapter Q8 conversion, atomic commit, and native reload
took 29.523 s and produced a 17,865,574,861-byte derived tree. A fresh product
adapter loaded it in 0.718 s. Its direct four-step generation took 20.109 s;
one-reference editing with KV reuse took 29.921 s and loaded in 0.769 s.

CUDA BF16 is 3.15x faster for steady generation on Spark, while MLX Q8 uses
41.6% less peak accelerator memory. The native MLX benchmark process loads
about 101x faster than the Diffusers BF16 reference process; the product
adapter's cached restart is faster again at 0.718 s.

At 9B scale, persistent callable and prompt reuse improve the aggregate steady
median by 0.7% versus upstream mflux. One upstream repeat emitted non-finite
VAE output and its saved `people` image was completely black; none of the 12
optimized generations did. Because MLX CUDA is not fixed-seed deterministic,
this is recorded as a backend numerical-stability event rather than evidence
that the optimization has eliminated the underlying issue.

CLIP ViT-L/14 mean prompt alignment was 0.3501 for MLX Q8 and 0.3632 for CUDA
BF16, an absolute gap of 0.0131 (3.6% relative). Manual review found correct
`AI2APPS` product-card text on both, competitive people composition, and a
cleaner complete `18 OCT` line in the MLX poster. Both backends still produce
pseudo-text in the dense architectural labels; no Q8-specific structural
failure was observed. Receipts are under `$HOME/flux2-bench/results/9b` in
`product-cache-v011`, `mlx-prequantized-predict-cache-q8-1024`,
`diffusers-bf16-1024`, and `quality-mlx-q8-vs-bf16`.

The follow-up precision controls isolate the Spark performance gap:

| MLX 9B configuration | Steady median | Denoiser median | Memory observation |
| --- | ---: | ---: | --- |
| BF16 all components | 8.457 s | 7.636 s | 33.25 GiB peak |
| Transformer BF16; text encoder/VAE Q8 | 8.170 s | 7.349 s | 28.16 GiB online-conversion peak |
| double blocks Q8; remaining transformer BF16; text encoder/VAE Q8 | 10.960 s | 10.125 s | 22.78 GiB resident after inference |
| first 12 single blocks Q8; remaining transformer BF16; text encoder/VAE Q8 | 12.613 s | 11.789 s | online-conversion peak includes BF16 source weights |
| Transformer Q8; text encoder/VAE BF16 | 19.279 s | 18.400 s | 33.25 GiB peak |
| Q8 all components, native cached weights | 19.691 s | 18.895 s | 20.27 GiB peak |

MLX BF16 is only 1.35x slower than Diffusers CUDA BF16 on GB10; whole-model
MLX Q8 is 2.33x slower than MLX BF16. The principal Spark bottleneck is thus
the CUDA quantized Transformer GEMM path, not the denoiser's normalization or
SDPA orchestration. Equal-parameter experiments also show that quantizing the
eight double blocks is substantially faster than quantizing half of the 24
single blocks. These mixed configurations are benchmark candidates, not yet
public request modes; Q8 remains the memory-safe product default.

On an Apple M5 Max with 128 GB unified memory, the standalone fused kernels
were tested at the representative
`[1, 4352, 4096]` BF16 shape. LayerNorm + AdaLN measured 2.10x faster and gated
residual + LayerNorm + AdaLN 1.70x faster than their unfused MLX expressions.
The residual was bit-exact; normalized output had 0.00187 mean absolute error.
A real mflux block A/B measured maximum/mean output error 0.0077/0.00075 for a
double block and 0.00028/0.000018 for a single block. A reduced-width complete
8-double + 24-single Transformer measured final maximum/mean error
0.000144/0.0000254 against a reference mean absolute output of 0.45.

The required full-image control used a locally ModelScope-validated 4B Q8
checkpoint, 1024 x 1024, four steps, and an identical prompt/seed. With the
custom fusions disabled, steady generation/denoising measured 3.887/3.479 s;
enabled measured 3.955/3.543 s, about 1.7-1.8% slower. The generated images had
RGB pixel MAE 0.692/255 and RMSE 1.576/255. A longer run encountered progressive
thermal throttling but preserved the same no-win result in its comparable
early samples. The microkernels are therefore retained only behind
`AI2APPS_FLUX2_METAL_FUSIONS=1`; the product default remains the compiled mflux
graph.

Apple 4B mixed-precision controls (same image settings, Metal fusions off)
measured 3.469 s for a BF16 Transformer with Q8 text encoder/VAE, and 3.577 s
when the double blocks plus text encoder/VAE were Q8. Against the 3.887 s
whole-model Q8 control, these are 10.8% and 8.0% faster respectively. The
balanced double-block image was visually indistinguishable in manual review;
its RGB pixel MAE versus whole-model Q8 was 1.277/255. These results support a
future prequantized high-performance profile, while whole-model Q8 remains the
current memory-safe public mode.

## Verification

The FLUX package tests pass 5/5. The broader provider file passes 33/34; its
remaining registry-envelope fixture fails on a missing `publisherKeyId` in the
current shared worktree and does not execute the FLUX package or Metal path.
The Apple Metal kernel, block, complete reduced-width Transformer, and edit
modulation-shape checks all pass.

Development artifact:
`ai2apps.model.flux2-klein-mlx-0.1.2-development.ai2service`.
File SHA-256:
`c44e97d24f27d2790a140c117abe86252e559f01bf94ab39fa0ea3cd48fd7e2e`.
Package digest:
`sha256:68029cba7a8fca2a602aa8ea62055ede096caa6160df24e8265574c02e8974f4`.

Production publication requires the signing/promotion procedure in
`docs/ai2apps-package-publication-runbook.md` and is not part of this work.
