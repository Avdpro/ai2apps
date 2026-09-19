#!/usr/bin/env python3
"""Compare face-swap video identity, detail, and excess temporal variation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .geometry import align_face
from .media import VideoReader, read_image_bgr
from .models import MLXArcFace, MLXYuNet
from .tracking import TemporalFaceTracker


def _largest(faces):
    if not faces:
        raise ValueError("no face detected")
    return max(
        faces,
        key=lambda face: float(face.bbox[2] - face.bbox[0])
        * float(face.bbox[3] - face.bbox[1]),
    )


def _sharpness(image: np.ndarray) -> float:
    gray = image.astype(np.float32).mean(axis=2)
    return float(np.var(np.diff(gray, axis=0)) + np.var(np.diff(gray, axis=1)))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--detector-model", type=Path, required=True)
    parser.add_argument("--recognizer-model", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target-video", type=Path, required=True)
    parser.add_argument("--output-video", type=Path, action="append", required=True)
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--detection-interval", type=int, default=2)
    parser.add_argument("--velocity-smoothing", type=float, default=0.5)
    args = parser.parse_args()

    detector = MLXYuNet(args.detector_model)
    recognizer = MLXArcFace(args.recognizer_model)
    source_image = read_image_bgr(args.source)
    source_face = _largest(detector.detect(source_image))
    source_embedding = recognizer.embed(source_image, source_face.landmarks)[0]

    target_reader = VideoReader(args.target_video)
    output_readers = [VideoReader(path) for path in args.output_video]
    output_iterators = [iter(reader) for reader in output_readers]
    per_output = [
        {"identity": [], "sharpness": [], "temporal_excess_mae": []}
        for _ in output_readers
    ]
    previous_target = None
    previous_outputs: list[np.ndarray | None] = [None] * len(output_readers)
    tracker = TemporalFaceTracker(velocity_smoothing=args.velocity_smoothing)
    chosen_track: int | None = None
    frames = 0
    try:
        for target_frame in target_reader:
            if args.max_frames and frames >= args.max_frames:
                break
            output_frames = []
            for iterator in output_iterators:
                try:
                    output_frames.append(next(iterator))
                except StopIteration:
                    output_frames.append(None)
            if any(frame is None for frame in output_frames):
                break
            if frames % args.detection_interval == 0:
                tracks = tracker.update(detector.detect(target_frame))
            else:
                tracks = tracker.predict()
            visible = [track for track in tracks if track.missed == 0]
            if chosen_track is None and visible:
                chosen_track = max(
                    visible,
                    key=lambda track: float(track.bbox[2] - track.bbox[0])
                    * float(track.bbox[3] - track.bbox[1]),
                ).track_id
            selected = next(
                (track for track in tracks if track.track_id == chosen_track), None
            )
            if selected is None or selected.missed > tracker.max_missed:
                previous_target = None
                previous_outputs = [None] * len(output_readers)
                frames += 1
                continue
            target_face = selected.detection()
            target_crop, _ = align_face(
                target_frame, target_face.landmarks, 256
            )
            target_core = target_crop[32:224, 32:224].astype(np.float32)
            for index, output_frame in enumerate(output_frames):
                assert output_frame is not None
                output_crop, _ = align_face(
                    output_frame, target_face.landmarks, 256
                )
                output_core = output_crop[32:224, 32:224].astype(np.float32)
                embedding = recognizer.embed_aligned(output_crop)[0]
                per_output[index]["identity"].append(
                    float(np.dot(source_embedding, embedding))
                )
                per_output[index]["sharpness"].append(_sharpness(output_core))
                if (
                    previous_target is not None
                    and previous_outputs[index] is not None
                ):
                    residual = (output_core - previous_outputs[index]) - (
                        target_core - previous_target
                    )
                    per_output[index]["temporal_excess_mae"].append(
                        float(np.mean(np.abs(residual)) / 255.0)
                    )
                previous_outputs[index] = output_core
            previous_target = target_core
            frames += 1
    finally:
        target_reader.close()
        for reader in output_readers:
            reader.close()

    results = []
    for path, values in zip(args.output_video, per_output, strict=True):
        results.append(
            {
                "path": str(path),
                "identity_mean": float(np.mean(values["identity"])),
                "identity_std": float(np.std(values["identity"])),
                "sharpness_mean": float(np.mean(values["sharpness"])),
                "temporal_excess_mae": float(
                    np.mean(values["temporal_excess_mae"])
                ),
            }
        )
    print(json.dumps({"frames": frames, "outputs": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
