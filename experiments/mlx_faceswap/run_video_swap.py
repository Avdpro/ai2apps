#!/usr/bin/env python3
"""Experimental MLX video face replacement with temporal tracking."""

from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path

from .assets import resolve_model
from .media import VideoReader, VideoWriter, read_image_bgr, remux_source_audio
from .models import MLXFaceSwapPipeline
from .tracking import FaceTrack, TemporalFaceTracker


def _area(track: FaceTrack) -> float:
    return max(0.0, float(track.bbox[2] - track.bbox[0])) * max(
        0.0, float(track.bbox[3] - track.bbox[1])
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--track-id", type=int)
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--restore-strength", type=float, default=0.0)
    parser.add_argument(
        "--swapper-precision",
        choices=("fp16_compatible", "bf16"),
        default="fp16_compatible",
    )
    parser.add_argument(
        "--mask-mode",
        choices=("feather", "semantic"),
        default="feather",
        help="Use the fast geometric feather mask or the optional XSeg mask.",
    )
    parser.add_argument(
        "--detector", choices=("yunet", "scrfd"), default="yunet"
    )
    parser.add_argument(
        "--detection-interval",
        type=int,
        default=1,
        help="Run face detection every N frames and reuse the tracked geometry between detections.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="Batch aligned target faces for Metal inference.",
    )
    args = parser.parse_args()
    if args.detection_interval < 1 or args.detection_interval > 8:
        parser.error("--detection-interval must be between 1 and 8")
    if args.batch_size < 1 or args.batch_size > 16:
        parser.error("--batch-size must be between 1 and 16")

    source = read_image_bgr(args.source)
    pipeline = MLXFaceSwapPipeline(
        resolve_model(
            args.models,
            (
                "face_detection_yunet_2023mar.onnx"
                if args.detector == "yunet"
                else "scrfd_2.5g_bnkps.onnx"
            ),
        ),
        resolve_model(args.models, "w600k_r50.onnx"),
        resolve_model(args.models, "inswapper_128.fp16.onnx"),
        (
            resolve_model(args.models, "XSeg_model.onnx", optional=True)
            if args.mask_mode == "semantic"
            else None
        ),
        resolve_model(args.models, "GFPGANv1.4.onnx", optional=True)
        if args.restore_strength > 0
        else None,
        restoration_strength=args.restore_strength,
        swapper_precision=args.swapper_precision,
        detector_kind=args.detector,
    )
    identity, _ = pipeline.prepare_identity(source)
    capture = VideoReader(args.video)
    fps, width, height = capture.fps, capture.width, capture.height
    tracker = TemporalFaceTracker()
    chosen_track = args.track_id
    frames = 0
    detect_seconds = 0.0
    swap_seconds = 0.0
    encode_seconds = 0.0
    started = time.perf_counter()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mlx-faceswap-") as temporary:
        silent_path = Path(temporary) / "video.mp4"
        writer = VideoWriter(silent_path, fps, (width, height))
        pending: list[tuple[object, object | None]] = []

        def flush_pending() -> None:
            nonlocal swap_seconds, encode_seconds
            if not pending:
                return
            selected = [
                (frame, detection)
                for frame, detection in pending
                if detection is not None
            ]
            stage_started = time.perf_counter()
            swapped = pipeline.swap_detections_batch(selected, identity)
            swap_seconds += time.perf_counter() - stage_started
            swapped_iter = iter(swapped)
            stage_started = time.perf_counter()
            for frame, detection in pending:
                writer.write(next(swapped_iter) if detection is not None else frame)
            encode_seconds += time.perf_counter() - stage_started
            pending.clear()

        try:
            for frame in capture:
                if args.max_frames and frames >= args.max_frames:
                    break
                if frames % args.detection_interval == 0:
                    stage_started = time.perf_counter()
                    detections = pipeline.detector.detect(frame)
                    detect_seconds += time.perf_counter() - stage_started
                    tracks = tracker.update(detections)
                else:
                    tracks = tracker.tracks
                visible = [track for track in tracks if track.missed == 0]
                if chosen_track is None and visible:
                    chosen_track = max(visible, key=_area).track_id
                selected = next(
                    (track for track in tracks if track.track_id == chosen_track), None
                )
                detection = (
                    selected.detection()
                    if selected is not None and selected.missed <= tracker.max_missed
                    else None
                )
                pending.append((frame, detection))
                frames += 1
                if len(pending) >= args.batch_size:
                    flush_pending()
            flush_pending()
        finally:
            writer.close()
            capture.close()
        remux_source_audio(silent_path, args.video, args.output)
    elapsed = time.perf_counter() - started
    print(
        json.dumps(
            {
                "output": str(args.output),
                "frames": frames,
                "seconds": elapsed,
                "effective_fps": frames / elapsed if elapsed else None,
                "track_id": chosen_track,
                "mask_mode": args.mask_mode,
                "swapper_precision": args.swapper_precision,
                "detector": args.detector,
                "detection_interval": args.detection_interval,
                "batch_size": args.batch_size,
                "stage_seconds": {
                    "detection": detect_seconds,
                    "swap_and_composite": swap_seconds,
                    "encode": encode_seconds,
                    "other_and_remux": max(
                        0.0,
                        elapsed - detect_seconds - swap_seconds - encode_seconds,
                    ),
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
