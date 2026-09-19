# MLX-RVC Model Package

Status: release source and complete immutable composite checkpoint layout prepared;
Package build and publication remain.

The Package-owned implementation under `src/mlx_rvc/` runs RVC v2/48 kHz with
native MLX ContentVec, RMVPE, exact retrieval, reverse flow, and NSF decoding.
`src/worker_adapter.py` exposes it through `audio_process` with
`task=voice_conversion` and the common controls `semitones`, `retrieval_rate`,
`protect`, `speaker_id`, and `seed`.

The Package also owns a native MLX training path. `src/train_voice.py` accepts
a directory of WAV recordings, uses the shared MLX ContentVec and RMVPE
checkpoints to build a non-executable safetensors cache, trains the RVC v2
generator and nine-branch discriminator with MLX autodiff, and emits
`model.safetensors`, `index.safetensors`, periodic training checkpoints, and a
JSON report. Preprocessing follows the pinned RVC trainer's 48 Hz high-pass,
3.7-second overlapping chunks, and blended peak normalization. The generator
objective uses the original 128-bin log-mel L1 reconstruction term with weight
45 rather than a substitute linear-frequency loss. The default compute
precision is FP16 with FP32 optimizer master weights; BF16 and FP32 remain
explicit alternatives, while losses accumulate in float32. Torch remains confined to the trusted
one-time conversion of the fixed upstream G/D initialization weights.

The default `safe` adaptation mode freezes the linguistic Content Encoder and
invertible Flow, then updates the posterior, NSF decoder, and speaker table.
This is a quality boundary: unrestricted full-network adaptation was faster
but failed the independent ASR content-preservation gate. The CLI defaults to
30 epochs; 10 is the quick preview tier and 100 remains an explicit extended
experiment.

Long training runs write `training-state.safetensors` plus a JSON sidecar at
every checkpoint interval. This rolling state includes the generator,
discriminator, FP32 master weights, both Adam states, epoch, step, and fixed
configuration. Resume with `src/train_voice.py --resume
/path/to/training-state.safetensors --epochs TARGET`; `--epochs` is the desired
total, not the number of additional epochs. Per-interval generator snapshots
remain available for listening comparisons without duplicating the much larger
optimizer state.

The Model Worker additionally implements `audio_voice_training` at
`/v1/audio/voices/train`. It accepts one bounded ZIP containing only WAV
files, reports preprocessing/training progress through the Worker protocol,
supports cancellation, and returns a ZIP Voice Bundle. This operation requires
Runtime 1.6.2 and its explicit `audio-voice-training-v1` capability. The full
Package can therefore advertise both `audio_process` and
`audio_voice_training` once that Runtime is published.

The release checkpoint is one atomic composite artifact containing:

1. Converted HuBERT/ContentVec safetensors plus `config.json`.
2. Converted RMVPE safetensors plus its fixed mel-basis safetensors.
3. A selected, legally publishable target voice containing `model.safetensors`
   and `index.safetensors`.
4. The converted RVC v2/48 kHz generator and discriminator initialization used
   by the native MLX voice trainer.

`scripts/stage_checkpoint.py` reproduces this layout and records every file's
size and SHA-256. The Worker remains offline and can only read the Host-selected
checkpoint root.
