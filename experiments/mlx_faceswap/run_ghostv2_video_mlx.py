#!/usr/bin/env python3
"""Run the complete parser-free MLX GhostV2 video pipeline."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import mlx.core as mx

from .geometry import align_face, paste_face
from .ghostv2 import MLXGhostV2
from .media import VideoReader, VideoWriter, read_image_bgr
from .models import MLXYuNet
from .tracking import FaceTrack, TemporalFaceTracker


def _area(value) -> float:
    bbox = value.bbox
    return max(0.0, float(bbox[2] - bbox[0])) * max(
        0.0, float(bbox[3] - bbox[1])
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--detector-model", type=Path, required=True)
    parser.add_argument("--native-generator", type=Path)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--precision", choices=("fp16", "bf16"), default="fp16")
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument(
        "--video-codec",
        choices=("h264_videotoolbox", "libx264"),
        default="libx264",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=2,
        help="Two-frame batching balances real-time latency and throughput.",
    )
    parser.add_argument(
        "--detection-interval",
        type=int,
        default=1,
        help="Detect every frame by default for the most stable tracking.",
    )
    parser.add_argument("--velocity-smoothing", type=float, default=0.5)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 16:
        parser.error("--batch-size must be between 1 and 16")
    if not 1 <= args.detection_interval <= 8:
        parser.error("--detection-interval must be between 1 and 8")
    if not 0.0 <= args.velocity_smoothing <= 1.0:
        parser.error("--velocity-smoothing must be between 0 and 1")

    mx.reset_peak_memory()
    process_started = time.perf_counter()
    detector = MLXYuNet(args.detector_model)
    model = MLXGhostV2(
        args.models,
        precision=args.precision,
        native_generator=args.native_generator,
    )
    source = read_image_bgr(args.source)
    source_faces = detector.detect(source)
    if not source_faces:
        raise ValueError("source image contains no detectable face")
    source_face = max(source_faces, key=_area)
    source_crop, _ = align_face(source, source_face.landmarks, 256)
    identity = model.encode_aligned(source_crop)
    ready_seconds = time.perf_counter() - process_started

    reader = VideoReader(args.video)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    writer = VideoWriter(
        args.output,
        reader.fps,
        (reader.width, reader.height),
        codec=args.video_codec,
    )
    tracker = TemporalFaceTracker(velocity_smoothing=args.velocity_smoothing)
    chosen_track: int | None = None
    pending = []
    frames = 0
    detect_seconds = 0.0
    generate_seconds = 0.0
    composite_seconds = 0.0
    started = time.perf_counter()

    def flush() -> None:
        nonlocal generate_seconds, composite_seconds
        selected = [(frame, face) for frame, face in pending if face is not None]
        aligned = [align_face(frame, face.landmarks, 256) for frame, face in selected]
        stage = time.perf_counter()
        generated = model.generate_aligned_batch(
            [crop for crop, _ in aligned], identity
        )
        generate_seconds += time.perf_counter() - stage
        generated_iter = iter(generated)
        aligned_iter = iter(aligned)
        stage = time.perf_counter()
        for frame, face in pending:
            if face is None:
                writer.write(frame)
            else:
                crop = next(generated_iter)
                _, matrix = next(aligned_iter)
                writer.write(paste_face(frame, crop, matrix))
        composite_seconds += time.perf_counter() - stage
        pending.clear()

    try:
        for frame in reader:
            if args.max_frames and frames >= args.max_frames:
                break
            if frames % args.detection_interval == 0:
                stage = time.perf_counter()
                tracks = tracker.update(detector.detect(frame))
                detect_seconds += time.perf_counter() - stage
            else:
                tracks = tracker.predict()
            visible = [track for track in tracks if track.missed == 0]
            if chosen_track is None and visible:
                chosen_track = max(visible, key=_area).track_id
            selected_track: FaceTrack | None = next(
                (track for track in tracks if track.track_id == chosen_track), None
            )
            face = (
                selected_track.detection()
                if selected_track is not None
                and selected_track.missed <= tracker.max_missed
                else None
            )
            pending.append((frame, face))
            frames += 1
            if len(pending) >= args.batch_size:
                flush()
        flush()
    finally:
        reader.close()
        writer.close()

    elapsed = time.perf_counter() - started
    total_seconds = time.perf_counter() - process_started
    print(
        json.dumps(
            {
                "output": str(args.output),
                "precision": args.precision,
                "video_codec": args.video_codec,
                "frames": frames,
                "seconds": elapsed,
                "ready_seconds": ready_seconds,
                "total_seconds": total_seconds,
                "fps": frames / elapsed,
                "detect_seconds": detect_seconds,
                "generate_seconds": generate_seconds,
                "composite_seconds": composite_seconds,
                "peak_memory_bytes": mx.get_peak_memory(),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
