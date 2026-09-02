#!/usr/bin/env python3
"""Build an ad-hoc-signed local Knowledge RAG Runtime Package."""

from __future__ import annotations

import argparse
import hashlib
import json
import plistlib
import shutil
import tempfile
from pathlib import Path

import yaml
from build_model_provider_package import build as build_local_service_package
from build_omlx_runtime_package import copy_tree, run, sign_runtime


def create_bundle(layers: Path, destination: Path, version: str) -> Path:
    cpython = layers / "cpython-3.11"
    framework = layers / "framework-knowledge-rag"
    if not cpython.is_dir() or not framework.is_dir():
        raise FileNotFoundError(
            "Export cpython-3.11 and framework-knowledge-rag before packaging"
        )
    bundle = destination / "AI2AppsKnowledgeRagRuntime.bundle"
    contents = bundle / "Contents"
    runtime = contents / "Resources" / "Runtime" / "Python"
    (contents / "MacOS").mkdir(parents=True)
    runtime.mkdir(parents=True)
    executable = contents / "MacOS" / "AI2AppsKnowledgeRagRuntime"
    shutil.copyfile(cpython / "bin" / "python3.11", executable)
    executable.chmod(0o755)
    (contents / "Info.plist").write_bytes(
        plistlib.dumps(
            {
                "CFBundleIdentifier": "com.ai2apps.runtime.knowledge-rag",
                "CFBundleName": "AI2Apps Knowledge RAG Runtime",
                "CFBundleExecutable": "AI2AppsKnowledgeRagRuntime",
                "CFBundlePackageType": "BNDL",
                "CFBundleShortVersionString": version,
                "CFBundleVersion": version,
            }
        )
    )
    copy_tree(cpython, runtime / "cpython-3.11")
    copy_tree(framework, runtime / "framework-knowledge-rag")
    return bundle


def descriptor(version: str, capabilities: list[str]) -> dict:
    return {
        "schema": "ai2apps.knowledge-runtime/v1",
        "service_id": "ai2apps.runtime.knowledge-rag",
        "version": version,
        "protocol": "ai2apps-knowledge-vector-worker/v1",
        "capabilities": capabilities,
        "python": "Contents/Resources/Runtime/Python/cpython-3.11/bin/python3.11",
        "python_home": "Contents/Resources/Runtime/Python/cpython-3.11",
        "framework_site_packages": "Contents/Resources/Runtime/Python/framework-knowledge-rag/lib/python3.11/site-packages",
        "payload": {
            "type": "dmg",
            "path": "variants/darwin-arm64/AI2AppsKnowledgeRagRuntime.dmg",
            "root": "AI2AppsKnowledgeRagRuntime.bundle",
        },
        "distribution": {"signing": "development", "team_id": None},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--layers", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--private-key", type=Path)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    layers = args.layers.resolve(strict=True)
    manifest = yaml.safe_load((source / "service.yaml").read_text(encoding="utf-8"))
    version = str(manifest["version"])
    output = (
        args.output
        or source / "dist" / f"ai2apps-runtime-knowledge-rag-{version}.ai2service"
    ).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ai2apps-knowledge-runtime-") as temporary:
        root = Path(temporary)
        image = root / "image"
        image.mkdir()
        bundle = create_bundle(layers, image, version)
        sign_runtime(bundle, "-")
        dmg = root / "AI2AppsKnowledgeRagRuntime.dmg"
        run(
            "/usr/bin/hdiutil",
            "create",
            "-fs",
            "HFS+",
            "-format",
            "UDZO",
            "-imagekey",
            "zlib-level=9",
            "-srcfolder",
            str(image),
            str(dmg),
        )
        run("/usr/bin/codesign", "--force", "--sign", "-", str(dmg))
        stage = root / "package"
        shutil.copytree(source, stage, ignore=shutil.ignore_patterns("dist", "README.md"))
        variant = stage / "variants" / "darwin-arm64"
        variant.mkdir(parents=True)
        shutil.copy2(dmg, variant / dmg.name)
        (stage / "META" / "runtime-manifest.json").write_text(
            json.dumps(
                descriptor(version, list(manifest.get("capabilities", ()))), indent=2
            )
            + "\n",
            encoding="utf-8",
        )
        result = build_local_service_package(
            stage,
            output,
            args.private_key.resolve(strict=True) if args.private_key else None,
        )
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    print(json.dumps({**result, "sha256": digest}, indent=2))


if __name__ == "__main__":
    main()
