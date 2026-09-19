#!/usr/bin/env python3
"""Compare the constrained MLX executor with ONNX Runtime."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from onnx import numpy_helper

from experiments.mlx_faceswap.onnx_mlx import MLXOnnxGraph


def inputs_for(
    model: str, model_path: Path, seed: int, source_image: Path | None = None
) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    if model in {"arcface", "simswap_arcface"}:
        name = "input.1" if model == "arcface" else "input"
        return {name: rng.normal(size=(1, 3, 112, 112)).astype(np.float32)}
    if model == "scrfd":
        return {"input.1": rng.normal(size=(1, 3, 320, 320)).astype(np.float32)}
    if model == "yunet":
        return {
            "input": rng.uniform(0.0, 255.0, size=(1, 3, 640, 640)).astype(np.float32)
        }
    if model == "xseg":
        if source_image is not None:
            import cv2

            image = cv2.imread(str(source_image))
            if image is None:
                raise ValueError(f"could not read source image: {source_image}")
            return {
                "in_face:0": cv2.dnn.blobFromImage(
                    image,
                    1.0 / 255.0,
                    (256, 256),
                    (0.0, 0.0, 0.0),
                    swapRB=True,
                ).astype(np.float32)
            }
        return {
            "in_face:0": rng.uniform(0.0, 1.0, size=(1, 3, 256, 256)).astype(np.float32)
        }
    if model == "simswap":
        identity = rng.normal(size=(1, 512)).astype(np.float32)
        identity /= np.linalg.norm(identity, axis=1, keepdims=True)
        return {
            "input": rng.uniform(-1.0, 1.0, size=(1, 3, 512, 512)).astype(np.float32),
            "onnx::Gemm_1": identity,
        }
    if model == "gfpgan":
        return {
            "input": rng.uniform(-1.0, 1.0, size=(1, 3, 512, 512)).astype(np.float32)
        }
    if model in {"liveportrait_appearance", "liveportrait_motion"}:
        return {"img": rng.uniform(0.0, 1.0, size=(1, 3, 256, 256)).astype(np.float32)}
    if model == "liveportrait_warping":
        return {
            "feature_3d": rng.normal(size=(1, 32, 16, 64, 64)).astype(np.float32),
            "kp_driving": rng.uniform(-0.5, 0.5, size=(1, 21, 3)).astype(np.float32),
            "kp_source": rng.uniform(-0.5, 0.5, size=(1, 21, 3)).astype(np.float32),
        }
    if model == "inswapper":
        if source_image is None:
            raise ValueError(
                "InSwapper validation requires --source-image with an aligned "
                "112x112 face; arbitrary vectors are outside its learned identity manifold"
            )
        import cv2

        image = cv2.imread(str(source_image))
        if image is None:
            raise ValueError(f"could not read source image: {source_image}")
        arcface_path = model_path.with_name("w600k_r50.onnx")
        if not arcface_path.exists():
            raise FileNotFoundError(
                "InSwapper parity needs sibling w600k_r50.onnx to create a "
                "valid ArcFace-manifold identity vector"
            )
        arcface = ort.InferenceSession(
            str(arcface_path), providers=["CPUExecutionProvider"]
        )
        arcface_input = cv2.dnn.blobFromImage(
            image,
            1.0 / 127.5,
            (112, 112),
            (127.5, 127.5, 127.5),
            swapRB=True,
        ).astype(np.float32)
        embedding = arcface.run(None, {arcface.get_inputs()[0].name: arcface_input})[0]
        embedding /= np.linalg.norm(embedding, axis=1, keepdims=True)
        model_graph = onnx.load(str(model_path), load_external_data=False)
        emap = numpy_helper.to_array(model_graph.graph.initializer[-1]).astype(
            np.float32
        )
        source = embedding @ emap
        source /= np.linalg.norm(source, axis=1, keepdims=True)
        return {
            "target": cv2.dnn.blobFromImage(
                image,
                1.0 / 255.0,
                (128, 128),
                (0.0, 0.0, 0.0),
                swapRB=True,
            ).astype(np.float32),
            "source": source,
        }
    raise ValueError(model)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "model",
        choices=(
            "arcface",
            "scrfd",
            "yunet",
            "inswapper",
            "xseg",
            "simswap",
            "simswap_arcface",
            "gfpgan",
            "liveportrait_appearance",
            "liveportrait_motion",
            "liveportrait_warping",
        ),
    )
    parser.add_argument("model_path", type=Path)
    parser.add_argument("--seed", type=int, default=20260905)
    parser.add_argument("--source-image", type=Path)
    parser.add_argument(
        "--float16-mode",
        choices=("fp16_compatible", "bf16"),
        default="fp16_compatible",
    )
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    feeds = inputs_for(args.model, args.model_path, args.seed, args.source_image)
    session = ort.InferenceSession(
        str(args.model_path), providers=["CPUExecutionProvider"]
    )
    started = time.perf_counter()
    expected = session.run(None, feeds)
    ort_seconds = time.perf_counter() - started

    graph = MLXOnnxGraph(args.model_path, float16_mode=args.float16_mode)
    started = time.perf_counter()
    actual_mx = graph(feeds)
    graph.evaluate(actual_mx)
    mlx_seconds = time.perf_counter() - started
    actual = [np.asarray(item) for item in actual_mx]

    outputs = []
    for index, (reference, candidate) in enumerate(zip(expected, actual, strict=True)):
        reference_finite = np.isfinite(reference)
        candidate_finite = np.isfinite(candidate)
        delta = np.abs(reference.astype(np.float32) - candidate.astype(np.float32))
        finite_delta = delta[np.isfinite(delta)]
        output_report = {
            "index": index,
            "shape": list(reference.shape),
            "reference_nonfinite": int(reference.size - reference_finite.sum()),
            "candidate_nonfinite": int(candidate.size - candidate_finite.sum()),
            "max_abs": float(finite_delta.max(initial=0.0)),
            "mean_abs": float(finite_delta.mean()) if finite_delta.size else None,
            "reference_abs_max": float(
                np.abs(reference[reference_finite]).max(initial=0.0)
            ),
        }
        if args.model == "xseg":
            reference_binary = reference >= 0.5
            candidate_binary = candidate >= 0.5
            intersection = np.logical_and(reference_binary, candidate_binary).sum()
            union = np.logical_or(reference_binary, candidate_binary).sum()
            output_report["binary_iou_at_0_5"] = float(
                intersection / union if union else 1.0
            )
        outputs.append(output_report)
    report = {
        "model": args.model,
        "model_path": str(args.model_path),
        "seed": args.seed,
        "float16_mode": args.float16_mode,
        "onnxruntime_cpu_seconds": ort_seconds,
        "mlx_cold_seconds": mlx_seconds,
        "outputs": outputs,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.json:
        args.json.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
