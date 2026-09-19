# MLX Demucs two-stem experiment

This experiment established the product-facing separation boundary and the
native MLX implementation. The production result is now published separately
as `ai2apps/model-demucs-mlx` 0.1.0; this directory remains the reproducible
parity and benchmark record rather than installed Package state.

## Current scope

- Input: mono or stereo audio.
- Output: equal-length float WAV `dialogue.wav` and `background.wav` plus
  `separation.json` (`ai2apps.audio-separation-result/v1`).
- The background stem is exactly `mixture - dialogue`. This preserves all
  input energy and makes the in-memory reconstruction error zero apart from
  floating-point rounding.
- `TorchDemucsBackend` runs official `htdemucs` only as a quality oracle.
  PyTorch, torchaudio, and Demucs are not Runtime dependencies.
- `MlxDemucsBackend` now runs the complete HTDemucs network on MLX/Metal from
  converted raw NPZ weights, including arbitrary-length overlap-add inference.
- The model declares generic `audio_processing.processing.separation`
  capabilities. Native four-stem output is kept distinct from derived
  `vocals_instrumental` and `dialogue_background` profiles.

## Reference run

Install the experiment-only dependencies into a development environment, then:

```bash
TORCH_HOME=/tmp/ai2apps-demucs-torch-cache \
  .venv/bin/python -m experiments.mlx_demucs \
  input.wav /tmp/demucs-two-stem --device cpu
```

The official checkpoint is downloaded to `TORCH_HOME`, never into the
repository or Runtime. `--device mps` is experimental; CPU remains the parity
oracle because PyTorch/MPS operator coverage is not the shipping path.

A deterministic speech-plus-synthetic-chord smoke benchmark can be run with:

```bash
TORCH_HOME=/tmp/ai2apps-demucs-torch-cache \
  .venv/bin/python -m experiments.mlx_demucs.benchmark \
  clean-speech.flac /tmp/demucs-benchmark --device cpu
```

It reports input/output SI-SDR, improvement, RTF, and reconstruction error.
The synthetic chord is only a repeatable engineering smoke fixture; release
quality requires separately licensed movie, music, and meeting evaluation sets.

## Checkpoint conversion boundary

`checkpoint.inspect_torch_checkpoint()` records architecture, source names,
sample rate, channel count, tensor count, and parameter count. The optional
`export_raw_npz()` helper emits raw PyTorch-layout tensors outside Git. Weight
layout transforms must be implemented and parity-tested layer by layer before
an MLX checkpoint can be called usable.

## Acceptance gates for the MLX backend

1. Identical output shape, duration, sample rate, and channel count.
2. Finite samples and monotonic progress for arbitrarily long inputs.
3. Chunk-boundary discontinuity below an explicit threshold.
4. PyTorch-vs-MLX layer/output parity on the same checkpoint.
5. Separation quality on speech+music, movie dialogue, and Chinese/English
   meeting fixtures; ASR CER/WER must improve or remain within an agreed bound.
6. RTF and peak memory reported for compact and M5 Max profiles.

The native implementation has passed Package Contract, public checkpoint,
Runtime 1.6.2, and Managed Service Sandbox acceptance. Broader licensed movie,
music, and meeting quality sets plus interruptible per-window cancellation
remain follow-up quality work rather than 0.1.0 publication blockers.

The first MLX-native primitive is available in `mlx_stft.py`. Run its
PyTorch parity check from a process with Metal device access:

```bash
.venv/bin/python -m experiments.mlx_demucs.validate_stft
```

`mlx_layers.py` now ports the time/frequency HEncLayer and HDecLayer primitives,
including dilated DConv residual branches, PyTorch-compatible GroupNorm, exact
GELU, GLU, LayerScale, and all convolution weight-layout transforms. Validate
the released checkpoint's first encoder and final decoder blocks with:

```bash
TORCH_HOME=/tmp/ai2apps-demucs-torch-cache \
  .venv/bin/python -m experiments.mlx_demucs.validate_layers
```

The implementation follows the Demucs architecture and retains its upstream
MIT notice in `LICENSE.demucs`. Checkpoint redistribution was independently
reviewed and published as
`dist_ai2apps_mlx_demucs_htdemucs_d4519e24_v1`.

Validate positional embeddings, all five alternating Transformer layers, and
the complete four-depth convolutional stack with:

```bash
TORCH_HOME=/tmp/ai2apps-demucs-torch-cache \
  .venv/bin/python -m experiments.mlx_demucs.validate_transformer
TORCH_HOME=/tmp/ai2apps-demucs-torch-cache \
  .venv/bin/python -m experiments.mlx_demucs.validate_stack
```

Validate waveform-to-four-source parity on the complete 7.8-second window:

```bash
TORCH_HOME=/tmp/ai2apps-demucs-torch-cache \
  .venv/bin/python -m experiments.mlx_demucs.validate_model \
  --length 343980
```

The backend accepts either the experiment's raw NPZ export or the byte-identical
Hugging Face/ModelScope `mlx-community/demucs-mlx` safetensors. The latter is
adapted in memory from its MLX-native convolution and split-QKV layout; no
second checkpoint copy is required. Run the actual two-track pipeline with:

```bash
.venv/bin/python -m experiments.mlx_demucs \
  input.wav /tmp/demucs-two-stem-mlx \
  --backend mlx --weights /path/to/htdemucs.safetensors
```
