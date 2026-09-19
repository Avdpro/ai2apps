# MLX Seed-VC v2 validation harness

The production-shaped implementation now lives in
`packages/omlx-model-seed-vc-v2/src/mlx_seed_vc_v2/`. This directory contains
offline checkpoint converters, PyTorch oracle validators, and runnable local
benchmarks. Production inference does not import Torch.

## Fixed upstream and initial target

- Repository: `Plachtaa/seed-vc`
- Revision: `51383efd921027683c89e5348211d93ff12ac2a8`
- Upstream status: archived read-only on 2025-11-21
- Implemented target: v2 `hubert-bsqvae-small`, including the AR token
  generator and the direct timbre path.

## Implemented graph

| Component | MLX direction |
|---|---|
| HuBERT Large | MLX Wav2Vec2-compatible encoder truncated at layer 18 |
| ASTRAL | 12-block ConvNeXtV2 plus BSQ-32 and BSQ-2048 |
| AR | 12-layer GQA transformer, reset RoPE positions, KV cache, EOS generation |
| CFM | Two discrete length regulators, 13-layer DiT, dual CFG, cosine sway Euler |
| Style | Full CAMPPlus FCM + 52 dense TDNN layers and statistics pooling |
| Vocoder | mlx-audio BigVGAN v2 22 kHz, converted from NVIDIA weights |

No Torch runtime fallback is allowed. Legacy pickle checkpoints are consumed
only by the offline conversion scripts; the Model Worker reads safetensors.

## Gates

1. Primitive and block output parity against the fixed PyTorch CPU oracle.
2. End-to-end content preservation and reference-speaker similarity at least
   95% of the upstream score on Mandarin and English fixtures.
3. Offline warm RTF below 0.5 on the M5 Max quality profile.
4. Reference audio remains request-scoped and never becomes an implicit stored
   voice profile.
5. Torch, torchaudio, Triton, and arbitrary remote code are absent from the
   production Package and Runtime.
