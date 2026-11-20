"""Check batching, partial batches and nonfinite-frame recovery on real weights."""

import argparse
import json
import os
import sys
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

    p = AvatarPipeline(args.model_root, renderer="reference")
    p.prepare(args.image)
    drives = np.repeat(p.source, 5, axis=0)
    drives += (
        np.random.default_rng(2026).normal(0, 0.008, drives.shape).astype("float32")
    )
    results = {}
    for mode in ("optimized", "fast"):
        p.renderer_mode = mode
        p.fast_renderer = FastRenderer(
            p.graphs, p.feature, p.source, mixed=mode == "fast"
        )
        reference = np.concatenate(
            [np.array(p.fast_renderer(mx.array(d[None]))) for d in drives]
        )
        for batch in (2, 5):
            out = np.concatenate(
                [
                    np.array(
                        p.fast_renderer.render_batch(mx.array(drives[i : i + batch]))
                    )
                    for i in range(0, 5, batch)
                ]
            )
            diff = abs(out - reference)
            row = {"max_abs": float(diff.max()), "mean_abs": float(diff.mean())}
            assert np.isfinite(out).all()
            if mode == "optimized":
                assert row["max_abs"] < 2e-4, row
            else:
                assert row["mean_abs"] < 0.001, row
            p.render_batch_size = batch
            pixels = np.concatenate(list(p.render_pixels(drives)))
            expected = (np.clip(out, 0, 1) * 255).astype("uint8").transpose(0, 2, 3, 1)
            pixel_difference = abs(pixels.astype("int16") - expected.astype("int16"))
            assert pixel_difference.max() <= 1
            row["quantization_max_levels"] = int(pixel_difference.max())
            results[f"{mode}_batch{batch}"] = row
            print(mode, batch, row, flush=True)
    # Inject one bad optimized frame. The same frame must be recovered, without reordering.
    original = p.fast_renderer

    class CorruptFrame:
        def render_batch(self, drive):
            out = original.render_batch(drive)
            out[0] = mx.full(out[0].shape, float("nan"))
            return out

    p.fast_renderer = CorruptFrame()
    p.render_batch_size = 5
    p.render_fallbacks = 0
    pixels = np.concatenate(list(p.render_pixels(drives)))
    reference = (
        (np.clip(np.array(p.render_reference(drives[:1]))[0], 0, 1) * 255)
        .astype("uint8")
        .transpose(1, 2, 0)
    )
    np.testing.assert_array_equal(pixels[0], reference)
    assert p.render_fallbacks == 1
    results["fallback"] = {"frames": 5, "recovered": 1}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
