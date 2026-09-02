# Ideogram 4 MLX implementation and optimization log

Date: 2026-08-26

## Status

The native MLX text-to-image and single-reference Remix/Img2Img paths are
correct and reproducible on the M5 Max 40-core GPU. Spark was deliberately not
used because its two existing downloads must not be disturbed. The optimized
pipeline is now packaged as the AI2Apps Model Worker
`ai2apps/model-ideogram4-mlx` 0.1.0; publication remains a separate release
step.

## Locked sources

- Official code: `ideogram-oss/ideogram4` commit
  `990fe1c4e950bb9e9dc90e01c0ad98ba434f83c2`.
- ModelScope weights: `Comfy-Org/Ideogram-4`, FP8 conditional transformer,
  unconditional transformer, Qwen3-VL encoder, and Flux 2 VAE.
- ModelScope tokenizer/config: `Qwen/Qwen3-VL-8B-Instruct`.
- Downloaded source size: approximately 28 GB.
- The Ideogram checkpoint remains subject to the upstream Ideogram 4 model
  agreement. AI2Apps exposes model choice and does not make the user's usage
  decision on their behalf.

## Native implementation

The baseline under `benchmarks/ideogram4` implements:

- the 34-layer, 4,608-wide single-stream diffusion transformer;
- QK RMSNorm, MRoPE, SwiGLU, AdaLN, and the final adaptive layer;
- Qwen3-VL-8B text-only inference with 13 intermediate activation taps;
- asymmetric conditional/unconditional classifier-free guidance;
- the official logit-normal Euler sampler and Turbo 12-step schedule;
- exact Ideogram `[patch_y, patch_x, channel]` latent unpatching;
- the exact inverse latent packing plus Flux 2 VAE input-image encoding;
- strength-controlled SDEdit/Remix initialization and partial denoising;
- strict mapping of all 250 Flux 2 VAE parameters;
- dependency-free E4M3FN decoding and native MLX Q8/Q4 conversion.

The role-aware input projection is the first accepted optimization. It applies
the 53,248-to-4,608 text projection only to actual text tokens rather than also
projecting thousands of masked image rows. This is algebraically equivalent to
the reference implementation, including projection bias behavior.

The second accepted optimization is a staged model lifecycle. The Qwen3-VL
text encoder is loaded only for prompt encoding and is synchronized and
released before the conditional transformer, unconditional transformer, and
VAE are loaded. Repeated generations unload the prior generation stage before
encoding the next prompt, so the memory saving is preserved beyond the first
request.

## Correctness gates

- Small official PyTorch versus MLX transformer:
  - cosine similarity: `0.99999994`;
  - maximum absolute error: `0.00150`.
- Actual 9.3B unconditional FP8 versus converted MLX Q8, one image token:
  - cosine similarity: `0.999913`;
  - mean absolute error: `0.0117`.
- Official PyTorch versus MLX VAE on an identical latent:
  - cosine similarity: `0.999994`;
  - mean absolute error: `0.000591`.
- MLX unit tests: `10/10` passed.
- The fixed structured-prompt image preserves the requested headline, layout,
  palette, and geometric element at both 256 and 512 pixels.

Two integration defects were found and fixed during the gate:

1. The ModelScope VAE uses Ideogram's module paths rather than the mflux
   Diffusers paths. A strict 250-parameter mapping now prevents random fallback
   layers.
2. Ideogram packs each latent token as `[patch_y, patch_x, channel]`; reusing the
   Flux 2 channel-first unpatch created periodic grid artifacts. The MLX path now
   follows the official reshape/transpose order exactly.

## Remix / Img2Img gate

The local Remix path accepts one PNG/JPEG/WebP image and a strength in `(0, 1]`.
It VAE-encodes the resized source, adds scheduler-consistent noise at the chosen
start time, and executes only `ceil(steps * strength)` denoising steps. All
accepted denoiser optimizations are reused unchanged: Q4 weights, BF16 MLP and
SDPA boundaries, fused QK RMSNorm/MRoPE, prepared static conditioning, staged
residency, and optional compiled denoisers.

At 512x512 Q4 Quality settings:

