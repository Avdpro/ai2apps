"""Run the standalone AVTR-1 MLX development pipeline from this checkout."""

import argparse
import json
import os
import sys
from pathlib import Path

# Strict FP32 is the validated baseline on M5; set before importing MLX.
os.environ["MLX_ENABLE_TF32"] = "0"
repository = Path(__file__).resolve().parents[3]
sys.path[:0] = [
    str(repository),
    str(repository / "packages/ai2apps-model-avtr1-mlx/src"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument(
        "--steps",
        type=int,
        default=5,
        help="ODE schedule points; 5 means 4 evaluations",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--renderer", choices=("reference", "optimized", "fast"), default="optimized"
    )
    parser.add_argument("--render-batch-size", type=int, choices=(1, 2, 5), default=2)
    parser.add_argument(
        "--output-mode",
        choices=("source", "crop"),
        default="source",
        help="source preserves original canvas; crop exports the 512px model result",
    )
    parser.add_argument("--sync-encoder", action="store_true")
    args = parser.parse_args()
    from avtr_mlx.pipeline import AvatarPipeline

    pipe = AvatarPipeline(
        args.model_root,
        renderer=args.renderer,
        output_mode=args.output_mode,
        render_batch_size=args.render_batch_size,
        asynchronous_encoding=not args.sync_encoder,
    )
    report = pipe.generate(
        args.image, args.audio, args.output, args.seconds, args.steps, args.seed
    )
    assert "torch" not in sys.modules, "Inference unexpectedly imported Torch"
    assert "onnxruntime" not in sys.modules, (
        "Inference unexpectedly imported ONNX Runtime"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
