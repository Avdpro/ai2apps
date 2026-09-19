# MLX Demucs two-stem validation

Date: 2026-09-05

## Boundary and isolation

- No App, Runtime, Registry, Package manifest, or installed model state was
  modified.
- The official PyTorch implementation is an experiment-only quality oracle.
- The production target remains an MLX-native backend on Runtime 1.6.0.
- All generated checkpoints, converted weights, WAV files, and reports are in
  `/tmp`; none are tracked by Git.

## Official baseline inspected

- Model: `htdemucs`
- Official signature/file: `955717e8-8726e21a.th`
- Download size: 80.2 MiB
- Architecture: `HTDemucs`
- Sources: drums, bass, other, vocals
- Sample rate/channels: 44.1 kHz stereo
- Segment: 7.8 seconds
- Tensors: 533
- Parameters: 41,984,456
- Raw tensor bytes: 83,968,912

The trusted official `.th` container was successfully exported to an untracked
84,129,080-byte NPZ in raw PyTorch layout. This proves checkpoint extraction;
it does not prove MLX weight-layout or inference parity.

## Automated contract tests

Command:

```bash
.venv/bin/python -m pytest experiments/mlx_demucs/tests -q
```

The tests cover stereo PCM round-trip, mono/rate adaptation, equal-length
stems, exact residual reconstruction, non-finite/shape rejection, deterministic
fixture generation, and JSON-safe checkpoint inspection.

## Real official-Demucs runs

Clean 13.69-second public speech fixture:

- Output: 603,729 frames per stem, 44.1 kHz stereo
- Dialogue energy ratio: 99.54%
- Background RMS: 0.001506
- Reconstruction max error: `1.86e-9`
- Wall time observed from the runner: about 4.1 seconds including model load

Deterministic speech plus synthetic amplitude-modulated chord:

- Duration: 13.69 seconds
- Elapsed: 3.402 seconds
- RTF: 0.2485
- Input dialogue SI-SDR: 3.12 dB
- Output dialogue SI-SDR: 17.19 dB
- Improvement: 14.07 dB
- Reconstruction max error: `7.45e-9`

These numbers are smoke evidence only. The chord is synthetic and favorable;
movie dialogue, real music, Chinese/English meetings, overlap, and ASR CER/WER
evaluation remain required.

## MLX STFT/iSTFT parity

The first native MLX primitive now matches the transform contract used by
`HTDemucs`: periodic Hann window, reflection-centered padding, quarter-window
hop, and orthonormal FFT normalization.

Command (run with Metal device access):

```bash
.venv/bin/python -m experiments.mlx_demucs.validate_stft
```

Result on a deterministic 44,032-sample stereo input with `n_fft=4096`:

- Spectrum shape: `[2, 2049, 44]`
- PyTorch-vs-MLX spectrum max absolute error: `5.34e-8`
- MLX round-trip max absolute error: `1.34e-7`
- MLX elapsed time: 0.212 seconds, including first-process execution overhead

This passes the first numerical primitive gate. It is not yet full-model
parity or a meaningful steady-state performance measurement.

## MLX encoder/decoder block parity

The MLX block implementation now includes:

- Conv1d/Conv2d and transposed-convolution PyTorch-to-MLX layouts
- exact GELU and channel GLU
- PyTorch-compatible GroupNorm
- two-layer dilated DConv residual branches and LayerScale
- time and frequency HEncLayer/HDecLayer paths

The fixed checkpoint's first time/frequency encoder and final time/frequency
decoder were compared between PyTorch CPU and MLX Metal. Shape parity passed
for all six checked outputs. The gate requires both peak-normalized error and
relative RMSE below 1% for every output.

| Output | Peak-normalized error | Relative RMSE |
|---|---:|---:|
| Time encoder 0 | 0.0365% | 0.0408% |
| Frequency encoder 0 | 0.0679% | 0.0242% |
| Time decoder 3 | 0.0613% | 0.0835% |
| Time decoder 3 saved branch | 0.1420% | 0.0590% |
| Frequency decoder 3 | 0.5572% | 0.6456% |
| Frequency decoder 3 saved branch | 0.1794% | 0.1244% |

