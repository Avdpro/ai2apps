# MLX WhisperX Detailed Transcription Package

This directory is the source contract for a standalone subtitle/meeting
transcription Model Worker. Its public models use the dedicated
`audio_detailed_transcription` type and operation, declare
`chat_eligible: false`, and require the published Runtime 1.6.0 capability
`audio-detailed-transcription-v1`. It is a subtitle and meeting-transcription
pipeline, not a Chat STT model.

Run `python -m experiments.mlx_whisperx.stage_package_candidate OUTPUT` to
produce a self-contained source tree. The staging command vendors only the
runtime pipeline modules under `src/mlx_whisperx`; it never includes test
fixtures, downloaded checkpoints, benchmark artifacts, or AMI/FLEURS audio.

The four Hugging Face snapshots have byte-identical ModelScope mirrors for the
selected runtime files. ModelScope adds `configuration.json`, which is excluded
by explicit `allow_patterns`. Each model identity has its own signed
distribution specification under `META/`; all four exact distributions are
published and anonymously verified in the Registry.

Release 0.1.4 carries signed `discovery`, `modelProfile`, and `modelInstall`
metadata in source. Its production artifact temporarily omits only the optional
top-level `modelInstall` catalog projection for Cloud compatibility, backed by
the Desktop's version-bounded 0.1.4 install mapping. Earlier releases through
0.1.3 continue to use legacy discovery/profile metadata. The dedicated model
type and all model capabilities remain signed in `service.yaml`.

0.1.2 avoids canonicalizing a sandbox-granted upload path before opening
it (important for macOS `/tmp` → `/private/tmp`) and accepts standard multipart
boolean strings such as `diarization=false`.

0.1.3 normalizes ASR language names and locale tags to the short codes required
by Qwen3 ForcedAligner, while retaining direct support for canonical full names.

0.1.4 keeps Qwen3-ASR's native transcript punctuation and casing when forced
alignment adds word timestamps. The aligner only replaces transcript text when
its normalized lexical coverage falls below the hallucination safety threshold.
