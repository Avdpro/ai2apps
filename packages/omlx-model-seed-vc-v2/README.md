# MLX Seed-VC v2 Model Package

Status: release source and immutable composite checkpoint layout prepared;
checkpoint origins, signed distribution, Package build, and publication remain.

The Package-owned implementation under `src/mlx_seed_vc_v2/` is a Torch-free
MLX port of Seed-VC v2. It includes HuBERT Large layer 18, ASTRAL ConvNeXtV2
with BSQ-32/BSQ-2048, the 12-layer AR model with KV caches, both discrete
length regulators, CAMPPlus, the 13-layer dual-guidance CFM DiT, cosine sway
Euler sampling, and NVIDIA BigVGAN v2.

`src/worker_adapter.py` exposes `audio_process` with `task=voice_conversion`.
It requires source part `file` and target-speaker part `reference`; controls are
`mode=timbre|voice`, `diffusion_steps`, `guidance_intelligibility`,
`guidance_similarity`, `length_adjust`, and `seed`.

The default quality tier is `timbre` with 30 diffusion steps, which matched the
pinned Torch reference in the same listening task. Ten steps remains the fast
tier; AR `voice` mode is exposed as a separate 30-step quality profile.

Production manifests are intentionally deferred until the converted checkpoint
is published immutably to both Hugging Face and ModelScope. The checkpoint root
contains the component safetensors plus `hubert/` and `bigvgan/` directories;
Torch is an offline conversion dependency only and is not required by the
Model Worker. `scripts/stage_checkpoint.py` reproduces the exact upload layout
and records every file's size and SHA-256.
