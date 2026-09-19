#!/usr/bin/env python3
"""Animate a source portrait from a driving video using MLX LivePortrait."""

from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path

from .assets import resolve_model
from .geometry import align_face, paste_face
from .liveportrait import MLXLivePortrait
from .media import (
    VideoReader,
    VideoWriter,
    read_image_bgr,
    remux_source_audio,
    resize_bgr,
)
from .models import MLXSCRFD, MLXYuNet
from .native_liveportrait import NativeMLXLivePortrait
from .tracking import TemporalFaceTracker


def _area(detection) -> float:
    return float(
        (detection.bbox[2] - detection.bbox[0])
        * (detection.bbox[3] - detection.bbox[1])
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--driving-video", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--detector", choices=("scrfd", "yunet"), default="scrfd")
    parser.add_argument("--native-weights", type=Path)
    parser.add_argument("--dtype", choices=("fp32", "bf16"), default="fp32")
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--crop-only", action="store_true")
    args = parser.parse_args()

    source = read_image_bgr(args.source)
    if args.detector == "yunet":
        detector = MLXYuNet(
            resolve_model(args.models, "face_detection_yunet_2023mar.onnx")
        )
    else:
        detector = MLXSCRFD(resolve_model(args.models, "scrfd_2.5g_bnkps.onnx"))
    source_faces = detector.detect(source)
    if not source_faces:
        raise ValueError("source image must contain a detectable face")
    source_crop, source_matrix = align_face(
        source, max(source_faces, key=_area).landmarks, 256
    )
    pipeline = (
        NativeMLXLivePortrait(args.native_weights, dtype=args.dtype)
        if args.native_weights is not None
        else MLXLivePortrait(args.models)
    )
    source_state = pipeline.prepare_source(source_crop)

    capture = VideoReader(args.driving_video)
    fps = capture.fps
    output_size = (512, 512) if args.crop_only else (source.shape[1], source.shape[0])
    tracker = TemporalFaceTracker(smoothing=0.5, max_missed=2)
    frames = 0
    rendered = 0
    driving_anchor = None
    last_output = (
        resize_bgr(source_crop, (512, 512), interpolation="cubic")
        if args.crop_only
        else source.copy()
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    with tempfile.TemporaryDirectory(prefix="mlx-liveportrait-") as temporary:
        silent_path = Path(temporary) / "video.mp4"
        writer = VideoWriter(silent_path, fps, output_size)
        try:
            for driving_frame in capture:
                if args.max_frames and frames >= args.max_frames:
                    break
                tracks = tracker.update(detector.detect(driving_frame))
                visible = [track for track in tracks if track.missed == 0]
                if visible:
                    driving_crop, _ = align_face(
                        driving_frame,
                        max(visible, key=lambda item: _area(item)).landmarks,
                        256,
                    )
                    driving_state = pipeline.prepare_driving(driving_crop)
                    if driving_anchor is None:
                        driving_anchor = driving_state
                    generated = pipeline.drive_prepared(
                        source_state,
                        driving_state,
                        driving_anchor=driving_anchor,
                    )
                    if args.crop_only:
                        last_output = generated
                    else:
                        output_scale = generated.shape[1] / source_crop.shape[1]
                        last_output = paste_face(
                            source,
                            generated,
                            source_matrix * output_scale,
                            erosion_fraction=0.035,
                            blur_fraction=0.04,
                        )
                    rendered += 1
                writer.write(last_output)
                frames += 1
        finally:
            writer.close()
            capture.close()
        remux_source_audio(silent_path, args.driving_video, args.output)
    elapsed = time.perf_counter() - started
    print(
        json.dumps(
            {
                "output": str(args.output),
                "frames": frames,
                "rendered_frames": rendered,
                "seconds": elapsed,
                "effective_fps": frames / elapsed if elapsed else None,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
