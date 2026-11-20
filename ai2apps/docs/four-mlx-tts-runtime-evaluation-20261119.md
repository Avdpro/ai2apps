# Four MLX TTS backends — Runtime evaluation, 2026-11-19

Implemented and exercised through `omlx.engine.tts.TTSEngine`: ZONOS3-Mini,
MOSS-TTS-Nano-100M, Fish Audio Drama 3 (4-bit), and Breeze TTS 2.
This is a source-level Runtime evaluation, not a published Runtime/Model Package
or a completed Voice Studio installation. Dev/App-Dev were not restarted.

## Implementation

- Keep Runtime MLX 0.32.0, mlx-lm 0.31.3, and mlx-audio's existing pin
  `cd605ecfcc266ccf6ea3077586c373101be982c6`.
- Reuse that pin's Breeze and MOSS implementations. Isolate Zonos3, Drama3 and
  Fish codec backports under `omlx/engine/tts_backends`; upstream revision and
  file hashes are in `PROVENANCE.json`, with upstream license retained.
- Drama3 reuses the Runtime's mlx-lm Qwen3.5 backbone and cache implementation.
  Existing oMLX attention/router/MoE kernels are unchanged.
- New loaders require local checkpoints and strict weight loading. MOSS's
  separate audio tokenizer is explicitly supplied through
  `dependency_checkpoints['OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano']`.
  Missing dependencies fail without Hub fallback.
- MOSS without a reference uses its supported `continuation` mode. Drama3
  instructions are encoded as inline tags, not the unsupported `instruct`
  argument. Reference cloning preserves the model-specific decoding pipeline.
- Stereo chunks are averaged to mono rather than flattened. Result sample rates
  are honored and mixed-rate/nonfinite chunks rejected.

## Evidence and reproduction

[Checkpoints and exact revisions](evidence/four-mlx-tts-20261119/checkpoints.local.json)
include temporary local cache paths; replace paths when replaying elsewhere.
All four models generated Chinese audio both without a reference and with the
same synthetic Zonos reference. Audio and per-run receipts are in
[evidence](evidence/four-mlx-tts-20261119). These are real Metal executions with
Hub offline, not mocked generation. Waveforms are nonempty and nonsilent.
No human listening score, ASR accuracy score, clone similarity, or emotional
controllability benchmark is claimed. Timings include warm filesystem/Metal
caches and are not cold-start performance benchmarks.

From this directory, with the normal Runtime dependencies available:

```sh
PYTHONPATH=.. HF_HUB_OFFLINE=1 ../.venv/bin/python -P scripts/evaluate_four_mlx_tts.py \
  --checkpoints docs/evidence/four-mlx-tts-20261119/checkpoints.local.json \
  --output /tmp/four-tts-evaluation --max-tokens 256
```

For the recorded run the shared venv had a preexisting broken editable
`mlx_audio` path. We used a clean export of the exact Runtime pin at
`/tmp/ai2apps-tts-pinned` via `PYTHONPATH=/tmp/ai2apps-tts-pinned:..`, without
modifying the shared venv or upgrading dependencies.

Add `--reference-audio PATH --reference-text TEXT` for cloning. The evaluation
script never downloads weights and emits an error receipt and nonzero exit code
when a backend fails.

## Validation and remaining release work

12 new targeted tests and 34 existing TTS sampling/reference/Worker tests passed.
The broader speech API run returned 112 passed, 2 failed, 39 teardown errors,
1 deselected: the errors and two failed tests report the existing
`PlatformRuntime.hook_execution` missing attribute during lifespan shutdown.
This run is not reported as fully green; unrelated Host lifecycle code was not
changed for this work.

Before making these available in Voice Studio, create/review their Model Package
capability and license declarations, add the corresponding Runtime capability
requirements, build/verify the Runtime, and install/test through the normal
Package/Worker path. No registry distribution IDs or release versions have been
invented during this evaluation. Do not advertise upstream features absent from
the MLX implementation: Zonos's full emotion/word controls, MOSS streaming, or
native speed control for Drama/Breeze. Emotion quality still needs a separate
listening evaluation. Model-weight licenses remain separate from the backend
code license; review Fish and Breeze restrictions before distribution.

## Follow-up: utterance emotion steering

Zonos3 now accepts `emotion` (`neutral`, `happy`, `scared`, `angry`, `sad`;
`fearful`/`afraid`/`fear` alias `scared`) and native `emotion_strength` 0–8
(default 2). Strength is a steering dose, not a probability or the Worker's
normalized 0–1 strength. No UI/Model Package mapping has been installed yet.
Official fixed mean-difference vectors are injected at attention-residual source
19 before bank insertion, on audio decode steps only, matching the official MLX
injection point. Neutral/zero do not inject; prompt prefill remains unmodified.
This is whole-utterance emotional steering, not word-span steering or full
official Studio control coverage. See the adjacent manifest for provenance.

Three models generated four takes each with identical Chinese text and synthetic
reference audio: neutral, happy, scared, angry. Zonos used strength 3.5; Drama
used inline cues; Breeze used Chinese instruction text. These settings are not
claimed to represent equal emotional intensity across models. There are 12 valid
nonsilent WAVs; 53 targeted tests passed. Subjective emotion and intelligibility
remain for user listening, not inferred merely from waveform differences.

[Open the listening comparison](evidence/tts-emotions-20261119/index.html).
Reproduce using `scripts/evaluate_tts_emotions.py` in the same pinned offline
environment described above. No Runtime or Model Package was published.
