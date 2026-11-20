"""Validate optimized renderers against the original full FP32 rendering path."""

import argparse
import json
import os
import sys
import time
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
    from avtr_mlx.pipeline import AvatarPipeline
    from avtr_mlx.renderer import FastRenderer

    pipe = AvatarPipeline(args.model_root, renderer="reference")
    pipe.prepare(args.image)
    renderers = {
        name: FastRenderer(pipe.graphs, pipe.feature, pipe.source, mixed=mixed)
        for name, mixed in [("optimized", False), ("fast", True)]
    }
    rng = np.random.default_rng(207)
    report = {name: [] for name in renderers}
    for i in range(12):
        drive = pipe.source.copy()
        if i:
            drive += rng.normal(0, 0.002 if i < 6 else 0.015, drive.shape).astype(
                "float32"
            )
        reference = np.array(pipe.render_reference(drive))
        for name, renderer in renderers.items():
            start = time.perf_counter()
            out = renderer(mx.array(drive))
            mx.eval(out)
            elapsed = time.perf_counter() - start
            result = np.array(out)
            assert np.isfinite(result).all(), (name, i)
            diff = abs(result - reference)
            mae = float(diff.mean())
            maximum = float(diff.max())
            psnr = float(-10 * np.log10(max(float(np.mean(diff**2)), 1e-20)))
            row = {
                "case": i,
                "max_abs": maximum,
                "mean_abs": mae,
                "psnr_db": psnr,
                "seconds": elapsed,
            }
            report[name].append(row)
            print(name, row, flush=True)
            if name == "optimized":
                assert maximum < 2e-4, (name, row)
            else:
                assert mae < 0.002 and psnr > 45, (name, row)
    # Ensure replacing the source prepares fresh constants rather than reusing old identity tensors.
    source2 = pipe.source.copy()
    source2[:, :, 0] += 0.02
    second = FastRenderer(pipe.graphs, pipe.feature, source2)
    drive = mx.array(source2)
    stitched = pipe.run_graph("stitch_network", kp_source=source2, kp_driving=drive)[0]
    warped = pipe.run_graph(
        "warp_network", feature_3d=pipe.feature, kp_source=source2, kp_driving=stitched
    )[0]
    expected = pipe.run_graph("decoder", feature=warped)[0]
    actual = second(drive)
    mx.eval(actual)
    np.testing.assert_allclose(
        np.array(actual), np.array(expected), atol=2e-4, rtol=2e-4
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
