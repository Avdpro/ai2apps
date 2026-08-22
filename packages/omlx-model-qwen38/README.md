# omlx-model-qwen38

Installable, isolated Qwen3.8 Model Worker Package for AI2Apps. The model code
and MLX state run outside the AI2Apps Host. The compatibility layer recognizes the
official dense Qwen3.8-27B VLM configuration and adds blockwise FP8 checkpoint
dequantization before oMLX's existing Qwen3.5-family sanitizer runs. It also
recognizes the expected mixed ModelOpt checkpoint layout and preserves its
per-channel FP8 and packed NVFP4 codes and scales through MLX's native
quantized matrix multiplication paths.

In addition to package-level config and synthetic-transform tests, release
`0.1.0` was validated with the complete
`unsloth/Qwen3.8-27B-NVFP4` checkpoint pinned at
`16b6615af3548b88e2d8e382457bc705b00479cf`. Text, Chinese, and image
generation all completed through oMLX's VLM engine on a 128 GiB Apple Silicon
Mac. The exact checkpoint recommendation lives in `release-checkpoints.json`.

The package deliberately does not replace the standard mlx-lm/mlx-vlm engine.
MLX, MXFP4, and ordinary affine-quantized checkpoints continue through oMLX's
normal loader; the adapter only supplies family-specific compatibility work.

Install the Service Package from AI2Apps Packages/Models. Its manifest pins the
checkpoint commit and lets the Host guide the download. The Worker receives
only the selected repository's read-only cache and the exact snapshot path;
it has no outbound network or Host Secret access. Upgrading or removing this
Package changes Qwen3.8 support independently of the desktop application or
pip-installed AI2Apps runtime release.
