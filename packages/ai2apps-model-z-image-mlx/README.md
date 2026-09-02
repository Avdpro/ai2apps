# Z-Image MLX Model Package

AI2Apps Model Worker package for `Tongyi-MAI/Z-Image-Turbo` on Apple Silicon.

It provides Q8, Q4 and BF16 generation and single-image Img2Img editing,
revision-scoped persistent native MLX checkpoints, and guarded Metal
RMSNorm/AdaLN block fusion. Img2Img accepts a strength in `(0, 1]`; the same
optimized denoiser is reused after the one-time VAE encode. The original mflux
graph is used automatically when Metal fusion is unavailable.

Build a local development artifact with:

```bash
.venv/bin/python scripts/build_model_provider_package.py \
  packages/ai2apps-model-z-image-mlx
```

The package requires `ai2apps/runtime-omlx >=1.5.2`.
