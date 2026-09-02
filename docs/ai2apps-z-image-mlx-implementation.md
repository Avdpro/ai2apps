# Z-Image MLX implementation and optimization receipt

Date: 2026-08-26

## Scope

- First model: `Tongyi-MAI/Z-Image-Turbo`
- Source mirror: ModelScope `master`, with Hugging Face identity pinned to
  `f332072aa78be7aecdf3ee76d5c247082da564a6`
- Runtime graph: mflux 0.19.0 on MLX 0.32.0
- Default sampler: eight steps, no external CFG
- Planned second variant: `Tongyi-MAI/Z-Image` base

The 19 MLX-required files were downloaded from ModelScope and shard-validated.
The resulting source tree occupies 31 GB.

## Runtime compatibility fixes

The clean torch-free Runtime exposed two eager optional-import defects in the
upstream Z-Image package:

1. importing text-to-image eagerly imported the OpenCV-backed ControlNet stack;
2. importing Z-Image eagerly imported the torch-backed optional PiD converter.

Runtime source now loads both paths only when the caller explicitly requests
ControlNet or PiD. Normal generation therefore remains free of torch and OpenCV.
This patch is tracked as `mlx-only-v3` and requires the next Runtime build
(planned 1.5.2) before the Z-Image package can ship.

## Persistent quantized checkpoints

Online Q8 loading is not an acceptable production path. Its first inference
retains source weights, lazy quantization graphs and activations together. A
native mflux Q8 save is 10 GB and reloads without the source graph. Fixed-seed
Q8 source and native-checkpoint outputs were pixel-identical in both baseline
cases.

| Checkpoint / mode | Geometry | Steady request | Peak MLX memory | Active after request |
| --- | ---: | ---: | ---: | ---: |
| online Q8 source | 512² / 8 | 5.04 s | 31.59 GB | not recorded |
| native Q8 | 512² / 8 | 3.81 s | 13.51 GB | 4.27 GB |
| native Q4 | 512² / 8 | 3.81 s | 8.47 GB | 2.31 GB |
| native Q8, cold | 1024² / 8 | 17.54 s | 17.95 GB | 4.27 GB |
| native Q4, cold | 1024² / 8 | 17.11 s | 12.91 GB | 2.31 GB |

At 512², native Q8 reduces peak memory by 57.2% and request time by 24.4%
relative to online Q8. At 1024², Q4 lowers peak by another 28.1%. Cold Q4 is
only 2.4% faster than cold Q8, but its second sustained run reached 18.53 s
while Q8 reached 30.53 s under thermal pressure. Q4 is therefore useful for
both 16 GB compatibility and sustained generation.

Product policy:

- Q8 remains the default quality profile and should be recommended for Macs
  with at least 24 GB unified memory at 1024².
- Q4 is an explicit low-memory/sustained profile and fits the measured 1024²
  request below 16 GB.
- The Worker must atomically materialize and reuse revision-scoped Q8/Q4 native
  checkpoints. It must never repeat online quantization for each process.

## Quality observations

The two-prompt fixed-seed set covers exact Chinese typography and a spatial
layout with three colored objects. Q8 and Q4 both preserved the requested
objects and positions. On the tested 1024² poster, Q4 rendered every requested
character correctly while Q8 substituted one character. This single result
does not establish that Q4 is generally better; a larger text/layout suite is
required before changing the default quality profile.

## Accepted Metal block fusion

The Z-Image transformer repeats four bandwidth-bound normalization patterns in
each of its 32 timestep-conditioned blocks. A guarded Metal path now fuses:

- `RMSNorm(x) * AdaLN scale`; and
- `residual + tanh(gate) * RMSNorm(branch)`.

The path preserves the public generation loop, including per-step progress,
cancellation and timing. It does not use the experimental deferred-sync loop.
At the representative 1024-token shape `[1, 4352, 3840]` in BF16, direct
same-process microbenchmarks measured:

