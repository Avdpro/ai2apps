# MLX visual actor-replacement technical plan

## Outcome so far

The core models used by Rope/VisoMaster-style workflows can execute directly on
MLX/Metal. The experiment currently covers:

- SCRFD detection and five-point landmarks, plus MIT-licensed YuNet as the
  release-safe LivePortrait detector;
- ArcFace and SimSwap ArcFace identity embeddings;
- InSwapper 128 and SimSwap 512 face generation;
- XSeg face/obstacle masks;
- GFPGAN v1.4 restoration;
- LivePortrait appearance, motion, eye/lip retargeting, keypoint stitching, 3D
  feature warping, and SPADE rendering;
- image compositing and a minimal tracked video pipeline with audio remux.
- full-frame LivePortrait image paste-back and a source-image/driving-video
  pipeline with reusable source state and audio remux.

No Torch execution path is used. The LivePortrait 5D trilinear GridSample is
implemented from MLX gather and tensor arithmetic and runs on Metal.

## Product capability layers

1. `face.detect`: boxes, confidence, five landmarks, and stable Track IDs.
2. `face.identify`: normalized identity embeddings and similarity matching.
3. `face.swap`: universal one-shot actor replacement with native GhostV2 MLX.
4. `face.mask`: semantic face/obstacle protection with XSeg plus soft geometry.
5. `face.restore`: optional, strength-controlled GFPGAN post-processing.
6. `portrait.motion`: LivePortrait pose/expression extraction, retargeting, and
   rendering for expression repair or portrait animation.
7. `video.actor_replace`: per-track configuration, temporal geometry smoothing,
   original audio retention, resumable progress, and frame timestamps.

The API should expose capabilities rather than checkpoint names. A model Package
declares which capability and controls it implements. Unsupported controls must
either be rejected explicitly or returned with `applied: false`; they must not
silently pretend to run.

## Runtime decision

The current experiment loads ONNX only as a trusted conversion/reference input.
Production Packages should ship an oMLX bundle:

```text
model.omlx/
  graph.json
  weights.safetensors
```

The converter preserves tensor shapes, control-flow subgraphs, model inputs,
outputs, and operator attributes. The inference loader needs only MLX, NumPy,
Pillow, PyAV, SciPy, and safetensors. These were verified in the mounted
Runtime 1.6.2 distribution. The production path no longer imports OpenCV and
does not invoke an external `ffmpeg` executable. OpenCV remains a
development-only reference dependency. The Package does not need Python
`onnx`, `onnxruntime`, Torch, torchvision, CUDA, or CoreML.

Therefore the current evidence does **not** justify another Runtime release.
The exact embedded Python 3.11 from Runtime 1.6.2 encoded H.264 with PyAV and
remuxed the source AAC stream successfully. A Runtime update is warranted only
if a later fused Metal kernel is placed in the Runtime rather than in the
Package.

## Package split

Use separate installable Packages so installations download only the
capabilities they select:

- `omlx-face-swap-ghostv2`: GhostV2, CVLFace, detector, tracking, and masks;
  the only product-facing universal face-swap choice, requiring 16 GB unified
  memory or more.
- `omlx-face-swap-personalized`: MLX-native SAEHD/DFM-compatible extraction,
  training, checkpointing, and inference for a fixed trained identity; a
  separate Studio capability rather than a GhostV2 fallback.
- `omlx-face-restore`: GFPGAN and future restorers; optional post-processing.
- `omlx-liveportrait`: YuNet plus all motion/retargeting/rendering components;
  it must not depend on the restricted InsightFace checkpoints.

InSwapper and SimSwap remain experiment/reference implementations. They are
not selectable production modes and are never automatic low-memory fallbacks.

Checkpoints must remain external dual-source distributions. Do not duplicate a
shared detector or embedding checkpoint when the Package manager can resolve an
existing content-addressed asset.

## Remaining engineering gates

- Package the verified parser-free bundles after checkpoint terms are cleared;
  all 13 selected graphs now convert and their representative end-to-end
  outputs have exact image parity with the ONNX development loader.
- Replace the reference node interpreter with model-specialized, compiled NHWC
  blocks where profiling shows meaningful Python/layout overhead.
- Add color transfer, mouth/teeth protection, and foreground occlusion tests.
- Build a moving multi-person video corpus and measure Track ID switches,
  landmark jitter, identity similarity, temporal LPIPS, FPS, and peak memory.
- Finish the LivePortrait image/video orchestration math and validate expression
  transfer on consented test footage.
- Add cancellation, progress, bounded frame queues, crash recovery, and audio
  timestamp preservation.
- Complete source-license and checkpoint redistribution review before any public
  Package build or publication.

## Safety boundary

Actor replacement is dual-use. The product layer should require an explicit
user action, preserve provenance metadata where possible, offer visible
watermark/export labeling, and document that users must have the necessary
rights and consent. These controls do not belong in model math, but they are a
release gate for a consumer-facing workflow.
