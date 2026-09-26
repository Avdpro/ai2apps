# AI2Apps oMLX Runtime

Official `inference_provider` Service Package for macOS arm64. It owns CPython,
MLX/oMLX, the Model Worker framework, Cached-MoE implementations, and all
native inference libraries. Version 1.6 adds the dedicated
`audio-detailed-transcription-v1` worker capability for subtitle and meeting
pipelines without changing Chat's `audio-stt` contract. Version 1.6.1 adds
request-scoped reference audio plus voice-conversion controls to
`POST /v1/audio/process`; the `audio-reference-input-v1` capability lets model
Packages require that transport contract explicitly. It contains no checkpoint
or instance data.

Version 1.6.2 adds the bounded, cancellable `audio_voice_training` Worker
operation and `POST /v1/audio/voices/train` transport. The explicit
`audio-voice-training-v1` capability lets a model Package require this protocol
before advertising on-device voice training. FP16 is the default RVC training
precision; BF16 and FP32 remain explicit alternatives.

Version 1.7.0 adds the verified `ai2apps.ssd-checkpoint/v1` contract. Cache-MoE
model Packages can now activate a compact backbone and its bundled expert store
directly, without rebuilding or retaining a second expert copy during install.
The Runtime validates the complete file manifest, metadata digests, family and
layout before exposing the checkpoint to Full or Cached execution.

Version 1.7.1 treats Hub-only `.gitattributes` metadata as optional when an
older signed SSD marker lists it but the verified Checkpoint Distribution omits
it. Runtime payload, metadata digest, expert-store and layout validation remain
strict. This allows the published DeepSeek V4.1 SSD distribution to start from
the machine-shared checkpoint cache without another model download.

Version 1.7.2 restores exact Qwen3.6/Ornith Full execution for SSD-ready
checkpoints: all 256 routed experts are injected from the external expert store
in canonical expert-ID order even when the Scope profile only ranks cache tiers.

Version 1.7.3 adds authenticated, non-queued Engine Boost control for an already
loaded Cached-MoE Worker and final Chat streaming usage with native throughput
or explicitly marked Worker-observed timing estimates. Model Packages and
checkpoint bytes are unchanged; the Host must also support Package boost routing.

Version 1.7.4 recognizes the current `ai2apps-ssd-checkpoint` layout when
estimating DeepSeek V4 Cache-MoE memory tiers and when selecting Full external
expert injection. Restricted App processes also detect physical memory through
POSIX page counts when spawning `sysctl` is unavailable. Existing model
Packages and checkpoint bytes are unchanged.

Version 1.7.5 adds the signed `ai2apps.reasoning/v1` Model Package contract.
Required-reasoning models force thinking on, and tagged reasoning is emitted
through the structured reasoning channel instead of leaking into answer text.

Version 1.7.6 fixes the dedicated DeepSeek V4.1 stream decoder. It preserves
the model's special `<think>` boundaries, withholds incomplete UTF-8 suffixes,
and emits append-only deltas so reasoning cannot be replayed into answer text.

Version 1.7.7 adds the versioned pure-Python
`ai2apps.model-stream-codec/v1` extension point. Existing model Packages keep
the Runtime decoder unchanged; future signed model Packages may override only
model-specific token-prefix and append-only delta policy. Package build and
inspection now reject native-code payloads in every Model Worker Package, so
MLX, tokenizer implementations, Metal kernels and executors remain Runtime-only.

Version 1.7.8 accepts the Qwen3.6 Tiered SSD reader's already separated
resident and tail expert banks in the text-model sanitizer. This fixes valid
Top120 + Tail24 checkpoints being rejected as though the 120-row resident bank
were an incomplete combined bank.

Version 1.7.9 adds native MLX VoxCPM2 and IndexTTS 2.5 execution. VoxCPM2 is
provided by the pinned MLX-Audio 0.5.5 source revision. IndexTTS 2.5 uses the
vendored, Torch-free WIndexTTS MLX inference path with structured emotion
vectors, native duration control, reference-audio cloning, and offline WeText
normalization for Chinese and English.

The native payload is deliberately Runtime-only: it embeds the system Model
Worker source rather than the full AI2Apps Host tree, omits Python test/cache
content and xgrammar's link-time static archive, and excludes Host-owned
ModelScope, Selenium, and MCP clients. MLX, MLX-LM/VLM, MLX Audio, both required
ONNX runtimes, PyAV, and the xgrammar runtime dylib remain bundled.

Build a local ad-hoc development artifact:

```bash
AI2APPS_ALLOW_DEVELOPMENT_RUNTIME=1 \
  .venv/bin/python scripts/build_omlx_runtime_package.py \
  --source packages/ai2apps-runtime-omlx \
  --layers packaging/_export \
  --sign-identity -
```

For a release artifact, first run `scripts/build_omlx_runtime_dmg.py` with the
AI2Apps Developer ID Application identity. The release flow is deliberately
two-phase: notarize and staple that DMG, then pass it to the Package builder with
`--prepared-dmg --prepared-signing developer-id --team-id 84XL5V265N` while
signing the outer Package with the official AI2Apps Publisher key. An
unstapled Developer ID DMG is never accepted into a release Package.

Version 1.7.10 fixes CosyVoice reference preprocessing on macOS Hardened Runtime. The private Python worker receives the executable-memory entitlement required by LLVM/Numba; library validation remains enabled.

Version 1.7.12 keeps Direct Prefill for compute-ready six-segment DeepSeek V4
expert stores and routes stores with required quantization biases through the
asynchronous legacy Prefill loader. A stale Direct request marker now safely
falls back after validating its layer and expert IDs.
