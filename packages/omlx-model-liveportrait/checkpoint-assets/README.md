---
license: mit
library_name: mlx
pipeline_tag: image-to-video
---

# MLX LivePortrait

Native MLX conversion of the official LivePortrait human portrait-animation
checkpoint for AI2Apps on Apple Silicon.

The repository contains seven deterministic NPZ weight files and an oMLX YuNet
face-detector bundle. It excludes InsightFace weights. Use the signed
`ai2apps/model-liveportrait-mlx` Package for inference, provenance checks,
multipart input validation, progress, cancellation, and audio preservation.

Default precision is FP32; BF16 is an explicit faster profile. FP16 is not
supported.