| Strength | Effective steps | VAE encode | Denoise | Result |
| ---: | ---: | ---: | ---: | --- |
| 0.55 | 7/12 | 0.318 s cold | 6.288 s | conservative structure-preserving remix |
| 0.85 | 11/12 | 0.135 s warm | 9.871 s | red circle changed to blue; requested headline/composition reworked |

Peak memory remained approximately 15.81 GB. This is a generic local SDEdit
implementation using the public Ideogram 4 weights, not a claim of bit-for-bit
or feature parity with Ideogram's hosted v4 Remix API. Masked inpainting and
the hosted API's private editing behavior are not exposed by the public model.

## Model Worker MVP

The package under `packages/ai2apps-model-ideogram4-mlx` exposes
`image_generation` and `image_edit` through `ai2apps-model-worker/v1`. It is
not a wrapper around an unoptimized upstream pipeline: the Worker vendors the
same native implementation and enables Q4 group-64 weights, staged residency,
BF16 MLP and SDPA boundaries, prepared static conditioning, and fused QK
RMSNorm/MRoPE by default. Full denoiser compilation remains opt-in because it
changes the floating-point trajectory slightly.

The Host downloads the exact four files from `Comfy-Org/Ideogram-4` at commit
`bbee2ab2b14b2b5223448d12d6e31e5f9cec0546`. On first use the Worker converts
them atomically into a revision-keyed Q4 cache under its private data root.
Conversion uses an exclusive lock, checks free disk space, and never mutates
the Host checkpoint. Qwen tokenizer/config metadata is bundled at commit
`0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`. MLX Runtime 1.5.2 supplies the
locked mflux 0.19 Flux 2 VAE implementation.

The edit input is one verified PNG/JPEG/WebP data URL, at most 25 MB and 64
megapixels. MVP geometry is 256-2048 pixels per side in multiples of 16;
Quality defaults to 12 steps. Responses contain OpenAI-compatible `b64_json`,
the AI2Apps image result, and an optimization/timing receipt.

A real request through `Ideogram4Adapter.invoke`, using the already validated
Q4 cache and the default non-compiled quality path, measured at 512x512 and
strength 0.85:

| Stage | Result |
| --- | ---: |
| Effective denoise steps | 11/12 |
| Source VAE encode | 0.134 s |
| Denoise | 9.964 s |
| Decode | 0.199 s |
| MLX peak memory | 15.812 GB |

The package has six dedicated contract/security tests; the broader Ideogram
and shared image-capability suite adds sixteen tests. All 22 pass on the real
Metal test environment. The reproducible smoke entry point is
`packages/ai2apps-model-ideogram4-mlx/scripts/smoke_worker.py`.

The local-development artifact is
`packages/ai2apps-model-ideogram4-mlx/dist/ai2apps.model.ideogram4-mlx-0.1.0-development.ai2service`.
Its archive SHA-256 is
`09937d8b437d1c65b8deb1f1ecff0118b6a8503e55d48cba81d4355a3dc80808`;
the signed package-content digest is
`sha256:c1dcef0030fccb5e57d935eeccc5c672f546bcfe29beaff57a12716fa2965b8c`.
The current signature is an ephemeral development signature, not a production
publisher release.

## Current M5 Max baseline

All rows use the same structured JSON caption, seed `20260603`, and official
Turbo 12-step sampler. Timings include denoising and list VAE decode separately.

| Precision | Resolution | Denoise | Decode | Peak memory | Static derived weights |
| --- | ---: | ---: | ---: | ---: | ---: |
| Q8 | 256x256 | 5.25 s | 0.084 s | 31.8 GB | 28.7 GB |
| Q8 | 512x512 | 16.99 s | 0.255 s | 33.7 GB | 28.7 GB |
| Q4 | 256x256 | 4.81 s | 0.077 s | 19.1 GB | 15.9 GB |
| Q4 | 512x512 | 17.33 s | 0.294 s | 21.0 GB | 15.9 GB |

After enabling staged residency, the same Q4 512x512 job measured:

- denoise: `16.20 s`;
- decode: `0.251 s`;
- peak memory: `15.81 GB`, down `5.15 GB` or `24.6%`;
- active memory after generation: `10.94 GB`, down `5.15 GB`;
- all lifecycle transitions and model loads: approximately `0.70 s` total.