| Operation | MLX composition | Fused Metal | Speedup | Mean absolute error |
| --- | ---: | ---: | ---: | ---: |
| RMSNorm + scale | 0.921 ms | 0.695 ms | 1.32x | 0.000710 |
| residual + gate + RMSNorm | 0.948 ms | 0.614 ms | 1.55x | 0.000706 |

The two-prompt Q8/512 regression measured 3.404 and 3.358 seconds, or a
3.381-second median, versus the 3.808-second native baseline: an 11.2% request
speedup with the same 13.51 GB peak-memory envelope. Both the exact Chinese
poster request and the left/center/right object-layout request passed visual
review. As expected for a diffusion graph, the BF16 reduction-order difference
does not produce pixel-identical images; the quality contract is semantic and
typographic parity rather than pixel identity.

A combined fused/deferred-sync 1024 run completed in 16.21 seconds versus the
17.54-second cold baseline, but deferred sync is not part of the accepted path
because it makes per-step progress and cancellation optimistic. A later
RMS-only 1024 run was invalidated by severe thermal throttling (30.63 seconds),
the same sustained-heat regime previously observed in the baseline. Cold-state
RMS-only 1024 A/B remains a release-candidate confirmation, not a blocker for
the already isolated 512 and operator-level results.

The Metal fusion must remain guarded by Metal availability, and the original
MLX graph remains the automatic fallback.

## Production integration

The accepted path is integrated in `ai2apps/model-z-image-mlx` 0.1.1. The
package owns the Metal kernels and optimized pipeline; shared Runtime 1.5.2
owns only mflux/MLX and the `mlx-only-v3` optional-import compatibility patch.
The Worker exposes Q8, Q4 and BF16, uses group size 64, and atomically persists
revision-scoped native quantized checkpoints. A real Q8/512 generation through
the production package entrypoint reported the Metal path enabled and produced
the expected exact Chinese poster text.

Version 0.1.1 also exposes `image_edit`. The Worker accepts exactly one verified
PNG/JPEG/WebP data URL (maximum 25 MB), uses strength `0.75` by default, and
passes the controlled temporary image path into mflux Img2Img. The existing
native checkpoint cache and accepted RMSNorm/AdaLN Metal kernels are reused;
only one VAE encode is added and mflux automatically runs a strength-dependent
subset of the configured denoising steps.

The real Q8/512 strength-0.70 canary ran 3/8 denoising steps. The two requests
completed in 2.583 and 1.534 seconds including VAE work, preserved the source
teapot/cup/lemon composition, and peaked at 16.29 GB. Generation-only peak was
13.51 GB; the edit increase comes from VAE encoding residency and is recorded
as a follow-up memory optimization rather than hidden.

## Rejected optimizations

Precomputing caption embedding, caption RoPE and the two context-refiner blocks
outside the compiled denoising graph changed the native-Q8 median from 3.81 to
3.88 seconds and slightly increased active memory. The saved work is too small
to offset constant capture and scheduling overhead, so the prototype remains
benchmark-only.

Quantized Q/K/V packing changed the median to 3.868 seconds (1.6% slower).
Packing Q/K/V plus the parallel FFN W1/W3 projections changed it to 4.025
seconds (5.7% slower) and retained more packed weight memory. The wider QMM
outputs lose more tile efficiency than the saved dispatches recover. They also
change the diffusion result substantially, so neither path ships.

Q8 with quantization group size 128 reduced peak memory from 13.51 GB to 13.19
GB, but changed the 512 median to 4.63 seconds. That 0.31 GB saving is not worth
the throughput and quality tradeoff; group size 64 remains mandatory.

Deferring all eight step synchronizations produced pixel-identical output and
showed a 3.3% 512 improvement in one run, but missed the 5% gate and breaks
truthful per-step progress/cancellation. It remains benchmark-only.

The next speed candidate is a denoiser-wide fused Metal schedule after the
accepted RMS kernels have shipped. Its target is an additional 8-15% without
changing QMM tiling, memory policy or request semantics.
