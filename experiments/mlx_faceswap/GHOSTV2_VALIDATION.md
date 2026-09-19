# MLX GhostV2 validation

Date: 2026-09-05

## Decision

GhostV2 is the recommended default **quality** face-swap engine on supported
Apple Silicon Macs. The native MLX path preserves source identity and fine
facial detail much better than the current InSwapper 128 path while sustaining
about 40 FPS with per-frame detection and 54 FPS for buffered export on the
validation Mac. GhostV2 is the single product-facing universal engine;
InSwapper remains only as a development comparison and compatibility test.
Machines below the supported memory floor receive an explicit resource error
instead of a silent engine downgrade.

Do not enable naive aligned-frame EMA by default. It reduces identity variance
but removes detail and introduces motion lag. The unsmoothed GhostV2 output was
already more stable in identity than the InSwapper comparison.

## Provenance and license

- Upstream: `dimitribarbot/ghostv2`
- Source commit: `bc53ed086dbe8ea38e165aec7aaac90d1749a335`
- Upstream states that its source code and pretrained models are BSD-3-Clause.
- Generator SHA-256:
  `6e45013c280f0afb7ad2760e6d2f80f4e754e6f4096f11edf0faf8dec29f4c22`
- CVLFace ViT SHA-256:
  `5fafd6b7d599a3ede5fac5bd1d01ad05e9e93e89b39b7687d4a3bc93ff2aebc0`

The evaluation uses the GhostV2 generator and CVLFace identity encoder. Face
detection, alignment, tracking, and ROI paste-back use the existing MLX YuNet
pipeline so the comparison measures the replaceable face-generation core.

## MLX conversion

The official Safetensors checkpoints were loaded into their official PyTorch
modules, exported at ONNX opset 16, converted to FP16, and packaged as
parser-free `ai2apps.omlx.graph` bundles.

| Graph | FP16 size | FP16 ONNX SHA-256 | oMLX weights SHA-256 |
| --- | ---: | --- | --- |
| CVLFace ViT | 219 MiB | `ab28f254c5855012a25e667d0e912eb920e2a9e1245a11dc52af625993e349ea` | `7272be8745938ee2c4f492a62f095edabf91a83e860f6e8ee6e09b1b5d1bc54e` |
| GhostV2 generator | 352 MiB | `f00e31ffd1f08d78e4cd95d6a6f35d2f9351e43d32af6edf9cb4f4cf4c81f93c` | `4cbcbee5e4f7c5469a4699b35c51904fd94b3f07503ef587dfc3bcffdfa622ef` |

The conversion exposed an ONNX compatibility bug: the MLX executor ignored
`Resize.coordinate_transformation_mode=align_corners`. Honoring that attribute
reduced generator mean pixel error from `12.762/255` to `0.066/255`.

The final generator is a native NHWC MLX implementation rather than an ONNX
graph interpreter. Its converter transposes convolution weights once and folds
all 13 encoder BatchNorm layers into their Conv/ConvTranspose weights. The
native FP16 generator is 352 MiB with SHA-256
`5d55bbcaefd5aa2a5068c399c2fee5fcd765a08a36708314795839e296d3d587`.

## Numerical parity

Official aligned `source1 -> target1`, compared with official Torch MPS:

| Path | Identity cosine | Mean pixel error | Tensor mean absolute error |
| --- | ---: | ---: | ---: |
| MLX FP32 | 0.9999983 | 0.061 / 255 | 0.000482 |
| MLX FP16 | 0.9999968 | 0.073 / 255 | 0.000591 |
| MLX BF16 | 0.9998234 | 0.377 / 255 | 0.002965 |

With the official Torch identity vector, the native FP16 generator has tensor
mean absolute error `0.000627` and RMSE `0.001176` against Torch MPS.

FP16 is the default quality precision. BF16 remains visually close and is a
valid lower-memory/performance profile.

## Quality comparison

Independent ArcFace measurements were used only as an evaluation metric. The
GhostV2 production path itself uses CVLFace and does not need the InsightFace
checkpoint.

On the 60-frame two-person motion fixture:

| Engine | Identity mean | Identity std (lower is steadier) | Detail score | Excess temporal MAE |
| --- | ---: | ---: | ---: | ---: |
| InSwapper MLX BF16 | 0.1911 | 0.2130 | 118.16 | 0.0425 |
| GhostV2 official Torch MPS | 0.5848 | 0.0720 | 137.15 | 0.0939 |
| GhostV2 MLX FP16 | 0.5840 | 0.0707 | 137.60 | 0.0939 |
| GhostV2 MLX BF16 | 0.5839 | 0.0716 | 137.24 | 0.0939 |
| Native MLX FP16, detect/1 | 0.6199 | 0.0294 | 101.20 | 0.0366 |
| Native MLX FP16, detect/2 + prediction | 0.6158 | 0.0305 | 110.11 | 0.0654 |

The excess-temporal metric is sensitive to genuine expression/detail changes,
so it must not be read as a pure flicker score. Frame inspection and identity
variance show that GhostV2 is stable; future evaluation should add optical-flow
warped temporal LPIPS on real footage.

The native rows use geometry evaluated with the same detection schedule as the
generation run. Constant-velocity landmark prediction substantially improves
the skipped frames compared with reusing stale landmarks.