The staged and eager output PNG files have the same SHA-256
`9dd4f9d32297e4c6198da1284e2933d573a91b4467a7e8dbe0ed7375775f9dac`.
The optimization is therefore output-preserving for the locked baseline.

Static conditioning is now also prepared once outside the sampler: the wide
text projection, MRoPE values, indicator embedding, and segment policy are no
longer rebuilt on every DiT call. Because generation uses one uniform segment,
the all-zero 1,235-by-1,235 attention mask is omitted and MLX can select its
unmasked SDPA path. The locked Q4 512x512 Quality run is byte-identical and now
measures `15.62 s` denoise plus `0.256 s` decode, a cumulative `9.9%` denoise
improvement from the original `17.33 s` Q4 baseline.

MLX fast kernels are now used for all RMSNorm and final LayerNorm operations.
The attention path already used MLX's fused scaled dot-product attention. A
model-specific `mlx.fast.metal_kernel` now fuses Q/K RMSNorm, transpose, and
Ideogram's half-rotation three-axis MRoPE into one write. At sequence length
1,235 the fused QK+MRoPE stage measures `0.352 ms` versus `1.262 ms`; cosine
similarity is at least `0.99999994`. Full attention improves from `7.90 ms` to
`7.11 ms` and the representative block from `19.65 ms` to `18.86 ms`.

The accepted Q4 512x512 Quality result is now `14.77 s` denoise plus `0.261 s`
decode, a cumulative `14.8%` improvement from the original `17.33 s` denoise
baseline. Peak memory remains `15.85 GB`. The corresponding 8-step Fast result
is `10.25 s` denoise plus `0.265 s` decode.

The Q4 MLP now casts only its projection activations to BF16 and restores the
surrounding residual stream to FP32. The stored Q4 scales and biases were
already BF16, so this lets MLX's M5 NAX path use native BF16 matrix arithmetic
without changing attention, residual accumulation, or final output precision.
At sequence length 1,235, the three MLP projections improve from a combined
`10.64 ms` to `8.29 ms`; the actual MLP measures `8.96 ms` and a full block
`16.88 ms`.

On the locked 211-token structured prompt, the 512x512 Quality result is now
`12.18 s` denoise plus `0.253 s` decode. This is 17.5% faster than the prior
`14.77 s` accepted result and 29.7% faster than the original `17.33 s`
baseline. Peak memory is unchanged at `15.85 GB`. Against the prior fixed-seed
PNG, pixel MAE is `1.23/255`, PSNR is `31.23 dB`, and 95.5% of channel values
change by no more than two levels; the requested typography, composition, and
palette are visually unchanged. The corresponding 8-step Fast result improves
from `10.25 s` to `7.99 s` denoise, with `0.253 s` decode.

Q4 attention now also casts only Q/K/V at the SDPA boundary to BF16 and restores
FP32 before the output projection. QKV projection, Q/K RMSNorm and MRoPE,
softmax, output projection, and the residual stream retain their prior
precision; MLX itself evaluates SDPA softmax in FP32. The complete locked
Quality run improves again from `12.18 s` to `11.81 s`, or 3.1%. This is a
cumulative 31.9% denoise reduction from the original `17.33 s`. The locked PNG
has `1.11/255` MAE and `32.32 dB` PSNR against the original FP32-activation
sample. Peak memory remains `15.85 GB`. Fast 8-step improves from `7.99 s` to
`7.67 s`, a cumulative 25.2% reduction from its prior `10.25 s` result.

The 8-step schedule remains a separate Fast quality tier rather than an
output-preserving speed optimization. The 12-step schedule remains the Quality
default.

Compiling both full denoiser branches remains disabled by default, but is now
available as an explicit benchmark/runtime experiment through
`--compile-denoisers`. On a same-process two-generation 512x512 Q4 run, the
compiled path reduced denoising from `11.16 s` to `10.65 s` on the first image
and from `12.66 s` to `12.04 s` on the thermally throttled second image, a
repeatable `4.6-4.9%` gain at the same thermal stage. Compilation changes the
floating-point trajectory: against eager, the fixed-seed image measured
`1.21/255` pixel MAE, `34.77 dB` PSNR, and `98.0%` of channel values within two
levels. The composition and text placement were visually unchanged. This is a
candidate for an opt-in resident Turbo tier, not the Quality default.

