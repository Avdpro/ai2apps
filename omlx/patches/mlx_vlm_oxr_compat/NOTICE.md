# OXR compatibility sources

Model, config, vision and processor copied without modification from
Blaizzy/mlx-vlm commit 8826b1126507cd8e87d125c656e10d119b764d0e,
mlx_vlm/models/oxr (PR #2560), copyright its contributors, MIT license.
See LICENSE-mlx-vlm. The original model weights are separately governed by
SoMark OXR License (Apache 2.0 plus additional terms); this backport does not
include weights or change their license. Local validation: ai2apps/experiments/oxr_mlx.

Also includes upstream qwen3/config.py, qwen3/language.py, mlp.py and activations.py. Import paths are adjusted to keep these dependencies OXR-local, avoiding registration or replacement of shared Qwen/MLP modules.
The OXR-local Qwen3 decoder uses the existing mlx-lm initialize_rope API, since the pinned mlx-vlm has no such helper. OXR uses vanilla RoPE (no scaling).