All outputs pass. Absolute error grows inside DConv because the released
checkpoint contains large rescaled pointwise-convolution weights, so the gate
uses scale-aware metrics rather than requiring CPU/GPU reduction-order bit
identity.

## Transformer and complete stack parity

The exact 1D/2D sinusoidal positions and all five alternating self/cross
attention layers now run on MLX. Standalone Transformer parity passed with a
worst relative RMSE of 0.288%. The full four-depth encoder, bottom projections,
Transformer, decoder, skip connections, and final output shapes also passed a
tightened 3% integrated gate:

- Frequency final decoder: 0.808% peak-normalized error, 2.273% relative RMSE
- Time final decoder: 0.309% peak-normalized error, 0.306% relative RMSE
- Final shapes: frequency `[1, 2048, 8, 16]`, time `[1, 8192, 8]`

## Full MLX waveform model

`mlx_model.py` now implements the entire inference-only HTDemucs forward path:
alignment padding, complex-as-channels input, PyTorch-compatible sample
standard deviation, both convolution branches, cross-domain Transformer,
four-source complex reconstruction, iSTFT, and time/frequency summation.

On an 8,192-sample deterministic input, its final four-source waveform matched
PyTorch with 0.303% peak-normalized error and 0.198% relative RMSE. On the full
343,980-sample (7.8-second) model window:

- Output shape: `[1, 4, 2, 343980]`, exactly matching PyTorch
- Spectrum relative RMSE: `3.72e-7`
- Inverse-spectrum relative RMSE: `4.24e-7`
- Final waveform peak-normalized error: 0.389%
- Final waveform relative RMSE: 0.316%
- Combined PyTorch-reference plus MLX validation elapsed: 1.395 seconds

`MlxDemucsBackend` adds official-compatible centered padding, 25% overlap,
triangle weighting, and arbitrary-length overlap-add. A 9-second two-chunk
synthetic stereo comparison produced finite equal-shape output and 0.548%
relative RMSE against the official PyTorch backend. Peak-normalized error was
12.49% because this tone-only fixture produces a near-zero vocal estimate; the
scale-aware RMSE is the meaningful parity measure for that case.

MLX-only execution on a deterministic 7.8-second stereo tone fixture:

| Run | Elapsed | RTF | MLX peak memory | Post-run active memory |
|---|---:|---:|---:|---:|
| Cold | 0.279 s | 0.0358 | 1,611,263,336 bytes | 24 bytes |
| Warm | 0.244 s | 0.0313 | 1,611,263,336 bytes | 24 bytes |

This is comfortably faster than real time on the current development Mac.
The 1.61 GB figure is MLX's allocator peak, not whole-process RSS. Hardware and
OS identifiers still need to be captured by the formal release benchmark.

The existing English and Mandarin speech smoke fixtures were each mixed with
the same deterministic synthetic accompaniment and separated by the MLX
safetensors path:

| Fixture | Duration | RTF | Input SI-SDR | Output SI-SDR | Improvement |
|---|---:|---:|---:|---:|---:|
| English | 3.785 s | 0.0500 | 3.11 dB | 20.33 dB | +17.22 dB |
| Mandarin | 4.138 s | 0.0440 | 3.26 dB | 21.98 dB | +18.73 dB |

Both residual reconstructions remained within `2.98e-8`. These are encouraging
bilingual engineering fixtures, not a substitute for diverse real meetings,
films, music, or an end-to-end CER/WER study.

An exact backend comparison on the same 3.785-second English mixture measured
1.478 seconds for official PyTorch CPU (RTF 0.3905) versus 0.189 seconds for
MLX/Metal (RTF 0.0500), a 7.81x end-to-end speedup. Output dialogue SI-SDR was
20.3271 dB on CPU and 20.3275 dB on MLX; the 0.0004 dB difference is negligible.

The file-level MLX CLI was also exercised on a 9-second stereo WAV. It emitted
396,900-frame float32 `dialogue.wav` and `background.wav` files plus the v1 JSON
result. Both stems retained 44.1 kHz stereo and exactly 9.0 seconds; residual
reconstruction max error was `1.49e-8`.

