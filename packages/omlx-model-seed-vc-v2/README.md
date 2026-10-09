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

### Precision contract (2026-10-08)

The dedicated Seed-VC Worker and standalone package set `MLX_ENABLE_TF32=0` before MLX operations. Import the package before running any MLX operation in standalone processes: MLX caches this setting. Reduced-precision FP32 matmul on supported hardware can flip near-zero ASTRAL sign bits. The shared Runtime and other model Workers are unchanged. Exact wide/narrow tokens passed the fixed speech/sweep/silence CUDA comparison; this does not imply complete voice-conversion quality or signed release acceptance. See `spark/evidence/media/seed-vc-v2-fp32-token-fix-20261008.json`.

### Long audio contract (2026-10-08)

The native Mac and CUDA pipelines now follow the pinned upstream v2 context limits: HuBERT uses 30-second windows with 5-second input context (250 token positions trimmed on subsequent windows), the reference uses at most its first 25 seconds, and AR condition segments contain at most 1500 reduced source-plus-reference tokens. Each AR segment receives the request seed plus its segment index modulo 2^32. Generated AR tokens are concatenated before length regulation; diffusion then uses a 30-second total prompt-plus-source frame window with 16-frame cosine-squared overlap blending. This retains every generated frame once, rather than discarding non-overlapping semantic frames at an AR segment boundary. Short inputs retain their existing computation and seed behavior.

An 81.76-second bilingual stress recording exposed catastrophic early EOS in the old unbounded voice path on both backends. The chunked implementation restores approximately full output duration; this execution result does not establish content or voice quality. The fixture concatenates two complete synthetic recordings and is not a natural continuous recording. Release acceptance still requires long-form content, seam and voice-quality checks, current isolated Worker/Host verification and signed installation.
