"""Command-line entry point for the evolving MLX implementation."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .config import GenerationRequest
from .memory_profiles import select_memory_profile
from .pipeline import AvatarPipeline


def _resolve_teacache_options(
    fast: bool, threshold: float | None, skip_start_steps: int | None
) -> tuple[float, int]:
    resolved_threshold = threshold if threshold is not None else (0.15 if fast else 0.0)
    resolved_skip_start = skip_start_steps if skip_start_steps is not None else (2 if fast else 5)
    return resolved_threshold, resolved_skip_start


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EchoMimicV3 MLX inference engine")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prompt", default="A person is speaking.")
    parser.add_argument("--seed", type=int, default=43)
    parser.add_argument("--width", type=int, choices=(512, 768), default=512)
    parser.add_argument("--height", type=int, choices=(512, 768), default=512)
    parser.add_argument(
        "--checkpoint",
        type=Path,
        help="atomically save each exact denoising step and resume after interruption",
    )
    parser.add_argument(
        "--long",
        action="store_true",
        help="segment the complete audio into bounded overlapping 81-frame windows",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="use the accepted approximate TeaCache preset (threshold 0.15, skip-start 2)",
    )
    parser.add_argument(
        "--teacache-threshold",
        type=float,
        default=None,
        help="override the TeaCache threshold (0 disables it)",
    )
    parser.add_argument("--teacache-skip-start-steps", type=int, default=None)
    args = parser.parse_args(argv)
    if args.checkpoint is not None and args.long:
        parser.error("--checkpoint is not yet supported with --long")
    teacache_threshold, teacache_skip_start_steps = _resolve_teacache_options(
        args.fast, args.teacache_threshold, args.teacache_skip_start_steps
    )
    request = GenerationRequest(
        str(args.image),
        str(args.audio),
        prompt=args.prompt,
        seed=args.seed,
        width=args.width,
        height=args.height,
        teacache_threshold=teacache_threshold,
        teacache_skip_start_steps=teacache_skip_start_steps,
        use_fused_norms=args.fast,
    )
    memory_profile = select_memory_profile()
    memory_profile.validate(request)
    pipeline = AvatarPipeline.from_pretrained(
        args.models, cache_conditions=memory_profile.cache_conditions
    )

    def progress(phase: str, current: int, total: int) -> None:
        print(f"{phase}: {current}/{total}", flush=True)

    print(f"memory-profile: {memory_profile.name}", flush=True)
    destination = (
        pipeline.generate_long_to_file(request, args.output, progress=progress)
        if args.long
        else pipeline.generate_to_file(
            request,
            args.output,
            progress=progress,
            checkpoint_path=args.checkpoint,
        )
    )
    print(destination)
    return 0
