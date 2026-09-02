# FLUX.2 Klein MLX

AI2Apps model package for local FLUX.2 Klein image generation and editing on
Apple silicon. The package contains no model weights. Installation prefers a
filtered ModelScope snapshot and then reconciles it against the immutable
Hugging Face revision recorded in `service.yaml`.

## Models

| Model ID | Operations | Quantization | Upstream terms |
| --- | --- | --- | --- |
| `ai2apps.model.flux2-klein-mlx/4b` | generation, edit (up to 4 references) | BF16, Q8, Q4 | Apache-2.0 |
| `ai2apps.model.flux2-klein-mlx/9b` | generation, edit (up to 4 references) | BF16, Q8, Q4 | FLUX non-commercial; gated upstream |

The package intentionally exposes both variants. AI2Apps reports the upstream
license metadata but does not make the user's deployment or commercial-use
decision.

## Runtime optimizations

- MLX-native transformer, text encoder, and VAE execution through mflux 0.19.0.
- Compiled denoiser graph supplied by the audited mflux FLUX.2 pipeline.
- Persistent compiled-denoiser callable reuse across regenerate requests.
- Q8 and Q4 weight-only execution in addition to BF16.
- Atomic, revision-keyed Q8/Q4 MLX checkpoint cache under the service data
  directory. The first quantized load materializes it once; later starts load
  the smaller native tree directly. Insufficient disk safely falls back to
  online quantization.
- Evaluated eight-entry prompt-embedding LRU cache for regenerate/edit loops.
- FLUX.2 edit transformer KV cache, enabled by default.
- Experimental Apple-Metal-only LayerNorm/AdaLN and gated-residual/LayerNorm
  kernels. They remain disabled by default because full-pipeline A/B did not
  outperform MLX's compiled graph. Developers can set
  `AI2APPS_FLUX2_METAL_FUSIONS=1`; activation is reported through
  `metal_fusions_enabled`. CUDA and CPU always keep the original mflux graph.
- One in-flight generation per device to prevent unified-memory overcommit.

Runtime requirement: `ai2apps.runtime.omlx >=1.5.0,<2.0.0`.
Q8 is the default execution mode; callers may explicitly select `bf16` or
`q4` when quality or memory constraints call for a different tradeoff.

## Benchmark

The reproducible MLX and CUDA comparison harness is in `benchmarks/flux2` at
the repository root. It fixes prompts, seeds, dimensions, inference steps, and
reports cold/steady latency plus peak accelerator memory. See
`docs/ai2apps-mlx-runtime-1.5-flux2-implementation.md` for the latest receipt.
