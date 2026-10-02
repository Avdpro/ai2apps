# SAM 2.1 Video Cutout MLX Package

Production Package for point-prompted foreground masks. The worker accepts a
video plus positive/negative points on one frame and returns a soft grayscale
MP4 mask aligned to the source timeline. The mask is intended to become a
dynamic Composer mask source; it is not a transparent-video export.

The MVP uses Hiera Small, supports forward propagation from one prompt frame,
and limits input to 450 frames at up to 1920x1080. The Package depends on
`ai2apps/runtime-omlx >=1.8.6,<2.0.0`; weights remain outside the Package and
are resolved through the published, signed dual-source checkpoint distribution
`dist_ai2apps_sam21_hiera_small_mlx_1b7b9882_v1`.
