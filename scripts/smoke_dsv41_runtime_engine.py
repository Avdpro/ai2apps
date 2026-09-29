#!/usr/bin/env python3
"""Run a short real checkpoint smoke through the formal DS4.1 Runtime engine."""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import importlib
import json
import mimetypes
import sys
import time
import types
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))


def _install_runtime_native_package(path: Path) -> None:
    """Reuse the signed Runtime extension while exercising checkout Python."""

    importlib.import_module("omlx.custom_kernels")
    source = SOURCE_ROOT / "omlx/custom_kernels/glm_moe_dsa"
    package_name = "omlx.custom_kernels.glm_moe_dsa"
    package = types.ModuleType(package_name)
    package.__package__ = package_name
    package.__path__ = [str(path.resolve()), str(source)]
    sys.modules[package_name] = package


async def _run(
    checkpoint: Path,
    output: Path,
    prompt: str,
    tokens: int,
    image: Path | None,
    boost: str,
    runtime_native_dir: Path | None,
) -> None:
    if runtime_native_dir is not None:
        _install_runtime_native_package(runtime_native_dir)
    from omlx.patches.deepseek_v41 import DeepseekV41Engine

    engine = DeepseekV41Engine(checkpoint)
    started = time.perf_counter()
    try:
        content: str | list[dict[str, object]] = prompt
        if image is not None:
            media_type = mimetypes.guess_type(image.name)[0] or "image/jpeg"
            encoded = base64.b64encode(image.read_bytes()).decode("ascii")
            content = [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{media_type};base64,{encoded}"},
                },
                {"type": "text", "text": prompt},
            ]
        result = await engine.chat(
            [{"role": "user", "content": content}],
            max_tokens=tokens,
            temperature=0,
            flesh_session_id="smoke-dsv41-runtime-engine",
            flesh_boost_mode=boost,
        )
        engine_stats = engine.get_stats()
        receipt = {
            "status": "complete",
            "checkpoint": str(checkpoint.resolve()),
            "ssd_checkpoint_sha256": hashlib.sha256(
                (checkpoint / "ssd-checkpoint.json").read_bytes()
            ).hexdigest(),
            "prompt": prompt,
            "image": str(image.resolve()) if image is not None else None,
            "text": result.text,
            "generated_ids": list(result.token_ids),
            "logits_sha256": list(result.logits_sha256),
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "finish_reason": result.finish_reason,
            "engine_stats": engine_stats,
            "elapsed_seconds": time.perf_counter() - started,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(receipt, ensure_ascii=False))
    finally:
        await engine.stop()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prompt", default="The capital of France is")
    parser.add_argument("--tokens", type=int, default=1)
    parser.add_argument("--image", type=Path)
    parser.add_argument(
        "--boost",
        choices=("auto", "natural", "turbo", "blast"),
        default="natural",
    )
    parser.add_argument("--runtime-native-dir", type=Path)
    args = parser.parse_args()
    asyncio.run(
        _run(
            args.checkpoint,
            args.output,
            args.prompt,
            args.tokens,
            args.image,
            args.boost,
            args.runtime_native_dir,
        )
    )


if __name__ == "__main__":
    main()