## Checkpoint dual-source result

The existing `mlx-community/demucs-mlx` artifact is available from both
Hugging Face and ModelScope without authentication. Full copies of
`htdemucs.safetensors` and `htdemucs_config.json` were downloaded from both
origins into `/tmp` and compared byte-for-byte:

| File | Bytes | SHA-256 |
|---|---:|---|
| `htdemucs.safetensors` | 168,005,865 | `339d267a7a6983a11eedbdc00413c602a65e9b9103f695fb5c2b2a481cd9d297` |
| `htdemucs_config.json` | 1,892 | `9258499513944fc062fbca0f11be425a446ec5702869a87e225323d7a57d2a01` |

The fixed revisions tested were Hugging Face
`d4519e24ddc2dd4a11d56a193092433d852c3961` and ModelScope
`3e2b356248c71ec999090ca6e5eebc65654b8893`. The safetensors conversion uses MLX-native
convolution layouts and split Q/K/V projections. `load_converted_safetensors()`
now adapts those tensors in memory. Its result has exactly the same 533 keys,
shapes, and float32 values as the official loaded PyTorch state, with no missing,
extra, or unequal tensors. Full waveform parity using this safetensors source
also passed with the same 0.303%/0.198% short-window output errors.

The upstream Demucs code and the Hugging Face model repository declare MIT;
the ModelScope model card repeats MIT, while its repository metadata currently
reports `other`. The Package must ship the upstream MIT notice and record this
metadata discrepancy in its release review rather than silently normalizing it.

## Generic separation capability contract

The prototype now declares source separation under the existing
`audio_processing` model type and `audio_process` operation. The signed-capability
shape distinguishes native stems (`drums`, `bass`, `other`, `vocals`) from three
stable output profiles: native `music_4stem`, pipeline `vocals_instrumental`, and
pipeline `dialogue_background`. Derived outputs carry an explicit derivation;
unknown profiles are rejected. The v1 result now reports requested/effective
profile and derivation under `features.source_separation`.

The shared Host validator now validates profile identifiers, unique stems,
profile mode, derivation, default profile, fallback policy, timeline behavior,
and channel limits. This is a declaration/preflight contract only; no new
Runtime operation or App UI was added in this experiment.

The native `music_4stem` profile was exercised on the Mandarin fixture through
the public experiment CLI. It emitted equal-length 44.1 kHz stereo
`drums.wav`, `bass.wav`, `other.wav`, and `vocals.wav` files (182,503 frames
each), and the response correctly reported native status and direct derivation.
Unlike the residual two-track profile, four independently estimated stems are
not mathematically mixture-consistent; the observed summed reconstruction max
error was 0.00583, so consumers must not infer exact reconstruction from a
native multi-stem declaration.

## Package publication result

`ai2apps/model-demucs-mlx` 0.1.0 and its checkpoint distribution
`dist_ai2apps_mlx_demucs_htdemucs_d4519e24_v1` were published on 2026-09-06.
The distribution contains the two files above (`168,007,757` bytes, 21 pieces),
was built with full HF/ModelScope dual-download verification, and passed an
anonymous signed-Index readback at checkpoint Index v54.

The final 34,658-byte Package (`sha256:10bae80790089ca8507f75349c8eb83d2104015df5f50de5177dd86720c91252`)
was installed with the production Runtime 1.6.2 artifact in a clean temporary
instance. The public distribution downloader used both providers, the Worker
started inside the Managed Service Sandbox with the Runtime's CPython 3.11,
and a 9-second PCM16 request returned HTTP 200 with a valid 3,176,969-byte ZIP
containing equal-duration `dialogue.wav`, `background.wav`, and relative-path
`separation.json`. The residual reconstruction maximum error was `7.45e-9`.
Anonymous Package Registry readback then verified Repository snapshot v120 and
found both the artifact bytes and envelope JSON exactly equal to the local
signed release.

## Follow-up quality gates

1. Measure chunk-boundary continuity on a broader licensed speech, music, and meeting set.
2. Run Chinese/English ASR before/after separation and record CER/WER impact.
3. Add interruptible progress between inference windows without weakening Worker serialization.
