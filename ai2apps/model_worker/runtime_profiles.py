# SPDX-License-Identifier: Apache-2.0
"""Select a signed Runtime's dependency layer before importing its server."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def framework_profile(runtime_root: Path, argv: list[str]) -> Path | None:
    if not (runtime_root / "META/framework-profiles.json").exists():
        return None
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--config", required=True)
    args, _ = parser.parse_known_args(argv)
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    return framework_profile_for_service(runtime_root, config["service_id"])


def framework_profile_for_service(runtime_root: Path, service_id: str) -> Path | None:
    """Resolve a Host-owned service identity using only signed Runtime metadata."""
    manifest = runtime_root / "META/framework-profiles.json"
    if not manifest.exists():
        return None
    value = json.loads(manifest.read_text(encoding="utf-8"))
    if value.get("format") != "ai2apps.framework-profiles/v1":
        raise RuntimeError("Unsupported Runtime framework profiles")
    profile = value["services"].get(service_id)
    if profile is None:
        return None
    return _resolve_profile(runtime_root, value, profile)


def framework_profile_for_stage(
    runtime_root: Path, service_id: str, stage: str
) -> Path:
    """Resolve a required subprocess layer from signed Runtime metadata only.

    Unlike the optional primary service layer, an undeclared stage must fail
    closed: falling back to the core can import incompatible model libraries.
    Request payloads must never provide a profile name or directory.
    """
    manifest = runtime_root / "META/framework-profiles.json"
    value = json.loads(manifest.read_text(encoding="utf-8"))
    if value.get("format") != "ai2apps.framework-profiles/v1":
        raise RuntimeError("Unsupported Runtime framework profiles")
    profile = value.get("stages", {}).get(service_id, {}).get(stage)
    if not isinstance(profile, str) or not profile:
        raise RuntimeError("Required Runtime stage profile is not declared")
    return _resolve_profile(runtime_root, value, profile)


def _resolve_profile(runtime_root: Path, value: dict, profile: str) -> Path:
    relative = Path(value["profiles"][profile]["site_packages"])
    if relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError("Runtime framework profile escapes Runtime root")
    root = runtime_root.resolve(strict=True)
    selected = (root / relative).resolve(strict=True)
    if not selected.is_relative_to(root) or not selected.is_dir():
        raise RuntimeError("Runtime framework profile escapes Runtime root")
    return selected


def framework_stage_entrypoint(runtime_root: Path, service_id: str, stage: str) -> Path:
    """Only a Runtime-declared stage program may run in a selected layer."""
    value = json.loads((runtime_root / "META/framework-profiles.json").read_text())
    if value.get("format") != "ai2apps.framework-profiles/v1":
        raise RuntimeError("Unsupported Runtime framework profiles")
    entry = value.get("stage_entrypoints", {}).get(service_id, {}).get(stage)
    if not isinstance(entry, str) or not entry:
        raise RuntimeError("Required Runtime stage entrypoint is not declared")
    relative = Path(entry)
    if relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError("Runtime stage entrypoint escapes Runtime root")
    root = runtime_root.resolve(strict=True)
    selected = (root / relative).resolve(strict=True)
    if not selected.is_relative_to(root) or not selected.is_file():
        raise RuntimeError("Runtime stage entrypoint escapes Runtime root")
    return selected
