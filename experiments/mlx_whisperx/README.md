# MLX Detailed Transcription (WhisperX-compatible) standalone experiment

This directory is an isolated, App-independent prototype of the
WhisperX-compatible capability pipeline. It does not register models, modify
the AI2Apps Runtime, or use an installed AI2Apps instance.

This is a subtitle, meeting-transcription, and other detailed-audio pipeline.
It is deliberately **not** the STT backend for Chat. Chat continues to use its
low-latency STT/TTS path; this service optimizes for accurate text, forced
alignment, and anonymous speaker attribution.

The first milestone implements:

- MLX Whisper and Qwen3-ASR transcription through the repository development
  environment;
- deterministic VAD segmentation before transcription;
- native Whisper word timestamps when the checkpoint provides alignment heads;
- optional MLX Sortformer diarization;
- deterministic speaker assignment by time overlap;
- WhisperX-compatible JSON with AI2Apps feature provenance.

The second milestone adds independent MLX Wav2Vec2 CTC forced aligners for
English words and Simplified Chinese characters. Native Whisper attention
timings remain available as a low-memory fallback and are never mislabeled as
CTC forced alignment. Unsupported alignment languages fail closed unless the
caller explicitly selects the `native` fallback. Out-of-vocabulary characters
inside an otherwise supported transcript are skipped for timing by default,
retained in segment text, and reported in `features.alignment`; callers can use
`--alignment-unknown-characters reject` for fail-closed behavior.

The current high-quality path uses Qwen3-ASR 1.7B 4-bit, Qwen3 ForcedAligner
0.6B 8-bit, and Sortformer v2.1. Qwen alignment covers mixed Chinese, Latin
text, and numbers without the Chinese CTC vocabulary gap. Sortformer's native
AOSC speaker cache keeps four global anonymous speaker slots across streaming
chunks; the legacy window-local mode remains available explicitly.
Meeting recordings default to `MeetingEnergyVAD`, while ordinary CLI runs keep
the original Energy VAD default. Transcription spans are hard-bounded to 30
seconds before ASR. After Qwen forced alignment, zero-duration units are
excluded from both word arrays and final subtitle text; the result reports the
aligned, discarded, rewritten, and removed-character counts so hallucination
suppression is auditable.
Same-speaker spans bridge only the model's native 0.12-second gap by default.
Longer 0.25/0.5/1/2-second compensation remains an explicit experiment: it
reduced frame-level DER but degraded transcript speaker attribution on one or
both AMI meetings, so it is not silently enabled.

## Run

Use a local checkpoint path to keep the experiment offline and independent of
the App model store:

```bash
.venv/bin/python -m experiments.mlx_whisperx \
  input.wav \
  --model /absolute/path/to/mlx-whisper-checkpoint \
  --output /tmp/mlx-whisperx-result.json
```

Select the existing MLX Qwen3-ASR backend explicitly:

```bash
.venv/bin/python -m experiments.mlx_whisperx \
  input.wav \
  --backend qwen3-asr \
  --model /absolute/path/to/Qwen3-ASR-0.6B-4bit \
  --language zh-CN \
  --output /tmp/qwen3-asr-whisperx-result.json
```

Enable an independently downloaded MLX Sortformer checkpoint:

```bash
.venv/bin/python -m experiments.mlx_whisperx \
  input.wav \
  --model /absolute/path/to/mlx-whisper-checkpoint \
  --diarization-model /absolute/path/to/mlx-sortformer-checkpoint
```

For the full trained-model path, reuse the same Sortformer pass for speech
activity and diarization:

```bash
.venv/bin/python -m experiments.mlx_whisperx \
  input.wav \
  --model /absolute/path/to/mlx-whisper-checkpoint \
  --language en \
  --vad sortformer \
  --no-word-timestamps \
  --alignment-model /absolute/path/to/mlx-wav2vec2-ctc-checkpoint \
  --alignment-min-word-score 0.01 \
  --alignment-window-seconds 30 \
  --alignment-unknown-characters skip \
  --diarization-window-seconds 30 \
  --diarization-model /absolute/path/to/mlx-sortformer-checkpoint
```

The score threshold is opt-in and is reported in `features.alignment`; its
default is `0.0`, so the pipeline does not silently discard uncertain words.
CTC work is grouped into bounded adjacent-segment windows, making long-audio
peak activation memory depend on the configured window rather than the full
recording duration.

