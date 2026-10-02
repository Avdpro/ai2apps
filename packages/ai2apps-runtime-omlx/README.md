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

Version 1.7.13 bounds DeepSeek V4.1 long-Decode Metal resource lifetime. At the
existing per-token materialization boundary it evaluates persistent cache state
and releases completed resident-bank output graphs, without adding a GPU-to-CPU
readback. Model Worker streams now record failures and cancellations explicitly
and return structured SSE errors instead of marking truncated generations as
successful.

Version 1.8.0 enforces each conversational model Package's declared context
window across Chat Completions and Responses, for streaming and non-streaming
text, vision, and DeepSeek V4.1 paths. Requested output is capped to the space
remaining after the formatted prompt; requests that leave no generation space
fail before Decode. Legacy conversational Packages without a declaration use a
32K compatibility window.

Version 1.8.1 completes the session-scoped Engine Boost production path for
DeepSeek V4/V4.1, GLM-5.3, Qwen3.6 text and vision models, Ornith 1.5, and
Qwen3.8 Flash Next Cached-MoE. Natural preserves each model's exact routing;
Turbo and Blast apply the model-specific protected Top-N policy at token
boundaries. Worker usage and idle status expose the effective mode and bounded
route/cache counters without adding a generation-time Metal synchronization.

Version 1.8.2 adds bounded per-session, whole-turn SSD telemetry alongside the
existing rolling 10-token Decode window. The Runtime reports cumulative expert
loads, bytes read, routed-expert bytes, pressure, and severity for the active
turn; the Host can combine this idle-safe snapshot with Worker RSS sampling to
show a completed turn's average SSD pressure and peak Worker memory. Collection
reuses existing counters and does not add a generation-time Metal readback.

Version 1.8.3 carries the already-materialized rolling SSD window and whole-turn
average in the existing local Worker metrics stream, so Chat can update SSD
pressure while Decode is active without polling full engine stats or adding a
Metal synchronization. It also lets clients compute rolling Token Gen speed
from local monotonic receipt time when an engine output omits native generation
timestamps while continuing to report cumulative completion tokens.

Version 1.8.5 extends that telemetry contract to every shipped Cached-MoE
engine, including the dedicated DeepSeek V4.1 engine, GLM-5.3, Qwen3.6/Ornith,
and Qwen3.8 Flash Next. The V4.1 path establishes the Decode baseline after
Prefill, derives exact expert
loads from each resident bank's completed SSD bytes, and publishes both the
rolling 10-token window and whole-turn average by Session. The counters are
plain Python values updated at the existing completed-token boundary, so the
fix does not add an MLX evaluation or GPU-to-CPU synchronization. Pressure uses
completed Decode steps; the first token sampled from Prefill logits is excluded.
The Host now reports macOS physical footprint in addition to legacy RSS and
Chat uses the footprint for Worker memory, so Metal unified allocations are no
longer omitted from DeepSeek V4.1's displayed current and sampled peak memory.

Version 1.8.6 adds the `video_segmentation` Model Worker operation and the
`video-segmentation` Runtime capability. It reuses the existing MLX, NumPy,
SciPy, Pillow, PyAV, Metal, and video-codec layers; no new native dependency is
added. This is the minimum Runtime required by the SAM 2.1 Video Cutout MLX
Package.


## Runtime 1.8.7

Adds the dedicated `video_upscaling` Model Worker operation at `/v1/videos/upscalings` and its bounded capability schema. Native dependencies are unchanged from 1.8.6. Host model catalog support requires the corresponding Desktop source update.
