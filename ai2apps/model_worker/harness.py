# SPDX-License-Identifier: Apache-2.0
"""Developer harness for validating a Model Worker Package before signing."""

from __future__ import annotations

import argparse
import asyncio
import json
import secrets
import tempfile
from pathlib import Path

import uvicorn
import yaml

from ai2apps.packages.archive import ServicePackageArchive
from ai2apps.packages.supervisor import ManagedServiceSupervisor

from .server import _context, _load_adapter, _maybe_call, create_app


def _config(
    package_root: Path, data_root: Path, *, resolve_checkpoints: bool = True
) -> Path:
    manifest_path = package_root / "service.yaml"
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    parsed = ServicePackageArchive._manifest(raw)
    if parsed.protocol != "ai2apps-model-worker/v1":
        raise ValueError("Package is not an ai2apps-model-worker/v1 Package")
    adapter, _, factory = parsed.raw["runtime"]["adapter"].partition(":")
    adapter_path = (package_root / adapter).resolve(strict=True)
    adapter_path.relative_to(package_root)
    data_root.mkdir(parents=True, exist_ok=True)
    checkpoints = ()
    if resolve_checkpoints:
        checkpoints, _ = ManagedServiceSupervisor._model_worker_checkpoints(
            parsed.raw, ManagedServiceSupervisor._huggingface_hub_cache()
        )
    path = data_root / "model-worker.harness.json"
    path.write_text(
        json.dumps(
            {
                "protocol": parsed.protocol,
                "service_id": parsed.service_key,
                "package_root": str(package_root),
                "data_root": str(data_root),
                "adapter_path": str(adapter_path),
                "adapter_factory": factory,
                "models": list(parsed.models),
                "checkpoints": list(checkpoints),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


async def _check(config_path: Path) -> None:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    adapter = await _load_adapter(config, _context(config))
    await _maybe_call(adapter, "start")
    await _maybe_call(adapter, "stop")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate an AI2Apps Model Package")
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--data", type=Path)
    parser.add_argument("--port", type=int, default=9100)
    parser.add_argument("--token")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    package_root = args.package.expanduser().resolve(strict=True)
    temporary = None
    if args.data is None:
        temporary = tempfile.TemporaryDirectory(prefix="ai2apps-model-worker-")
        data_root = Path(temporary.name)
    else:
        data_root = args.data.expanduser().resolve()
    # --check validates Package import and Adapter lifecycle without granting
    # or following any checkpoint path from the developer machine.
    config_path = _config(
        package_root, data_root, resolve_checkpoints=not args.check
    )
    if args.check:
        asyncio.run(_check(config_path))
        print("Model Worker adapter check passed")
        return
    token = args.token or secrets.token_urlsafe(24)
    print(f"Model Worker developer token: {token}")
    app = create_app(config_path, token=token)
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
