#!/usr/bin/env python3
"""Run the minimal official GhostV2 generator/identity path for quality audit."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as functional
from PIL import Image
from safetensors.torch import load_file

from .geometry import align_face, paste_face
from .media import read_image_bgr, write_image_bgr
from .models import MLXYuNet


def _rgb_tensor(rgb: np.ndarray, device: torch.device) -> torch.Tensor:
    values = np.ascontiguousarray(rgb.transpose(2, 0, 1))[None] / 127.5 - 1.0
    return torch.from_numpy(values.astype(np.float32)).to(device)


def _tensor(path: Path, size: int, device: torch.device) -> torch.Tensor:
    with Image.open(path) as image:
        rgb = np.asarray(
            image.convert("RGB").resize((size, size), Image.Resampling.BILINEAR),
            dtype=np.uint8,
        )
    return _rgb_tensor(rgb, device)


def _output_rgb(value: torch.Tensor) -> np.ndarray:
    return (
        value.detach()
        .float()
        .clamp(-1.0, 1.0)
        .add(1.0)
        .mul(127.5)
        .round()
        .byte()[0]
        .permute(1, 2, 0)
        .cpu()
        .numpy()
    )


def _save(path: Path, value: torch.Tensor) -> None:
    rgb = _output_rgb(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb, mode="RGB").save(path)


def _largest_face(detector: MLXYuNet, image_bgr: np.ndarray):
    faces = detector.detect(image_bgr)
    if not faces:
        raise ValueError("input image contains no detectable face")
    return max(
        faces,
        key=lambda face: float(face.bbox[2] - face.bbox[0])
        * float(face.bbox[3] - face.bbox[1]),
    )


def _full_image_inputs(
    detector_model: Path,
    source_path: Path,
    target_path: Path,
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor, np.ndarray, np.ndarray]:
    detector = MLXYuNet(detector_model)
    source_bgr = read_image_bgr(source_path)
    target_bgr = read_image_bgr(target_path)
    source_face = _largest_face(detector, source_bgr)
    target_face = _largest_face(detector, target_bgr)
    source_crop, _ = align_face(source_bgr, source_face.landmarks, 256)
    target_crop, matrix = align_face(target_bgr, target_face.landmarks, 256)
    return (
        _rgb_tensor(source_crop[..., ::-1], device),
        _rgb_tensor(target_crop[..., ::-1], device),
        target_bgr,
        matrix,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--embedding-output", type=Path)
    parser.add_argument("--tensor-output", type=Path)
    parser.add_argument("--device", choices=("cpu", "mps"), default="mps")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument(
        "--detector-model",
        type=Path,
        help="Optional MLX YuNet model for full-image alignment and paste-back.",
    )
    args = parser.parse_args()

    sys.path.insert(0, str(args.repo.resolve()))
    from CVLFace import get_vit_model  # noqa: PLC0415
    from Ghost.AEI_Net import AEI_Net  # noqa: PLC0415

    device = torch.device(args.device)
    generator_path = args.repo / "weights/GhostV2/G_unet_2blocks.safetensors"
    identity_path = (
        args.repo
        / "weights/CVLFace/cvlface_adaface_vit_base_webface4m.safetensors"
    )
    started = time.perf_counter()
    generator = AEI_Net("unet", num_blocks=2, c_id=512, align_corners=True)
    generator.load_state_dict(
        {
            key.removeprefix("_orig_mod."): value
            for key, value in load_file(generator_path).items()
        },
        strict=True,
    )
    identity = get_vit_model(str(identity_path))
    generator.eval().to(device)
    identity.eval().to(device)
    load_seconds = time.perf_counter() - started

    target_bgr = None
    target_matrix = None
    if args.detector_model is None:
        source = _tensor(args.source, 256, device)
        target = _tensor(args.target, 256, device)
    else:
        source, target, target_bgr, target_matrix = _full_image_inputs(
            args.detector_model, args.source, args.target, device
        )
    timings: list[float] = []
    with torch.inference_mode():
        embedding = functional.normalize(
            identity(functional.interpolate(source, (112, 112), mode="bilinear"))
        )
        if args.embedding_output is not None:
            args.embedding_output.parent.mkdir(parents=True, exist_ok=True)
            np.save(args.embedding_output, embedding.float().cpu().numpy())
        output = None
        for _ in range(max(1, args.runs)):
            started = time.perf_counter()
            output, _ = generator(target, embedding)
            if device.type == "mps":
                torch.mps.synchronize()
            timings.append(time.perf_counter() - started)
    assert output is not None
    if args.tensor_output is not None:
        args.tensor_output.parent.mkdir(parents=True, exist_ok=True)
        np.save(args.tensor_output, output.float().cpu().numpy())
    if target_bgr is None or target_matrix is None:
        _save(args.output, output)
    else:
        swapped_bgr = np.ascontiguousarray(_output_rgb(output)[..., ::-1])
        write_image_bgr(
            args.output,
            paste_face(target_bgr, swapped_bgr, target_matrix),
        )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "device": str(device),
                "load_seconds": load_seconds,
                "runs": timings,
                "warm_seconds": timings[-1],
                "warm_fps": 1.0 / timings[-1],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
