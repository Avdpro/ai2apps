# MLX Face-Swap Experiment

GhostV2 quality, parity, and video-performance results are recorded in
[`GHOSTV2_VALIDATION.md`](GHOSTV2_VALIDATION.md). It is the recommended default
and the only product-facing universal face-swap engine. The original InSwapper
path remains a development parity and benchmark reference; it is not an
automatic low-memory fallback.

The separate fixed-identity training track is described in
[`PERSONALIZED_TRAINING_PLAN.md`](PERSONALIZED_TRAINING_PLAN.md). It targets an
MLX-native SAEHD/DFM-compatible workflow for users who are willing to train a
dedicated actor model rather than use one-shot identity transfer.

This directory develops the core face-replacement pipeline independently from
the AI2Apps App and Runtime. The staged target is:

1. ArcFace identity embedding parity;
2. SCRFD face detection and five-point landmark parity;
3. InSwapper 128 single-frame replacement parity;
4. alignment, mask, compositing, tracking, and temporal stability;
5. evaluation of SimSwap 512, restorers, and LivePortrait.

All five stages now have executable MLX baselines. See `TECHNICAL_PLAN.md` for
the proposed capability and Package boundaries.

LivePortrait has two independent MLX engines: the auditable parser-free graph
oracle and the faster specialized `NativeMLXLivePortrait`. The native engine
uses weights reproducibly converted from the pinned official checkpoint; pass
`--native-weights /path/to/converted/weights` to either LivePortrait CLI.

`onnx_mlx.py` is intentionally a constrained executor rather than a general
ONNX implementation. It accepts only operators found in the locked model
graphs. This creates an auditable numerical baseline before model-specific
fusion and layout optimization.

## Assets

Model sources and SHA-256 values are fixed in `assets.lock.json`. Downloaded
checkpoints are not committed. The current weights are restricted to local
experimentation until their separate model terms and redistribution rights are
reviewed.

The current local test cache is expected at
`/private/tmp/ai2apps-faceswap-models`; callers may use any path after verifying
the hash.

## Parity check

Run from the repository root with the repository virtual environment:

```bash
./.venv/bin/python -m experiments.mlx_faceswap.validate_parity \
  arcface /private/tmp/ai2apps-faceswap-models/w600k_r50.onnx
```

The script reports output-wise maximum and mean absolute error against ONNX
Runtime CPU. Timings are cold-start diagnostic values, not final benchmarks.

Warm latency can be measured with `benchmark.py`. `run_image_swap.py` executes
the complete single-frame path, while `run_video_swap.py` adds persistent Track
IDs, landmark smoothing, short detection-gap tolerance, and audio remuxing.
`run_liveportrait_image.py` supports crop-only output or full-frame paste-back;
`run_liveportrait_video.py` reuses the source appearance features across all
driving frames and retains the driving video's audio stream. Runtime-facing
image, geometry, video encode, and audio remux use Pillow/NumPy/SciPy/PyAV, so
OpenCV and an external `ffmpeg` binary are not production dependencies.

GFPGAN is deliberately disabled by default. Pass `--restore-strength` between
0 and 1 to the InSwapper or SimSwap CLIs when restoration is wanted. This
avoids silently changing identity/detail just because a restorer checkpoint is
installed.

Measured results and open gates are recorded in `VALIDATION.md`.

For Package/runtime use, convert an ONNX source in the trusted build environment:

```bash
./.venv/bin/python -m experiments.mlx_faceswap.export_bundle \
  /path/to/model.onnx /path/to/model.omlx
```

The resulting inference bundle does not require the Python ONNX parser.
`export_all_bundles.py` converts every locally present locked asset and validates
the source hash. Every bundle includes `bundle.json` with source, graph, and
weight hashes; verify these before packaging with:

```bash
./.venv/bin/python -m experiments.mlx_faceswap.verify_bundles \
  /path/to/bundles/*.omlx
```

The runtime CLIs prefer complete `.omlx/` directories and only fall back to
raw ONNX in the trusted development environment.
