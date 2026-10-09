Stable Audio 3 Small MLX

Distribution purpose: non-commercial installation, evaluation and testing. Users confirm the original Stability AI and Gemma license terms in ACPF/Discover before any weight download; commercial usage remains subject to those terms.

Native MLX text-to-music and sound effects, 1–120 seconds. Powered by Stability AI. Weight download requires acceptance of Stability AI and Gemma terms.

Operation `audio_generate`, endpoint `/v1/audio/generations`. Required fields: model, task (music or sound_effects), prompt and duration. Optional: steps (1–100, default 8), seed, lyrics (ACE only), language. Output: stereo PCM16 WAV. Reference audio and streaming are not supported.

Weights are downloaded by the Host through a signed multi-source Registry distribution. The Worker has no outbound network permission and reads only `context.checkpoint_for()` paths. Each request releases its model; cancellation is cooperative during sampling/planning.

Install Runtime 1.8.9+, accept the checkpoint terms when prompted, prepare the selected model, then start the managed service. Package removal does not implicitly delete shared checkpoints.

Music and SFX use separate DiT variants (about 1.70 GB per selection); both share the T5Gemma text encoder and SAME-S decoder. The Host checkpoint blob cache deduplicates these shared files. No reference-audio encoder is needed for v1 text-only generation.
