#!/usr/bin/env python3
"""Run the Package adapter directly against a pinned local checkpoint."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", default="dialogue_background")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from ai2apps.model_worker import (
        ModelWorkerCheckpoint,
        ModelWorkerContext,
        ModelWorkerPart,
        ModelWorkerRequest,
    )

    spec = importlib.util.spec_from_file_location(
        "demucs_worker_adapter", root / "src/worker_adapter.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    async def run() -> None:
        with tempfile.TemporaryDirectory(prefix="demucs-smoke-") as temporary:
            work = Path(temporary)
            output_root = work / "output"
            output_root.mkdir()
            checkpoint = ModelWorkerCheckpoint(
                model_id="ai2apps.model.demucs-mlx/default",
                upstream_id="mlx-community/demucs-mlx",
                provider="huggingface",
                repo_id="mlx-community/demucs-mlx",
                revision="d4519e24ddc2dd4a11d56a193092433d852c3961",
                path=args.checkpoint.resolve(),
                preparation={"recipe": "native"},
            )
            context = ModelWorkerContext(
                service_id="ai2apps.model.demucs-mlx",
                package_root=root,
                data_root=work / "data",
                models=(),
                checkpoints=(checkpoint,),
            )
            adapter = module.create_adapter(context)
            progress = []

            async def report(value):
                progress.append(dict(value))

            source = args.input.resolve()
            request = ModelWorkerRequest(
                operation="audio_process",
                payload={
                    "model": "mlx-community/demucs-mlx",
                    "task": "source_separation",
                    "profile": args.profile,
                },
                request_id="demucs-package-smoke",
                parts={
                    "file": ModelWorkerPart(
                        name="file",
                        path=source,
                        media_type="audio/wav",
                        filename=source.name,
                        size=source.stat().st_size,
                        sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                    )
                },
                output_root=output_root,
                progress=report,
            )
            result = await adapter.invoke(request)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(result.path, args.output)
            await adapter.stop()
            print(
                {
                    "artifact": str(args.output),
                    "bytes": args.output.stat().st_size,
                    "media_type": result.media_type,
                    "progress": progress,
                }
            )

    asyncio.run(run())


if __name__ == "__main__":
    main()
