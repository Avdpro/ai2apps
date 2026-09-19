# MLX-Seed-VC validation

Date: 2026-09-05

- Fixed source: `Plachtaa/seed-vc` at
  `51383efd921027683c89e5348211d93ff12ac2a8`.
- Fixed checkpoint source: `Plachta/Seed-VC` at
  `257283f9f41585055e8f858fba4fd044e5caed6e`.
- v1 checkpoint SHA-256:
  `8ec8841b20bb46df9f7e8e570a6946a4b87b940133c7f0e778487ff33841f720`.
- Native MLX Euler/CFG flow sampler implemented and contract-tested.
- Continuous Whisper-content length regulator real-checkpoint output:
  `[1, 47, 512]`, relative RMSE `0.02596%` against the PyTorch oracle.

## Seed-VC v2 checkpoints

- CFM/AR: `Plachta/Seed-VC` revision
  `257283f9f41585055e8f858fba4fd044e5caed6e`.
- ASTRAL: `Plachta/ASTRAL-quantization` revision
  `4a2e9679f76eb03753adc8c503e3c23bb9c22f26`.
- CAMPPlus: `funasr/campplus` revision
  `e4b6ede7ce16997aff4ae69fbca1f0175e2afede`.
- HuBERT Large: `facebook/hubert-large-ll60k` revision
  `ff022d095678a2995f3c49bab18a96a9e553f782`.
- BigVGAN: `nvidia/bigvgan_v2_22khz_80band_256x` revision
  `633ff708ed5b74903e86ff1298cf4a98e921c513`.

## Numerical gates

- v2 CFM length regulator relative RMSE `7.77e-7`; AR regulator exact.
- HuBERT layer 18 relative RMSE `0.002079`, cosine `0.99999797`.
- ASTRAL BSQ-32 token match `100%`; BSQ-2048 random-fixture token match
  `94.737%` with encoder relative RMSE `0.001918`. The wide mismatch is a
  near-zero sign sensitivity under Metal convolution accumulation.
- AR output logits relative RMSE `0.001081`, Top-1 parity `100%`.
- CFM DiT relative RMSE `0.002316`, cosine `0.99999869`.
- CAMPPlus relative RMSE `1.60e-6`, cosine `1.0`.
- BigVGAN waveform relative RMSE `0.01590`, cosine `0.99987483`.

## End-to-end gates on M5 Max 128 GiB

The Package-owned Torch-free path generated valid 22.05 kHz WAV files:

- English 3.831 s, 10 steps: `0.616 s`, RTF `0.1607`, peak MLX `4.539 GB`.
- Mandarin 7.605 s, 10 steps: `1.122 s`, RTF `0.1476`, peak MLX `5.225 GB`.
- AR `voice` smoke, 2.450 s output and 4 steps: `0.740 s`, RTF `0.3021`,
  peak MLX `4.767 GB`.

Qwen3-ASR 0.6B recovered the complete source sentence from both full 10-step
outputs. CAMPPlus cosine similarity moved from source-to-target `0.4641` to
English output-to-target `0.8994`, and from `0.2769` to Mandarin
output-to-target `0.8003`.

The source implementation is complete. Signing/publication remains separate:
converted weights first need immutable Hugging Face and ModelScope artifacts.

Runtime compatibility was tested against the signed Runtime 1.6.0 DMG using
its bundled Python 3.11. A 1-second, 4-step Package-layout inference completed
at RTF `0.3484` with `3.345 GB` peak MLX memory. The Package constructs its
Slaney mel filter directly (numerically equal to librosa at relative error
`4.22e-8`) because calling librosa's cached filter builder from the sealed
Runtime process was not reliable. The existing 1.6.0 dependency stack and MLX
kernels are sufficient; production API integration still requires a later
Runtime release containing the new multipart `reference` and guidance fields.