Static cross-sex, cross-age, facial-hair, and expression tests showed materially
sharper eyes, skin detail, wrinkles, and facial hair than InSwapper. Remaining
weaknesses are edge/color matching, difficult hairlines, occlusion, extreme
profiles, and the lack of a learned semantic face mask in this minimal path.

## Performance

Validation hardware: Apple M5 Max, 128 GB unified memory. Generated face size:
256x256. Video fixture: 960x540, one selected face, YuNet detection, and ROI
compositing. Detection interval and batch size are shown per row.

| Path | Core warm FPS | End-to-end FPS | Peak MLX memory |
| --- | ---: | ---: | ---: |
| Official Torch MPS | 52.9 | 33.7 | not measured by MLX |
| Generic MLX FP16 compiled | 44.1 | 29.77 | 1.82 GB |
| Native MLX FP16, batch 1, detect/2 | 66.8 | 34.44 | 1.39 GB generator-only |
| Native MLX FP16, batch 2, detect/1 | — | 39.91 | 2.08 GB full pipeline |
| Native MLX FP16, batch 2, detect/2 + prediction | — | 45.64 | 2.08 GB full pipeline |
| Native MLX FP16, batch 8, detect/2 + prediction | — | 53.07 | 2.66 GB full pipeline |

At 1920x1080, batch 2 with detection every frame reaches 25.49 FPS. Detection
every second frame plus landmark-velocity prediction reaches 29.88 FPS. Batch 8
file export with prediction reaches 32.13 FPS. The 256x256 GhostV2 generator is no longer the
1080p bottleneck; full-frame detection, decode, compositing, and encode dominate.

The generic graph and Torch MPS paths scale poorly with batching, while the
native MLX path benefits substantially. Shader compilation is cached; a truly
fresh machine should expect an additional first-run compilation pause.
Package/UI integration should preload the model after selection and expose a
ready state.

## Product defaults

1. Default interactive mode on machines with at least 16 GB unified memory:
   native GhostV2 MLX FP16, batch 2, detection every frame. This buffers one
   extra frame but retains about 40 FPS throughput and the best tracking.
2. Lowest-latency camera preview: native GhostV2 MLX FP16, batch 1.
3. 1080p real-time preview: native GhostV2 MLX FP16, batch 2, detection
   interval 2, with landmark-velocity prediction between detections.
4. Fast file export: native GhostV2 MLX FP16, batch 8, detection interval 2.
   Quality-first export may detect every frame because it is not latency bound.
5. Minimum supported configuration: 16 GB unified memory. Do not expose an
   8 GB InSwapper product tier and do not silently change engines under memory
   pressure. Reject the job before loading weights with the measured required
   and available memory in the error. Native BF16 did not outperform FP16 and
   is not a fallback on this hardware.
6. Do not silently switch identities or targets when tracking confidence drops;
   preserve the selected track and pass through the original frame on loss.
7. Before Package release, add a semantic face/hair mask, color matching,
   optical-flow video evaluation, checkpoint dual-source distribution, and
   explicit abuse/consent UX.

## Reproduction entry points

- `benchmark_ghostv2_torch.py`: official core baseline and intermediate tensors.
- `export_ghostv2_onnx.py`: official PyTorch to ONNX export.
- `convert_onnx_float16.py`: deterministic FP16 graph conversion.
- `validate_ghostv2_mlx.py`: numerical parity and compiled performance.
- `run_ghostv2_video_mlx.py`: end-to-end MLX video pipeline.
- `native_ghostv2/convert.py`: BN-fused NHWC native-weight conversion.
- `native_ghostv2/model.py`: native compiled MLX AAD generator.
- `native_ghostv2/validate.py`: native numerical and core-speed validation.
- `evaluate_swap_identity.py`: static independent identity comparison.
- `evaluate_video_stability.py`: video identity/detail/temporal comparison.

## Recorded benchmark commands

Native weight conversion:

```bash
.venv/bin/python -m experiments.mlx_faceswap.native_ghostv2.convert \
  /private/tmp/ghostv2-audit/weights/GhostV2/G_unet_2blocks.safetensors \
  /private/tmp/ghostv2-native-mlx
```

Native core parity and speed:

```bash
.venv/bin/python -m experiments.mlx_faceswap.native_ghostv2.validate \
  --model /private/tmp/ghostv2-native-mlx \
  --target /private/tmp/ghostv2-audit/examples/images/training_insightface_v2/target1.png \
  --embedding /private/tmp/ghostv2_source1_embedding_mps.npy \
  --reference /private/tmp/ghostv2_source1_target1_tensor_mps.npy \
  --output /private/tmp/ghostv2_native_source1_target1_fp16.png \
  --precision fp16 --runs 5
```

Default interactive video mode:

```bash
.venv/bin/python -m experiments.mlx_faceswap.run_ghostv2_video_mlx \
  --models /private/tmp/ghostv2-omlx-fp16 \
  --native-generator /private/tmp/ghostv2-native-mlx \
  --detector-model /private/tmp/mlx-faceswap-bundles.vkdVqH/face_detection_yunet_2023mar.omlx \
  --source /private/tmp/ai2apps-fasterliveportrait-mlx-audit/assets/examples/source/s0.jpg \
  --video /private/tmp/mlx_faceswap_two_person_motion.mp4 \
  --output /private/tmp/ghostv2_native_interactive.mp4 \
  --precision fp16 --batch-size 2 --detection-interval 1 --max-frames 60
```
