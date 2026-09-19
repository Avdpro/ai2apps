# Validation log

Date: 2026-09-05
Hardware: Apple Silicon development Mac
Reference: ONNX Runtime 1.20.1 CPUExecutionProvider
MLX: repository environment, Metal device

The values below use the locked assets from `assets.lock.json`. Model loading is
excluded from warm timing. These are experiment measurements rather than a
Runtime compatibility promise.

## Tensor parity

| Model | Input | Maximum absolute error | Mean absolute error |
| --- | --- | ---: | ---: |
| ArcFace w600k_r50 | deterministic 112x112 tensor | 0.00000346 | 0.00000081 |
| SCRFD 2.5G | deterministic 320x320 tensor | 0.004128 across 9 outputs | 0.000892 worst-output mean |
| InSwapper 128 FP16 | aligned face and valid ArcFace/emap identity | 0.002702 | 0.000416 |
| XSeg | aligned face, 256x256 | 0.008464 | 0.000119 |
| SimSwap 512 | deterministic image/identity tensors | 0.022260 | 0.000673 |
| SimSwap ArcFace | deterministic 112x112 tensor | 0.00000109 | 0.00000028 |
| GFPGAN v1.4 | deterministic 512x512 tensor | 0.046946 | 0.001483 |
| LivePortrait appearance | deterministic 256x256 tensor | 0.261345 | 0.015392 |
| LivePortrait warping/SPADE | deterministic feature/keypoint tensors | 0.014557 | 0.000812 |

The InSwapper implementation stores weights and graph activations in FP16 but
uses FP32 convolution accumulation, then saturates to the finite FP16 range.
Without this behavior its first 1024-channel encoder convolution overflows on
MLX while the ONNX Runtime reference remains finite.

## Warm inference latency

Twenty measured iterations after two warm-ups:

| Model | ORT CPU median | MLX median | Median speed-up |
| --- | ---: | ---: | ---: |
| ArcFace w600k_r50 | 24.76 ms | 8.10 ms | 3.06x |
| SCRFD 2.5G, 320x320 | 4.34 ms | 3.78 ms | 1.15x |
| YuNet, 640x640 | 6.13 ms | 4.22 ms | 1.45x |
| InSwapper 128 FP16 | 507.88 ms | 45.00 ms | 11.29x |
| XSeg | 49.13 ms | 9.30 ms | 5.28x |
| SimSwap 512 | 369.92 ms | 67.37 ms | 5.49x |
| GFPGAN v1.4 | 562.48 ms | 92.32 ms | 6.09x |
| LivePortrait appearance | 96.48 ms | 10.21 ms | 9.45x |
| LivePortrait motion | 41.63 ms | 6.48 ms | 6.42x |
| LivePortrait warping/SPADE | 1774.43 ms | 131.72 ms | 13.47x |

The first end-to-end two-image run after models were loaded completed detection,
identity extraction, generation, warp, and blend in 104 ms. That run used a
640x640 detector canvas and should be repeated over a larger corpus before it
is treated as a stable throughput number.

## Current gates

- ArcFace tensor parity: passed.
- MIT-licensed YuNet replacement detector: passed. Across 12 raw outputs the
  maximum MLX error was `0.00000477`; on the six-face real image, MLX and
  OpenCV FaceDetectorYN produced identical boxes and landmarks and maximum
  score error `0.0000000596`.
- SCRFD raw tensor parity: passed provisionally; decoded real-image parity is
  also passed. Both backends found six faces at 640x640; maximum decoded box
  and landmark error was 0.0000611 pixels and maximum score error was
  0.000000119.
- InSwapper finite output and close FP16 parity: passed.
- XSeg semantic mask parity: passed; binary IoU at threshold 0.5 was 0.999789.
- SimSwap 512, its dedicated ArcFace encoder, and GFPGAN: passed tensor parity
  and end-to-end image generation.
- Identity evaluation at a fixed target landmark crop: target-to-source was
  0.0526 before replacement, 0.7468 with InSwapper, 0.4661 with SimSwap, and
  0.4687 with SimSwap plus 50% GFPGAN. InSwapper is the stronger identity mode;
  SimSwap is the higher-resolution texture mode.
- LivePortrait appearance, motion, warping/SPADE, eye retargeting, lip
  retargeting, and stitching graphs all execute in MLX. The three stitching
  graphs have maximum errors between 0.000000030 and 0.000000089.
- The custom 5D trilinear GridSample path is finite and close to the ORT output.
- LivePortrait full-frame image paste-back passed visually. The first absolute
  motion video exposed facial-shape distortion; replacing it with the official
  anchor-relative rotation, expression, scale, and translation formulation
  removed the first-frame distortion. The corrected five-frame smoke rendered
  every frame at 6.08 effective FPS at 1080x1438 output and retained AAC audio.
  Source appearance/keypoints and the first driving-frame anchor are reused.
- Single-image pipeline: passed visually on the upstream InsightFace test set.
- Tracking unit tests: passed.
- Video pipeline smoke: passed on a five-frame MP4 at 14.43 effective FPS,
  including persistent Track ID and AAC audio remux. A moving temporal-quality
  corpus remains pending.
- Checkpoint redistribution/license review: passed. The MIT-licensed native
  LivePortrait weights and YuNet detector bundle were published from immutable
  Hugging Face and ModelScope revisions as
  `dist_ai2apps_mlx_liveportrait_2bccacd9_v1`; full dual-download verification
  covered all 16 files before Package publication.
- License-safe LivePortrait detector path: passed with YuNet. A five-frame
  YuNet + LivePortrait Bundle-only video rendered at 6.26 effective FPS and
  retained AAC audio.