Sortformer is a four-speaker model. On audio longer than the configured
diarization window, the default `global-streaming` mode uses its native AOSC
speaker cache and FIFO so `speaker_0` through `speaker_3` remain global across
chunks. `--diarization-speaker-identity window-local` is the explicit fallback
for recordings with more than four total participants; it avoids false global
merges but does not preserve identities between windows. Use Energy VAD for
content coverage and Sortformer for attribution until a dedicated trained VAD
has passed the long-audio recall gate.

Enable multilingual Qwen forced alignment:

```bash
.venv/bin/python -m experiments.mlx_whisperx input.wav \
  --backend qwen3-asr \
  --model /absolute/path/to/Qwen3-ASR-1.7B-4bit \
  --language zh-CN --vad energy \
  --alignment-backend qwen3-forced-aligner \
  --alignment-model /absolute/path/to/Qwen3-ForcedAligner-0.6B-8bit \
  --alignment-window-seconds 240 \
  --diarization-model /absolute/path/to/Sortformer-4spk-v2.1-fp16
```

## Standalone Detailed Transcription API

`api.py` exposes only the independent endpoint
`POST /v1/audio/transcriptions/detailed` and its capability document. It does
not register or alter `/v1/audio/transcriptions`, Chat, the App, or Runtime.
The development Package contract is in `package.manifest.json`.
`package_candidate/` plus `stage_package_candidate.py` define the production
Package source tree. The Package uses a dedicated
`audio_detailed_transcription` operation, is not Chat-eligible, and requires
the published Runtime 1.6.0 `audio-detailed-transcription-v1` capability.
All four referenced checkpoint distributions are published and anonymously
verified in the Registry, so the production Package can be signed and
published.

The request supports `profile=compact|quality`, `timestamps=segment|word`,
anonymous `diarization`, `speech_rate_analysis`, and
`unsupported_policy=reject|compatibility`. Unsupported speaker recognition
always rejects because identities must never be fabricated. Emotion can only
use the explicit compatibility policy, which returns `neutral` together with
`status=fallback`; it is never reported as native inference.

Run the isolated API with four pinned local checkpoints:

```bash
.venv/bin/python -m experiments.mlx_whisperx.api \
  --compact-asr /path/to/Qwen3-ASR-0.6B-4bit \
  --compact-asr-revision 313d850181767edf09f00a9c289becca70e58cd0 \
  --quality-asr /path/to/Qwen3-ASR-1.7B-4bit \
  --quality-asr-revision 78a389c776a5483b2d0d4ea5494e11012e0d6159 \
  --aligner /path/to/Qwen3-ForcedAligner-0.6B-8bit \
  --aligner-revision 0e1a68e91d815300c7c9754b2a7639378b23db15 \
  --diarizer /path/to/Sortformer-4spk-v2.1-fp16 \
  --diarizer-revision e23e6404bd9859e93edbf94a740eb1c7fc58f12e
```

Enable independent CTC forced alignment. `--no-word-timestamps` demonstrates
that word boundaries come from the CTC model rather than Whisper attention:

```bash
.venv/bin/python -m experiments.mlx_whisperx \
  input.wav \
  --model /absolute/path/to/mlx-whisper-checkpoint \
  --language en \
  --no-word-timestamps \
  --alignment-model /absolute/path/to/mlx-wav2vec2-ctc-checkpoint
```

Prepare the pinned public English CTC checkpoint without downloading redundant
PyTorch or TensorFlow weights:

```bash
.venv/bin/python -m experiments.mlx_whisperx.prepare_ctc_model \
  --source facebook/wav2vec2-base-960h \
  --revision 22aad52d435eb6dbaf354bdad9b0da84ce7d6156 \
  --source-dir /absolute/ignored/source-directory \
  --output /absolute/ignored/mlx-ctc-directory
```

Prepare the pinned public Simplified Chinese CTC checkpoint in the same way:

```bash
.venv/bin/python -m experiments.mlx_whisperx.prepare_ctc_model \
  --source wbbbbb/wav2vec2-large-chinese-zh-cn \
  --revision b654b5f3df69725df32808de454a1b865c829e4c \
  --language zh \
  --source-dir /absolute/ignored/source-directory \
  --output /absolute/ignored/mlx-chinese-ctc-directory
```

The selected Chinese aligner has a Simplified Chinese (`Hans`) vocabulary.
For the current smoke path, pass `--language zh --prompt
'以下内容使用简体中文。'`. The prompt is an output constraint rather than a
general Traditional-to-Simplified converter: arbitrary Traditional Chinese
input still fails closed until a separately versioned normalizer is provided.
Unlike English, the Chinese target builder does not insert a word-delimiter
token between character timestamp targets.

The CLI accepts Hugging Face repository identifiers for development
experiments, but Package integration must use Host-prepared checkpoints pinned
to immutable revisions.

