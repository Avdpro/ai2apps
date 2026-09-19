# AI2Apps MLX visual replacement Package design

Date: 2026-09-05

## Release order

1. `ai2apps/model-liveportrait-mlx`: official LivePortrait human weights plus
   MIT YuNet. This is the first public candidate.
2. `ai2apps/model-face-swap-mlx`: native GhostV2 FP16, CVLFace identity input,
   tracking, and optional semantic mask. It is the sole universal actor-swap
   Package exposed to users and requires at least 16 GiB unified memory.
3. `ai2apps/model-face-swap-personalized-mlx`: later Studio Package for
   MLX-native SAEHD/DFM-compatible dataset preparation, resumable fixed-identity
   training, export, and inference. It complements GhostV2; it is not a
   low-memory fallback.
4. `ai2apps/model-face-restore-mlx`: optional GFPGAN restoration after the exact
   checkpoint conversion provenance and notices are verified.

All four depend on `ai2apps/runtime-omlx >=1.6.2,<2.0.0`. No Runtime upgrade is
needed. Model weights remain in signed, dual-source checkpoint distributions
and are not embedded in `.ai2service` archives.

## Capability-facing API

Checkpoint names are implementation metadata, not API choices. Callers select
stable operations and modes:

| Operation | Required inputs | Native controls | Output |
| --- | --- | --- | --- |
| `portrait.animate.image` | source portrait, driving image | `motion_mode`, `motion_multiplier`, `crop_only` | PNG/JPEG artifact |
| `portrait.animate.video` | source portrait, driving video | same controls plus `audio_output_mode` | H.264 MP4 artifact |
| `actor.replace.image` | identity image, target image | `track`, `identity/detail`, `mask`, `restore_strength` | PNG/JPEG artifact |
| `actor.replace.video` | identity image, target video | same controls plus Track ID and audio mode | H.264 MP4 artifact |

The initial LivePortrait video request maps to Model Worker
`video_generation` and uses multipart parts. Its normalized payload is:

```json
{
  "model": "ai2apps/MLX-LivePortrait",
  "inputs": {
    "reference_image": {"part_name": "source"},
    "reference_video": {"part_name": "driving"}
  },
  "parameters": {
    "motion_mode": "relative",
    "motion_multiplier": 1.0,
    "crop_only": false,
    "audio_output_mode": "preserve_driving_audio",
    "output_format": "mp4"
  }
}
```

The Package declares the combination as `reference_image + reference_video`,
H.264 output, optional AAC preservation, phase progress, cancellation, and one
concurrent job per Metal device. It does not advertise text prompting,
generated audio, masks, first/last-frame conditioning, or resumability.

The image operation maps to `image_edit`; actor replacement uses the same
multipart conventions with `reference_image` as identity and the primary image
or `source_video` as the target media.

## Control result contract

Every successful result includes machine-readable control resolution:

```json
{
  "mode": "relative",
  "applied_controls": {
    "motion_multiplier": {"requested": 1.0, "applied": 1.0},
    "audio_output_mode": {
      "requested": "preserve_driving_audio",
      "applied": "preserve_driving_audio"
    }
  },
  "warnings": []
}
```

Compatibility values may be normalized only when the result reports the
requested and applied value. A control that changes semantic intent is rejected
with `unsupported_control`; it is never silently ignored. Examples:

- LivePortrait rejects identity-strength, face-restoration, and semantic-mask
  controls because they belong to actor replacement.
- Actor replacement rejects legacy `identity`/`detail` engine-selection values;
  the universal operation resolves to GhostV2. A personalized model is selected
  through a separate trained-model asset, not by silently switching engines.
- `preserve_driving_audio` rejects input without an audio stream only when the
  caller marked it required; `auto` may return silent video with a warning.
- Track selection rejects an unknown explicit Track ID rather than replacing
  the largest face.

## Checkpoint layout

The LivePortrait checkpoint should use:

```text
ai2apps-checkpoint.json
conversion-receipt.json
models/
  face_detection_yunet_2023mar.omlx/
  appearance_feature_extractor.omlx/
  motion_extractor.omlx/
  stitching.omlx/
  stitching_eye.omlx/
  stitching_lip.omlx/
  warping_spade.omlx/
LICENSE
NOTICE.md
```

`ai2apps-checkpoint.json` binds the schema, official source revision, converter
revision, per-file hashes, supported precision profiles, and model roles. The
default profile remains FP32. BF16 may be offered as an explicit speed mode;
FP16 motion must be rejected because the audit produced non-finite tensors.

The preferred Package layout uses the seven directly converted native MLX
weight files from `convert_official_liveportrait.py` with
`NativeMLXLivePortrait`. The parser-free graph bundles remain the independent
release oracle and conversion baseline.

## Resource and transport limits

- Minimum recommendation: 16 GiB unified memory for GhostV2 or 512-pixel
  LivePortrait; 24 GiB is the comfortable tier for video plus decode/encode
  buffers. An unsupported machine is rejected before model loading; there is
  no 8 GiB InSwapper fallback.
- Model state is lazy-loaded and retained for sequential jobs; `stop()` drops
  references and calls `mx.clear_cache()`. The supervised Worker process exit
  is the hard release boundary for MLX compiled-function allocations.
- Frames are decoded, inferred, and encoded with a bounded queue;
  the complete video is never resident in memory. Actor replacement batches up
  to eight aligned 128x128 faces for Metal inference while retaining only the
  corresponding bounded set of full frames.
- Runtime 1.6.2 Pillow/PyAV/SciPy are sufficient. OpenCV, ONNX Runtime, Torch,
  and external ffmpeg are build/reference dependencies only.
- Model Worker currently caps each multipart file at 100 MiB. That is adequate
  for Package smoke tests but too small for general film workflows. Raising the
  limit or using brokered artifact references is an App/Host API follow-up, not
  a model or Runtime requirement.

## Remaining release gates

1. Create byte-identical Hugging Face and ModelScope checkpoint revisions.
2. Build and publish the signed checkpoint distribution; only then place its
   real `distribution_id` in the Package manifests.
3. Build the Package with the standard signed-artifact builder and run a real
   installed Managed Service Sandbox smoke test.
4. Validate cancellation, audio timestamps, malformed media, missing faces,
   multi-person Track IDs, memory release, and a longer moving-video corpus.
5. Publish only after explicit authorization for the checkpoint upload and the
   named Package/version.
