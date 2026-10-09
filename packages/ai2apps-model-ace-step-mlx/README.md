ACE-Step 1.5 Turbo MLX

Native MLX music generation with optional lyrics, 10–120 seconds; 10.09 GB checkpoint.

Operation `audio_generate`, endpoint `/v1/audio/generations`. Required fields: model, task (music or sound_effects), prompt and duration. Optional: steps (1–100, default 8), seed, lyrics (ACE only), language. Output: stereo PCM16 WAV. Reference audio and streaming are not supported.

Weights are downloaded by the Host through a signed multi-source Registry distribution. The Worker has no outbound network permission and reads only `context.checkpoint_for()` paths. Each request releases its model; cancellation is cooperative during sampling/planning.

Install Runtime 1.8.9+, accept the checkpoint terms when prompted, prepare the selected model, then start the managed service. Package removal does not implicitly delete shared checkpoints.

The advertised 120-second range requires 48 GiB unified memory: the measured 120-second MLX peak was 35.82 GB on M5 Max. After each request active MLX allocation returned below 1 KiB and cache allocation to zero.
