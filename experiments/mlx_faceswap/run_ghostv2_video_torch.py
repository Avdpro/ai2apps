#!/usr/bin/env python3
"""Run the official GhostV2 core on video with MLX detection and tracking."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as functional
from safetensors.torch import load_file

from .benchmark_ghostv2_torch import _output_rgb, _rgb_tensor
from .geometry import align_face, paste_face
from .media import VideoReader, VideoWriter, read_image_bgr
from .models import MLXYuNet
from .tracking import FaceTrack, TemporalFaceTracker


def _area(track: FaceTrack) -> float:
    return max(0.0, float(track.bbox[2] - track.bbox[0])) * max(
        0.0, float(track.bbox[3] - track.bbox[1])
    )


def _largest_face(detector: MLXYuNet, image_bgr: np.ndarray):
    faces = detector.detect(image_bgr)
    if not faces:
        raise ValueError("source image contains no detectable face")
    return max(
        faces,
        key=lambda face: float(face.bbox[2] - face.bbox[0])
        * float(face.bbox[3] - face.bbox[1]),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--detector-model", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps"), default="mps")
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--detection-interval", type=int, default=1)
    parser.add_argument(
        "--temporal-smoothing",
        type=float,
        default=0.0,
        help="Previous aligned output weight in [0, 0.5].",
    )
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 16:
        parser.error("--batch-size must be between 1 and 16")
    if not 1 <= args.detection_interval <= 8:
        parser.error("--detection-interval must be between 1 and 8")
    if not 0.0 <= args.temporal_smoothing <= 0.5:
        parser.error("--temporal-smoothing must be between 0 and 0.5")

    sys.path.insert(0, str(args.repo.resolve()))
    from CVLFace import get_vit_model  # noqa: PLC0415
    from Ghost.AEI_Net import AEI_Net  # noqa: PLC0415

    device = torch.device(args.device)
    detector = MLXYuNet(args.detector_model)
    generator = AEI_Net("unet", num_blocks=2, c_id=512, align_corners=True)
    generator.load_state_dict(
        {
            key.removeprefix("_orig_mod."): value
            for key, value in load_file(
                args.repo / "weights/GhostV2/G_unet_2blocks.safetensors"
            ).items()
        },
        strict=True,
    )
    identity = get_vit_model(
        str(
            args.repo
            / "weights/CVLFace/cvlface_adaface_vit_base_webface4m.safetensors"
        )
    )
    generator.eval().to(device)
    identity.eval().to(device)

    source_bgr = read_image_bgr(args.source)
    source_face = _largest_face(detector, source_bgr)
    source_crop, _ = align_face(source_bgr, source_face.landmarks, 256)
    with torch.inference_mode():
        source_tensor = _rgb_tensor(source_crop[..., ::-1], device)
        embedding = functional.normalize(
            identity(functional.interpolate(source_tensor, (112, 112), mode="bilinear"))
        )

    reader = VideoReader(args.video)
    writer = VideoWriter(args.output, reader.fps, (reader.width, reader.height))
    tracker = TemporalFaceTracker()
    chosen_track: int | None = None
    pending: list[tuple[np.ndarray, object | None]] = []
    frames = 0
    detect_seconds = 0.0
    generate_seconds = 0.0
    composite_seconds = 0.0
    previous_generated: np.ndarray | None = None
    started = time.perf_counter()

    def flush() -> None:
        nonlocal generate_seconds, composite_seconds, previous_generated
        selected = [item for item in pending if item[1] is not None]
        if selected:
            aligned = [align_face(frame, face.landmarks, 256) for frame, face in selected]
            batch = torch.cat(
                [_rgb_tensor(crop[..., ::-1], device) for crop, _ in aligned], dim=0
            )
            stage = time.perf_counter()
            with torch.inference_mode():
                generated, _ = generator(batch, embedding.expand(batch.shape[0], -1))
                if device.type == "mps":
                    torch.mps.synchronize()
            generate_seconds += time.perf_counter() - stage
            generated_bgr = [
                np.ascontiguousarray(_output_rgb(value[None])[..., ::-1])
                for value in generated
            ]
            stage = time.perf_counter()
            generated_iter = iter(generated_bgr)
            aligned_iter = iter(aligned)
            rendered = []
            for frame, face in pending:
                if face is None:
                    previous_generated = None
                    rendered.append(frame)
                    continue
                crop = next(generated_iter)
                _, matrix = next(aligned_iter)
                if previous_generated is not None and args.temporal_smoothing:
                    strength = args.temporal_smoothing
                    crop = np.clip(
                        crop.astype(np.float32) * (1.0 - strength)
                        + previous_generated.astype(np.float32) * strength,
                        0,
                        255,
                    ).astype(np.uint8)
                previous_generated = crop
                rendered.append(paste_face(frame, crop, matrix))
            composite_seconds += time.perf_counter() - stage
        else:
            previous_generated = None
            rendered = [frame for frame, _ in pending]
        for frame in rendered:
            writer.write(frame)
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
                tracks = tracker.tracks
            visible = [track for track in tracks if track.missed == 0]
            if chosen_track is None and visible:
                chosen_track = max(visible, key=_area).track_id
            selected_track = next(
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
    print(
        json.dumps(
            {
                "output": str(args.output),
                "frames": frames,
                "seconds": elapsed,
                "fps": frames / elapsed,
                "detect_seconds": detect_seconds,
                "generate_seconds": generate_seconds,
                "composite_seconds": composite_seconds,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
