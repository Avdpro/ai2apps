# Notices

- RVC implementation and architecture: Retrieval-based-Voice-Conversion-WebUI,
  MIT License, pinned source revision
  `81eed5e8f68b6bed1789f682fe78cdd324495afc`.
- The bundled functional voice is trained from synthetic audio generated with
  the Qwen3-TTS `serena` preset. It is marked as synthetic in the checkpoint
  manifest and must not be represented as a recording of a real person.
- The native MLX training initialization is a safetensors conversion of the
  pinned upstream RVC v2/48 kHz generator and discriminator checkpoints.
- The Package performs local voice conversion only. It does not grant rights
  to source recordings supplied by a user.
