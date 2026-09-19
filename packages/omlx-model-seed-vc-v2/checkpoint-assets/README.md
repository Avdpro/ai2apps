---
license: gpl-3.0
pipeline_tag: audio-to-audio
tags:
  - mlx
  - voice-conversion
  - seed-vc
---

# MLX Seed-VC v2

Torch-free native MLX conversion of the pinned Seed-VC v2 inference pipeline
for AI2Apps. The composite checkpoint contains the CFM and AR models, both
ASTRAL quantizers, CAMPPlus, HuBERT Large layer 18, and BigVGAN v2. Runtime
weights are stored as safetensors and configuration as JSON.

The default quality profile uses timbre mode with 30 diffusion steps. A 10-step
fast profile and a 30-step AR voice profile are also exposed by the Model
Package. A request must contain both source audio and reference-speaker audio;
reference audio is request-scoped and is not persisted as a Voice Profile.

The implementation is based on `Plachtaa/seed-vc` revision
`51383efd921027683c89e5348211d93ff12ac2a8`. See `NOTICE.md` for all pinned
checkpoint sources and licenses.
