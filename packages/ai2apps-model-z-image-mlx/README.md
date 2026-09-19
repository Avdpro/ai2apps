> 0.1.3 capability contract: Z-Image Turbo text-to-image generation only; image editing is disabled pending acceptance.

# Z-Image MLX Model Package

AI2Apps Model Worker package for `Tongyi-MAI/Z-Image-Turbo` on Apple Silicon.

It provides Q8, Q4 and BF16 text-to-image generation,
revision-scoped persistent native MLX checkpoints, and guarded Metal
RMSNorm/AdaLN block fusion. Public image editing is rejected before model loading
because the current Img2Img path has not passed editing acceptance. The original mflux
graph is used automatically when Metal fusion is unavailable.

Build a local development artifact with:

```bash
.venv/bin/python scripts/build_model_provider_package.py \
  packages/ai2apps-model-z-image-mlx
```

The package requires `ai2apps/runtime-omlx >=1.5.2`.
