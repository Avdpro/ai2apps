#!/usr/bin/env python3
"""Export a compact Linux ARM64 CUDA Torch Runtime and package it."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.metadata
import json
import os
import shutil
import site
import subprocess
import sys
import sysconfig
import tarfile
import tempfile
from collections import deque
from pathlib import Path

import yaml
from packaging.utils import canonicalize_name

from packaging.requirements import InvalidRequirement, Requirement

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "packages" / "ai2apps-runtime-cuda-torch"
ROOT_DISTRIBUTIONS = (
    "fastapi",
    "pillow",
    "psutil",
    "python-multipart",
    "torch",
    "transformers",
    "uvicorn",
)
SYSTEM_CUDA_DISTRIBUTIONS = frozenset(
    {
        "cuda-bindings",
        "cuda-pathfinder",
        "cuda-toolkit",
        "triton",
    }
)
BUNDLED_NVIDIA_DISTRIBUTIONS = frozenset(
    {
        "nvidia-cudnn-cu13",
        "nvidia-cusparselt-cu13",
        "nvidia-nccl-cu13",
        "nvidia-nvshmem-cu13",
    }
)


def _ignored(_directory: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name in {"__pycache__", "test", "tests", "idlelib", "tkinter", "turtledemo"}
        or name.endswith((".pyc", ".pyo"))
    }


def _copy(source: Path, destination: Path) -> None:
    if source.is_symlink():
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.symlink_to(os.readlink(source))
    elif source.is_dir():
        shutil.copytree(source, destination, symlinks=True, ignore=_ignored)
    elif source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _distribution_index() -> dict[str, importlib.metadata.Distribution]:
    return {
        canonicalize_name(distribution.metadata["Name"]): distribution
        for distribution in importlib.metadata.distributions()
        if distribution.metadata.get("Name")
    }


def _excluded_distribution(name: str) -> bool:
    normalized = canonicalize_name(name)
    return normalized in SYSTEM_CUDA_DISTRIBUTIONS or (
        normalized.startswith("nvidia-")
        and normalized not in BUNDLED_NVIDIA_DISTRIBUTIONS
    )


def _distribution_closure() -> tuple[importlib.metadata.Distribution, ...]:
    index = _distribution_index()
    queue = deque(canonicalize_name(name) for name in ROOT_DISTRIBUTIONS)
    selected: dict[str, importlib.metadata.Distribution] = {}
    while queue:
        name = queue.popleft()
        if name in selected or _excluded_distribution(name):
            continue
        distribution = index.get(name)
        if distribution is None:
            raise RuntimeError(f"Required Runtime distribution is not installed: {name}")
        selected[name] = distribution
        for raw in distribution.requires or ():
            try:
                requirement = Requirement(raw)
            except InvalidRequirement:
                continue
            if requirement.marker is None or requirement.marker.evaluate():
                dependency = canonicalize_name(requirement.name)
                if dependency not in selected and not _excluded_distribution(dependency):
                    queue.append(dependency)
    return tuple(selected[name] for name in sorted(selected))


def _site_roots() -> tuple[Path, ...]:
    values = [Path(value).resolve() for value in site.getsitepackages()]
    user = site.getusersitepackages()
    if isinstance(user, str):
        values.append(Path(user).resolve())
    return tuple(dict.fromkeys(path for path in values if path.is_dir()))


def _copy_framework(destination: Path) -> list[dict[str, str]]:
    roots = _site_roots()
    copied: set[Path] = set()
    inventory = []
    for distribution in _distribution_closure():
        inventory.append(
            {
                "name": distribution.metadata["Name"],
                "version": distribution.version,
            }
        )
        for entry in distribution.files or ():
            source = Path(distribution.locate_file(entry))
            relative = None
            for root in roots:
                try:
                    relative = source.absolute().relative_to(root)
                    break
                except ValueError:
                    continue
            if relative is None or relative in copied or "__pycache__" in relative.parts:
                continue
            if relative.suffix in {".pyc", ".pyo"}:
                continue
            copied.add(relative)
            _copy(source, destination / relative)
    return inventory


def _copy_python(runtime: Path) -> tuple[Path, Path]:
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    python_home = runtime / "Python"
    binary = Path(getattr(sys, "_base_executable", sys.executable)).resolve(strict=True)
    target_binary = python_home / "bin" / version
    target_binary.parent.mkdir(parents=True)
    shutil.copy2(binary, target_binary)
    target_binary.chmod(0o755)
    stdlib = Path(sysconfig.get_path("stdlib")).resolve(strict=True)
    shutil.copytree(stdlib, python_home / "lib" / version, symlinks=True, ignore=_ignored)
    framework = python_home / "lib" / version / "site-packages"
    framework.mkdir(parents=True, exist_ok=True)
    return target_binary, framework


def _copy_launcher(runtime: Path) -> None:
    app = runtime / "app" / "ai2apps"
    app.mkdir(parents=True)
    for name in ("__init__.py", "_version.py"):
        shutil.copy2(REPO / "ai2apps" / name, app / name)
    shutil.copytree(
        REPO / "ai2apps" / "model_worker",
        app / "model_worker",
        symlinks=True,
        ignore=_ignored,
    )


def _sanitize_symlinks(root: Path) -> None:
    canonical_root = root.resolve(strict=True)
    for path in root.rglob("*"):
        if not path.is_symlink():
            continue
        try:
            path.resolve(strict=True).relative_to(canonical_root)
        except (OSError, ValueError):
            path.unlink()


def _archive(source: Path, output: Path) -> tuple[str, int]:
    output.parent.mkdir(parents=True)
    with (
        output.open("wb") as raw,
        gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed,
        tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive,
    ):
        archive.add(source, arcname=source.name, recursive=True)
    digest = hashlib.sha256()
    with output.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    unpacked = sum(path.stat().st_size for path in source.rglob("*") if path.is_file())
    return digest.hexdigest(), unpacked


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--private-key", type=Path)
    parser.add_argument("--keep-work", type=Path)
    parser.add_argument(
        "--package-python",
        type=Path,
        help="Python interpreter with AI2Apps and cryptography for outer Package signing.",
    )
    args = parser.parse_args()
    if sys.platform != "linux" or os.uname().machine not in {"aarch64", "arm64"}:
        raise RuntimeError("CUDA Torch Runtime must be built on Linux ARM64")
    manifest = yaml.safe_load((SOURCE / "service.yaml").read_text(encoding="utf-8"))
    version = str(manifest["version"])
    output = (
        args.output
        or SOURCE / "dist" / f"ai2apps-runtime-cuda-torch-{version}.ai2service"
    ).resolve()
    temporary_context = (
        tempfile.TemporaryDirectory(prefix="ai2apps-cuda-runtime-")
        if args.keep_work is None
        else None
    )
    work = Path(temporary_context.name) if temporary_context else args.keep_work.resolve()
    if temporary_context is None:
        work.mkdir(parents=True, exist_ok=False)
    try:
        runtime = work / "AI2AppsCudaTorchRuntime"
        runtime.mkdir()
        python, framework = _copy_python(runtime)
        inventory = _copy_framework(framework)
        _copy_launcher(runtime)
        _sanitize_symlinks(runtime)
        runtime.joinpath("META").mkdir()
        runtime.joinpath("META/distributions.json").write_text(
            json.dumps(inventory, indent=2) + "\n", encoding="utf-8"
        )
        stage = work / "package"
        shutil.copytree(SOURCE, stage, ignore=shutil.ignore_patterns("dist", "README.md"))
        payload = stage / "variants" / "linux-arm64" / "AI2AppsCudaTorchRuntime.tar.gz"
        sha256, unpacked = _archive(runtime, payload)
        descriptor_path = stage / "META" / "runtime-manifest.json"
        descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
        descriptor["python"] = python.relative_to(runtime).as_posix()
        descriptor["python_home"] = "Python"
        descriptor["framework_site_packages"] = framework.relative_to(runtime).as_posix()
        descriptor["payload"]["sha256"] = sha256
        descriptor["payload"]["max_unpacked_bytes"] = unpacked + 64 * 1024 * 1024
        descriptor_path.write_text(json.dumps(descriptor, indent=2) + "\n", encoding="utf-8")
        package_python = (args.package_python or Path(sys.executable)).absolute()
        if not package_python.is_file():
            raise FileNotFoundError(package_python)
        command = [
            str(package_python),
            str(REPO / "scripts" / "build_model_provider_package.py"),
            str(stage),
            "--output",
            str(output),
        ]
        if args.private_key is not None:
            command.extend(("--private-key", str(args.private_key.resolve(strict=True))))
        completed = subprocess.run(
            command, check=True, capture_output=True, text=True
        )
        report = json.loads(completed.stdout)
        report.update(
            {
                "payload_sha256": sha256,
                "payload_bytes": payload.stat().st_size,
                "unpacked_bytes": unpacked,
                "distributions": inventory,
            }
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        if temporary_context is not None:
            temporary_context.cleanup()


if __name__ == "__main__":
    main()
