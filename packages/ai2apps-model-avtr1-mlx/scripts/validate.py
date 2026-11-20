"""Opt-in real-checkpoint parity against PyTorch and ONNX Runtime (developer only)."""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ["MLX_ENABLE_TF32"] = "0"
repository = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(repository / "packages/ai2apps-model-avtr1-mlx/src"),
    str(repository / "packages/omlx-model-liveportrait/src"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    import mlx.core as mx
    import numpy as np
    import onnx
    import onnxruntime as ort
    import torch
    from avtr_mlx.graph import AvatarGraph
    from avtr_mlx.model import MotionModel
    from avtr_mlx.pipeline import AvatarPipeline

    report = {}

    def compare(name, actual, expected, atol):
        actual, expected = np.asarray(actual), np.asarray(expected)
        diff = abs(actual - expected)
        assert np.isfinite(actual).all(), name
        report[name] = {
            "max_absolute": float(diff.max()),
            "mean_absolute": float(diff.mean()),
            "atol": atol,
        }
        print(name, report[name], flush=True)
        assert float(diff.max()) <= atol, (name, report[name])

    torch.set_num_threads(8)
    ref = torch.jit.load(
        str(args.model_root / "build_artifacts/avtr1.scripted.pt"), map_location="cpu"
    ).eval()
    model = MotionModel(args.model_root)
    rng = np.random.default_rng(42)
    values = {
        k: rng.normal(size=s).astype("float32")
        for k, s in {
            "past_cond": (1, 75, 42),
            "audio_cond": (1, 85, 2048),
            "kp_cond": (1, 1, 129),
            "past_times": (1, 15, 1),
        }.items()
    }
    with torch.no_grad():
        expected = ref.encode_conditions(
            **{k: torch.from_numpy(v) for k, v in values.items()}
        )
    actual = model.encode(**{k: mx.array(v) for k, v in values.items()})
    mx.eval(actual)
    for i, (a, b) in enumerate(zip(actual, expected)):
        compare("condition_" + str(i), np.array(a), b.numpy(), 5e-5)
    noise = rng.normal(size=(1, 5, 42)).astype("float32")
    x = torch.from_numpy(noise.copy())
    with torch.no_grad():
        for i in range(4):
            velocity = ref(
                x=x,
                kp=expected[0],
                past_context=expected[1],
                past_last=expected[2],
                audio_self=expected[3],
                audio_other=expected[4],
                t=torch.full((1, 1), i / 4),
                self_weights=torch.full((512,), 2.0),
                other_weights=torch.full((512,), 2.0),
                kp_weights=torch.full((512,), 3.0),
            )
            x = x + velocity / 4
    out = model.sample(
        actual,
        mx.array(noise),
        steps=5,
        self_weights=2.0,
        other_weights=2.0,
        kp_weights=3.0,
    )
    compare("motion_four_euler_steps", np.array(out), x.numpy(), 2e-4)
    del model, ref

    options = ort.SessionOptions()
    options.intra_op_num_threads = 8
    for name, shape, folder in [
        ("hubert-lbs-avtr1", (1, 8400), "build_artifacts"),
        ("motion_extractor", (1, 3, 256, 256), "ditto_onnx"),
        ("appearance_extractor", (1, 3, 256, 256), "ditto_onnx"),
    ]:
        path = args.model_root / folder / (name + ".onnx")
        graph = AvatarGraph(path)
        data = rng.uniform(0, 1, shape).astype("float32")
        actual = graph({graph.inputs[0]: data})
        mx.eval(actual)
        session = ort.InferenceSession(
            str(path), sess_options=options, providers=["CPUExecutionProvider"]
        )
        expected = session.run(None, {session.get_inputs()[0].name: data})
        for i, (a, b) in enumerate(zip(actual, expected)):
            compare(name + "_" + str(i), np.array(a), b, 5e-4)
        del session, graph

    pipe = AvatarPipeline(args.model_root)
    pipe.prepare(args.image)
    feeds = {"kp_source": pipe.source, "kp_driving": pipe.source.copy()}
    feeds["kp_driving"][:, 14, 1] += 0.02
    for name in ("stitch_network", "warp_network", "decoder"):
        if name == "warp_network":
            feeds = {
                "feature_3d": np.array(pipe.feature),
                "kp_source": pipe.source,
                "kp_driving": np.array(actual[0]),
            }
        if name == "decoder":
            feeds = {"feature": np.array(actual[0])}
        actual = pipe.run_graph(name, **feeds)
        path = args.model_root / "ditto_onnx" / (name + ".onnx")
        with tempfile.TemporaryDirectory() as temp:
            if name == "warp_network":
                graph = onnx.load(path)
                # Ditto's plugin is F.grid_sample(..., align_corners=False).
                # Replace only the custom sampling node in a temporary reference.
                for node in graph.graph.node:
                    if node.op_type == "GridSample3D":
                        node.op_type = "GridSample"
                        del node.attribute[:]
                        node.attribute.extend(
                            [
                                onnx.helper.make_attribute("align_corners", 0),
                                onnx.helper.make_attribute("mode", "bilinear"),
                                onnx.helper.make_attribute("padding_mode", "zeros"),
                            ]
                        )
                graph = onnx.version_converter.convert_version(graph, 20)
                path = Path(temp) / "warp-reference.onnx"
                onnx.save(graph, path)
            session = ort.InferenceSession(
                str(path), sess_options=options, providers=["CPUExecutionProvider"]
            )
            expected = session.run(None, feeds)
            compare(name, np.array(actual[0]), expected[0], 1e-4)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