## Tests

The contract and pipeline tests use fake inference backends and do not import
MLX, access the network, or require Metal:

```bash
.venv/bin/python -m pytest -q experiments/mlx_whisperx/tests
```

Real-model validation is intentionally separate because it requires a Metal
device and local checkpoints.

Deterministic 10 dB and 5 dB white-noise fixtures can be generated with
`create_noisy_fixture.py`. The generated manifest records noise kind, exact
SNR, seed, and output SHA-256, so noisy regression is reproducible without
checking derived audio into Git.

## Priority-language mini-benchmark

The checked-in manifests pin five public FLEURS test utterances for each
priority language, including the dataset revision, reference text, license,
and each audio file's SHA-256. Download only those files:

```bash
.venv/bin/python -m experiments.mlx_whisperx.prepare_benchmark \
  --manifest experiments/mlx_whisperx/fixtures/fleurs-zh-cn-5.json \
  --output experiments/mlx_whisperx/.artifacts/fleurs
```

Run the actual trained-VAD pipeline rather than bare Whisper inference:

```bash
.venv/bin/python -m experiments.mlx_whisperx.benchmark \
  --manifest experiments/mlx_whisperx/fixtures/fleurs-zh-cn-5.json \
  --audio-root experiments/mlx_whisperx/.artifacts/fleurs \
  --model experiments/mlx_whisperx/.models/whisper-small-asr-6bit \
  --vad sortformer \
  --diarization-model \
    experiments/mlx_whisperx/.models/sortformer-4spk-v2.1-fp16 \
  --output experiments/mlx_whisperx/.artifacts/benchmark-small-zh.json
```

The runner computes dependency-free English WER or Chinese CER after Unicode,
case, whitespace, and punctuation normalization. This five-case fixture is a
fast regression and candidate screen, not a statistically meaningful model
quality claim. Full model selection still requires the complete public test
split and long/noisy/speaker-overlap suites.

The complete split supersedes the five-case screen. Qwen3-ASR 1.7B 4-bit
reached 11.99% Chinese CER and 7.04% English WER, versus 12.67%/8.97% for its
0.6B sibling and 16.48%/7.82% for Whisper Turbo. The recommendation is now
Qwen 0.6B for the compact profile and Qwen 1.7B for the quality profile in this
detailed-transcription service. Whisper remains a pluggable baseline rather
than the Chat STT route.

## Full benchmark and long-audio stress run

The full FLEURS-derived manifests contain 945 Simplified Chinese and 647 US
English test utterances. `prepare_benchmark` verifies the pinned transcript
hash and exact audio count. The benchmark writes an atomic checkpoint every ten
cases and resumes with `--resume`:

```bash
.venv/bin/python -m experiments.mlx_whisperx.benchmark \
  --backend qwen3-asr \
  --manifest experiments/mlx_whisperx/fixtures/fleurs-en-us-full.json \
  --audio-root experiments/mlx_whisperx/.artifacts/fleurs-full \
  --model experiments/mlx_whisperx/.models/qwen3-asr-0.6b-4bit \
  --vad sortformer \
  --diarization-model \
    experiments/mlx_whisperx/.models/sortformer-4spk-v2.1-fp16 \
  --checkpoint-every 10 --resume \
  --output experiments/mlx_whisperx/.artifacts/turbo-en-full.json
```

Build a deterministic multi-minute fixture from the same pinned manifest:

```bash
.venv/bin/python -m experiments.mlx_whisperx.compose_long_audio \
  --manifest experiments/mlx_whisperx/fixtures/fleurs-en-us-full.json \
  --audio-root experiments/mlx_whisperx/.artifacts/fleurs-full \
  --duration-seconds 600 --silence-seconds 0.3 \
  --output experiments/mlx_whisperx/.artifacts/fleurs-en-10min.wav
```

The sidecar records the exact source sequence, boundaries, reference text, and
composed WAV SHA-256. Full split and ten-minute results are recorded in
`VALIDATION.md`; generated audio and result JSON remain ignored.

## Reproducible model validation

The public, authentication-free checkpoints used for the first real-model run
are pinned by immutable revision and weight SHA-256 in `models.lock.json`.
Commands, measurements, passed capabilities, and known limitations are recorded
in `VALIDATION.md`. Model binaries and generated artifacts remain ignored.

Use an `mlx-audio` ASR conversion that includes processor and tokenizer assets.
Legacy `mlx-examples` directories such as `whisper-tiny-mlx` contain compatible
weights but not the complete loading contract required by the current backend;
the CLI rejects them before model allocation with an actionable error.