- Runtime 1.6.2 dependency probe: passed without a Runtime update. Its embedded
  Python 3.11 provides MLX, NumPy, Pillow, PyAV, SciPy, SoundFile, and
  safetensors, but not OpenCV. The inference path was therefore migrated away
  from OpenCV. The exact Runtime interpreter encoded H.264 and remuxed AAC via
  PyAV. A five-frame no-OpenCV LivePortrait smoke rendered every frame at 5.10
  effective FPS and retained both H.264 video and AAC audio.
- The corresponding no-OpenCV InSwapper regression replaced the selected
  tracked face in all five frames at 11.52 effective FPS and also produced
  H.264 plus copied AAC audio.
- A 60-frame, two-person moving/crossing-path synthetic stress clip retained
  exactly two detections in every frame. Each ground-truth trajectory kept one
  stable Track ID for all 60 frames, with zero ID switches. Replacing only
  explicit Track ID 1 completed all 60 960x540 frames at 15.11 effective FPS;
  Track ID 2 was left unselected. The silent-input branch produced a valid
  six-second H.264 MP4 without inventing an audio stream.
- LivePortrait processed the same 60-frame input without frame drops, reused
  source and anchor state, and rendered all 60 frames at 5.39 effective FPS.
  The output was a valid six-second H.264 MP4 with no spurious audio stream.
- The integrated specialized native FP32 LivePortrait engine processed the
  same 60 frames at 6.05 FPS, 12.2% faster than the graph baseline. Decoded
  H.264 frames differed from the graph output by mean 0.0731 intensity levels
  (worst-frame mean 0.0853). The corresponding full-frame JPEG comparison had
  mean difference 0.0137, maximum 9, and no values above 10.
- Explicit native BF16 reduced the same image render section from 199.9 ms to
  158.4 ms (20.8%). Its real-image mean difference from native FP32 was 0.0778,
  but the maximum was 53 and the deterministic stress test remained materially
  worse. BF16 is therefore an opt-in fast profile, not an automatic fallback.
- The prototype Model Worker adapter passed direct protocol-level image-edit
  and video-generation invocations against the staged checkpoint. It returned
  PNG/MP4 artifacts, five monotonic render progress updates, preserved AAC for
  the video, and reported requested/applied precision, motion multiplier,
  crop, and audio controls. Unsupported semantic controls are rejected with
  `unsupported_control` rather than silently ignored.
- A 60-frame adapter task cancelled during execution returned structured
  `generation_cancelled` / HTTP 409. First-load model construction is not
  interruptible inside MLX, but a cancellation received during it is honored
  immediately after construction and before frame inference begins.
- `stop()` plus `mx.clear_cache()` reduced allocator cache memory from 6.75 GiB
  to zero. Compiled MLX functions retained about 487 MiB of active allocations
  until Worker process exit; disabling compile reduced the retained active
  amount to about 165 MiB. The production lifecycle relies on the supervised
  Worker process exit for complete release and must avoid accumulating
  precision variants in one long-lived process.
- Focused geometry, media, tracking, bundle-integrity, and adapter-contract
  tests: 14 passed. Ruff and `git diff --check` passed for the experiment scope.
- The actor-replacement fast path now maps the source FP16 graph to BF16 so
  InSwapper convolutions no longer require per-layer FP32 overflow protection.
  Warm median model latency fell from 44.61 ms to 31.71 ms. Against the same
  ONNX Runtime CPU input this is an 18.98x median speed-up. Full-frame JPEG
  output differed from the compatible FP16 path by mean 0.0164 intensity
  levels; only 5 of 3,402,240 channel values differed by more than 10.
- InSwapper BF16 batch throughput was 34.33 images/s at batch 1, 50.84 at
  batch 4, and 64.50 at batch 8. Caching the invariant feather mask and limiting
  inverse warping/blending to the projected face ROI raised the final YuNet +
  two-frame detection interval + eight-frame inference batch path from 31.17
  to 40.60 effective FPS. Batch 16 reached 42.44 FPS. The optimized batch-8
  result is pixel-identical after H.264 decode to the former full-frame
  compositor (60/60 frames, mean/max absolute delta 0) and still replaces only
  explicit Track ID 1 in the 960x540 two-person stress clip.
- The Package-facing multipart Model Worker adapter completed the same 60-frame
  job in 1.58 seconds including model load, returned structured applied-control
  metadata, and correctly warned that the silent source contained no audio.
  Focused actor-replacement adapter, geometry, tracking, and media tests now
  pass 20/20.
- YuNet after the Pillow preprocessing migration still matched the OpenCV
  FaceDetectorYN reference on the regression portrait: one face in both paths,
  IoU 0.99733, maximum box error 0.247 px, landmark error 0.537 px, and score
  error 0.0000567. The small change is attributable to resize interpolation.

## Parser-free bundle

`export_bundle.py` converts ONNX graph metadata to compact JSON and all tensors
to safetensors. Both ArcFace and the control-flow-bearing SimSwap graph produced
bit-identical MLX outputs when loaded from the bundle (`max_abs = 0`). This
keeps Python `onnx` and ONNX Runtime out of the eventual inference Package.

All 13 locked graphs were converted successfully into a 1.7 GB parser-free
bundle set and passed manifest integrity verification. Complete end-to-end
InSwapper, SimSwap, and LivePortrait image outputs loaded only from bundles and
were pixel-identical to their raw-ONNX development runs (maximum and mean image
difference both zero). Representative bundle-only elapsed times after model
load were 113 ms for InSwapper, 233 ms for SimSwap, and 187 ms for a
LivePortrait crop render.
