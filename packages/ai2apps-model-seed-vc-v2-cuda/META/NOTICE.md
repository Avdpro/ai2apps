# Seed-VC v2 CUDA notices

This Package wraps the modified CUDA Seed-VC implementation supplied by the
AI2Apps CUDA Runtime. Seed-VC and ASTRAL are GPL-3.0; CAMPPlus is Apache-2.0,
and NVIDIA BigVGAN v2 is MIT. Original notices and source revisions are retained
in source-lock.json, META/licenses, and the fixed checkpoint model card.
Package adapter source is included. Runtime-owned CUDA engine sources remain
in the matching Runtime; no MLX execution dependency is shipped here.
