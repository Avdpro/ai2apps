---
license: mit
pipeline_tag: audio-to-audio
tags:
  - mlx
  - voice-conversion
  - rvc
---

# MLX-RVC Serena e70

Native MLX RVC v2/48 kHz composite checkpoint for AI2Apps. It contains the
MLX-trained e70 synthetic Serena test voice, its exact retrieval index, the
shared ContentVec and RMVPE components, and the converted RVC v2/48 kHz
generator/discriminator initialization used by the native MLX trainer. The
checkpoint contains only safetensors and JSON; it does not require Torch,
torchaudio, FAISS, or pickle at runtime.

The voice training corpus was generated with the `serena` preset of Qwen3-TTS
and is intended as a built-in functional voice, not as the identity of a real
person. Users must have permission to process the source audio they submit.

The implementation is derived from RVC at source revision
`81eed5e8f68b6bed1789f682fe78cdd324495afc`. The selected voice is the native
MLX safe-adaptation epoch-70 checkpoint chosen by listening comparison.