The repeated-run benchmark also exposed sustained-load thermal behavior on the
M5 Max. With staged model reloads, the second eager image increased from
`11.16 s` to `12.66 s`; compiled increased from `10.65 s` to `12.04 s`. Runtime
throughput claims must therefore compare equivalent request positions or
control device temperature rather than mixing cold and sustained runs.

## M5 Max denoiser profiling

At the real 512x512 sequence length of 1,235, one representative Q4 layer
measured:

| Operation | Median |
| --- | ---: |
| QKV projection | 4.20 ms |
| Full attention | 7.35 ms |
| SwiGLU MLP | 9.04 ms |
| Full transformer block | 16.73 ms |

Q8 measured 20.86 ms per block, only 2.7% behind Q4. Q4 therefore acts mainly
as a memory tier in the current MLX kernel rather than delivering proportional
low-bit compute throughput. Group sizes 32, 64, and 128 were within roughly 1%
at Ideogram's fixed projection shapes. MXFP4 and NVFP4 also had no speed
advantage over affine Q4 and produced larger projection error.

The following experiments were rejected rather than shipped:

- concatenating the SwiGLU gate/up projections was numerically exact but had
  effectively zero speed benefit;
- independent Metal streams for conditional and unconditional CFG increased
  denoise time to 16.86 seconds and changed the numerical trajectory;
- full BF16 DiTs used 42.5 GB peak memory and took 17.30 seconds;
- globally changing all DiT activations to BF16 improved a hot Q4 block but the
  complete two-model run took 16.06 seconds; only the MLP-local BF16 path is
  retained;
- an isolated MLX 0.32.0 source build using a 128-row NAX QMM tile measured
  `10.65 ms` across the three real MLP projections versus `10.64 ms` for the
  upstream 64-row tile, so the runtime kernel dispatch remains unchanged;
- a cross-layer parameterized `mx.compile` MLP graph saved only about 1%, and a
  batched gate/up NAX dispatch was 1.2% slower; neither is enabled;
- an isolated MLX native dual-QMM SwiGLU primitive was tested with simultaneous
  and sequential accumulators. The correct sequential implementation reached
  cosine similarity `0.9999948`, but saved only about 1% across the complete
  MLP in a stable 25-run test. It does not justify a maintained MLX fork;
- an Ideogram-specific BM96 Q4 NAX tile used six compute simdgroups and a
  corrected 128-thread weight loader. It improved a hot single-layer MLP from
  `8.34 ms` to `8.09 ms`, but the strict same-binary full denoiser gate regressed
  from `10.707 s` to `10.838 s`. BN128 and BK32 were also slower, while BK128 is
  incompatible with the current group-64 loader. The upstream BM64/BK64 tile
  remains selected;
- MLX 0.32.0 full fused SDPA does not support Ideogram's head dimension 256.
  An isolated NAX BD=256 extension reduced attention scratch memory by 3-5x,
  but was 2.2x, 3.2x, and 3.7x slower at 1,235, 2,048, and 4,096 tokens. The
  upstream fallback remains faster, with BF16 used only at its SDPA boundary.

The next kernel stage must benchmark complete-model streaming rather than hot
single-layer loops. Since a larger generic NAX tile did not help, the next
plausible target is a model-specific fused gate/up QMM plus SwiGLU epilogue that
avoids materializing both 12,288-wide projection outputs.

Q4 is currently the memory tier: it cuts peak memory by about 40% at 256 and
37.8% at 512 while preserving the main typography and composition. It is not a
consistent speed tier yet; at 512 it is approximately 2% slower than Q8.

## Next optimization gates

1. Profile the 512 and 1024 token regimes, especially attention, QKV projection,
   SwiGLU, and per-step synchronization.
2. Evaluate protected mixed Q4/Q8 layers for small typography and multilingual
   OCR rather than accepting Q4 from one poster.
3. Add the AI2Apps Model Worker package, source lock, capability manifest, and
   clean install smoke.
4. Add Spark parity only after the existing Spark downloads are complete.
