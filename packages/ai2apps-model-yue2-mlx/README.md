# YuE2 MLX

AI2Apps offline song-generation worker with original YuE2-3B and YuE2-Vae checkpoints. Requires Runtime 1.8.10 and macOS 26.2 on Apple silicon; 16 GiB memory minimum. The primary model declares its VAE dependency for preparation. Weights are obtained only via signed Registry distributions after original-license confirmation in ACPF/Discover. Code is Apache-2.0; see MODEL_LICENSE for weight terms. Final PCM16 stereo WAV is limited to 120 seconds; generation may end earlier or reach the limit. No reference-audio transcription, stage resume or partial rerender.
