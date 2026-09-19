# MLX Actor Replacement

Native Apple-Silicon GhostV2 actor replacement for images and videos. The
Package detects faces with YuNet, encodes the reference identity with CVLFace,
maintains stable Track IDs, renders 256-pixel faces with the native NHWC MLX
generator, composites the result, encodes H.264, and optionally preserves the
source audio.

The quality preset uses FP16, batch 2, and detection on every frame. It reached
39.91 FPS end-to-end at 960x540 on the Apple M5 Max development Mac. Fast file
export uses batch 8 and detection every second frame with landmark-velocity
prediction, reaching 53.07 FPS. At 1080p that fast profile reached 32.13 FPS.

GhostV2 is the only product-facing engine. InSwapper and SimSwap remain
development comparisons and are not low-memory fallbacks. The minimum supported
machine has 16 GiB unified memory; unsupported machines are rejected before
weights load.

This source tree contains no pretrained weights. A release binds the separate,
signed, dual-source `ai2apps.mlx-ghostv2-checkpoint/v1` distribution. GhostV2
source and pretrained models are BSD-3-Clause; YuNet is MIT.
