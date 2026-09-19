from __future__ import annotations

import argparse
import json
import os

from .backends import MlxDemucsBackend, TorchDemucsBackend
from .pipeline import SeparationConfig, separate_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the standalone two-stem Demucs baseline")
    parser.add_argument("input")
    parser.add_argument("output_dir")
    parser.add_argument("--model", default="htdemucs")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--torch-home", help="Temporary/local torch checkpoint cache")
    parser.add_argument("--shifts", type=int, default=0)
    parser.add_argument("--overlap", type=float, default=0.25)
    parser.add_argument("--backend", choices=("torch", "mlx"), default="torch")
    parser.add_argument("--weights", help="NPZ or safetensors required by --backend mlx")
    parser.add_argument(
        "--profile",
        choices=("dialogue_background", "vocals_instrumental", "music_4stem"),
        default="dialogue_background",
    )
    args = parser.parse_args()
    if args.torch_home:
        os.environ["TORCH_HOME"] = args.torch_home
    if args.backend == "mlx":
        if not args.weights:
            parser.error("--weights is required by --backend mlx")
        backend = MlxDemucsBackend(
            weights_path=args.weights,
            overlap=args.overlap,
            model_name=args.model,
        )
    else:
        backend = TorchDemucsBackend(
            model_name=args.model,
            device=args.device,
            shifts=args.shifts,
            overlap=args.overlap,
        )
    result = separate_file(
        args.input,
        args.output_dir,
        backend=backend,
        config=SeparationConfig(profile=args.profile),
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
