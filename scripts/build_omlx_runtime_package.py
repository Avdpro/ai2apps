#!/usr/bin/env python3
"""Build the macOS oMLX Runtime bundle, DMG, and signed Service Package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import shutil
import stat
import subprocess
import tempfile
import time
from contextlib import nullcontext
from pathlib import Path

import yaml
from build_model_provider_package import build as build_local_service_package

from ai2apps.packages.contract_v1 import build_package, create_signature_envelope
from ai2apps.secrets.factory import create_secret_backend

REPO = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    ".build",
}


def run(*command: str) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
    )
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip()[-4000:]
        raise RuntimeError(f"Command failed ({command[0]}): {detail}")
    return completed


def run_codesign(*arguments: str) -> subprocess.CompletedProcess[str]:
    """Run codesign with bounded retries for transient timestamp failures."""

    for attempt in range(3):
        try:
            return run("/usr/bin/codesign", *arguments)
        except RuntimeError as error:
            if "timestamp" not in str(error).lower() or attempt == 2:
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def copy_tree(source: Path, destination: Path, *, runtime_source: bool = False) -> None:
    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored = {name for name in names if name in EXCLUDED_PARTS}
        if runtime_source and Path(directory).name == "omlx":
            ignored.update(name for name in names if name == "eval")
        ignored.update(name for name in names if name.endswith((".pyc", ".pyo")))
        return ignored

    shutil.copytree(source, destination, symlinks=True, ignore=ignore)


def sanitize_symlinks(root: Path) -> None:
    """Remove export-time links that would escape or break the signed Runtime."""

    canonical_root = root.resolve(strict=True)
    for path in root.rglob("*"):
        if not path.is_symlink():
            continue
        try:
            target = path.resolve(strict=True)
            target.relative_to(canonical_root)
        except (OSError, ValueError):
            path.unlink()


def is_macho(path: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    try:
        with path.open("rb") as stream:
            magic = stream.read(4)
    except OSError:
        return False
    return magic in {
        b"\xfe\xed\xfa\xce",
        b"\xfe\xed\xfa\xcf",
        b"\xce\xfa\xed\xfe",
        b"\xcf\xfa\xed\xfe",
        b"\xca\xfe\xba\xbe",
        b"\xca\xfe\xba\xbf",
    }


def sign_runtime(bundle: Path, identity: str) -> str | None:
    timestamp = [] if identity == "-" else ["--timestamp", "--options", "runtime"]
    native_paths = sorted(
        (item for item in bundle.rglob("*") if is_macho(item)),
        key=lambda item: len(item.parts),
        reverse=True,
    )
    # Exported Python wheels may carry ad-hoc or stale Developer ID signatures.
    # Replacing one directly with a timestamped signature can make codesign
    # validate the old signature first and fail on its missing timestamp.
    # Normalize every nested Mach-O to unsigned bytes before sealing the tree.
    for path in native_paths:
        # venvstacks preserves wheel modes. Some native files are read-only,
        # which makes codesign's in-place signature removal fail and leaves a
        # stale non-timestamped seal behind. The Runtime bundle itself is an
        # immutable build staging tree, so grant only owner write permission.
        path.chmod(path.stat().st_mode | stat.S_IWUSR)
        subprocess.run(
            ["/usr/bin/codesign", "--remove-signature", str(path)],
            check=False,
            capture_output=True,
        )
    for path in native_paths:
        run_codesign("--force", *timestamp, "--sign", identity, str(path))
    run_codesign(
        "--force",
        "--deep",
        *timestamp,
        "--sign",
        identity,
        str(bundle),
    )
    run("/usr/bin/codesign", "--verify", "--deep", "--strict", str(bundle))
    if identity == "-":
        return None
    details = run("/usr/bin/codesign", "-dvvv", str(bundle)).stderr
    for line in details.splitlines():
        if line.startswith("TeamIdentifier="):
            return line.partition("=")[2]
    raise RuntimeError("Developer ID Runtime bundle has no TeamIdentifier")


def create_bundle(
    layers: Path,
    destination: Path,
    version: str,
    *,
    runtime_source_root: Path = REPO,
) -> Path:
    cpython = layers / "cpython-3.11"
    framework = layers / "framework-mlx-base"
    if not cpython.is_dir() or not framework.is_dir():
        raise FileNotFoundError("Export cpython-3.11 and framework-mlx-base first")
    bundle = destination / "AI2AppsOmlxRuntime.bundle"
    contents = bundle / "Contents"
    runtime = contents / "Resources" / "Runtime"
    (contents / "MacOS").mkdir(parents=True)
    runtime.mkdir(parents=True)
    executable = contents / "MacOS" / "AI2AppsOmlxRuntime"
    # A macOS code bundle needs a Mach-O main executable for deterministic
    # bundle sealing. Do not copy a sealed system executable such as
    # /usr/bin/true: current macOS ships it as a universal arm64e system binary
    # whose reconstructed signature does not survive an HFS+ DMG round trip.
    # The exported arm64 CPython launcher is ordinary Mach-O code and is already
    # part of this Runtime. The bundle is never launched through this marker;
    # Model Workers use the descriptor's private CPython path.
    shutil.copyfile(cpython / "bin" / "python3.11", executable)
    executable.chmod(0o755)
    (contents / "Info.plist").write_bytes(
        plistlib.dumps(
            {
                "CFBundleIdentifier": "com.ai2apps.runtime.omlx",
                "CFBundleName": "AI2Apps oMLX Runtime",
                "CFBundleExecutable": "AI2AppsOmlxRuntime",
                "CFBundlePackageType": "BNDL",
                "CFBundleShortVersionString": version,
                "CFBundleVersion": version,
            }
        )
    )
    copy_tree(cpython, runtime / "Python" / "cpython-3.11")
    copy_tree(framework, runtime / "Python" / "framework-mlx-base")
    copy_tree(
        runtime_source_root / "ai2apps",
        runtime / "app" / "ai2apps",
        runtime_source=True,
    )
    copy_tree(
        runtime_source_root / "omlx",
        runtime / "app" / "omlx",
        runtime_source=True,
    )
    sanitize_symlinks(bundle)
    return bundle


def create_knowledge_bundle(layers: Path, destination: Path, version: str) -> Path:
    """Build the isolated LanceDB/embedding Runtime using the release signer."""

    cpython = layers / "cpython-3.11"
    framework = layers / "framework-knowledge-rag"
    if not cpython.is_dir() or not framework.is_dir():
        raise FileNotFoundError(
            "Export cpython-3.11 and framework-knowledge-rag first"
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
    sanitize_symlinks(bundle)
    return bundle


def descriptor(
    version: str,
    signing: str,
    team_id: str | None,
    capabilities: list[str],
) -> dict:
    return {
        "schema": "ai2apps.inference-runtime/v1",
        "service_id": "ai2apps.runtime.omlx",
        "version": version,
        "protocol": "ai2apps-model-worker/v1",
        "capabilities": capabilities,
        "python": "Contents/Resources/Runtime/Python/cpython-3.11/bin/python3.11",
        "python_home": "Contents/Resources/Runtime/Python/cpython-3.11",
        "framework_site_packages": "Contents/Resources/Runtime/Python/framework-mlx-base/lib/python3.11/site-packages",
        "launcher": "Contents/Resources/Runtime/app/ai2apps/model_worker/launcher.py",
        "payload": {
            "type": "dmg",
            "path": "variants/darwin-arm64/AI2AppsOmlxRuntime.dmg",
            "root": "AI2AppsOmlxRuntime.bundle",
        },
        "distribution": {"signing": signing, "team_id": team_id},
    }


def knowledge_descriptor(
    version: str,
    signing: str,
    team_id: str | None,
    capabilities: list[str],
) -> dict:
    return {
        "schema": "ai2apps.knowledge-runtime/v1",
        "service_id": "ai2apps.runtime.knowledge-rag",
        "version": version,
        "protocol": "ai2apps-knowledge-vector-worker/v1",
        "capabilities": capabilities,
        "python": "Contents/Resources/Runtime/Python/cpython-3.11/bin/python3.11",
        "python_home": "Contents/Resources/Runtime/Python/cpython-3.11",
        "framework_site_packages": (
            "Contents/Resources/Runtime/Python/framework-knowledge-rag/"
            "lib/python3.11/site-packages"
        ),
        "payload": {
            "type": "dmg",
            "path": "variants/darwin-arm64/AI2AppsKnowledgeRagRuntime.dmg",
            "root": "AI2AppsKnowledgeRagRuntime.bundle",
        },
        "distribution": {"signing": signing, "team_id": team_id},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--layers", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--sign-identity", default="-")
    parser.add_argument(
        "--prepared-dmg",
        type=Path,
        help="Use an already signed/stapled Runtime DMG instead of rebuilding it",
    )
    parser.add_argument(
        "--prepared-signing",
        choices=("development", "developer-id"),
        default="development",
    )
    parser.add_argument("--team-id")
    parser.add_argument("--private-key", type=Path)
    parser.add_argument("--keychain-secret")
    parser.add_argument("--keychain-namespace")
    parser.add_argument("--publisher-id")
    parser.add_argument("--key-id")
    parser.add_argument(
        "--development-publisher-id",
        help=(
            "Override service.yaml publisher.id for an ad-hoc development "
            "artifact so it does not replace the production trust record"
        ),
    )
    parser.add_argument(
        "--work-directory",
        type=Path,
        help="Preserve an explicit empty build directory for diagnostics",
    )
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    manifest = yaml.safe_load((source / "service.yaml").read_text(encoding="utf-8"))
    service_id = str(manifest["id"])
    if service_id not in {
        "ai2apps.runtime.omlx",
        "ai2apps.runtime.knowledge-rag",
    }:
        raise ValueError(f"unsupported native Runtime service: {service_id}")
    knowledge_runtime = service_id == "ai2apps.runtime.knowledge-rag"
    payload_name = (
        "AI2AppsKnowledgeRagRuntime.dmg"
        if knowledge_runtime
        else "AI2AppsOmlxRuntime.dmg"
    )
    version = str(manifest["version"])
    package_slug = "knowledge-rag" if knowledge_runtime else "omlx"
    output = (
        args.output
        or source / "dist" / f"ai2apps-runtime-{package_slug}-{version}.ai2service"
    ).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.work_directory is not None:
        root = args.work_directory.resolve()
        root.mkdir(parents=True, exist_ok=False)
        work = nullcontext(str(root))
    else:
        work = tempfile.TemporaryDirectory(prefix="ai2apps-omlx-runtime-")
    with work as temporary:
        root = Path(temporary)
        if args.prepared_dmg is not None:
            dmg = args.prepared_dmg.resolve(strict=True)
            signing = args.prepared_signing
            team_id = args.team_id
            # The standard DMG builder verifies the image checksum before it
            # signs the final file. Running `hdiutil verify` on that signed
            # artifact can update image metadata and invalidate the outer
            # signature, so prepared release artifacts are authenticated by
            # their whole-file code signature instead.
            run("/usr/bin/codesign", "--verify", "--strict", str(dmg))
            if signing == "developer-id":
                if not team_id:
                    raise ValueError("--team-id is required for a Developer ID DMG")
                run("/usr/bin/xcrun", "stapler", "validate", str(dmg))
                # A stapled DMG contains an Apple ticket appended after the
                # original code signature. Validate the release trust chain
                # with Gatekeeper instead of treating that ticket as an
                # unsigned content mutation via a bare codesign check.
                run(
                    "/usr/sbin/spctl",
                    "-a",
                    "-t",
                    "open",
                    "--context",
                    "context:primary-signature",
                    str(dmg),
                )
        else:
            if args.sign_identity != "-":
                raise ValueError(
                    "Release packaging is two-phase: build/sign/notarize the DMG, "
                    "then pass it with --prepared-dmg --prepared-signing developer-id"
                )
            image_source = root / "image"
            image_source.mkdir()
            bundle = (
                create_knowledge_bundle(
                    args.layers.resolve(strict=True), image_source, version
                )
                if knowledge_runtime
                else create_bundle(
                    args.layers.resolve(strict=True), image_source, version
                )
            )
            team_id = sign_runtime(bundle, args.sign_identity)
            dmg = root / payload_name
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
                str(image_source),
                str(dmg),
            )
            run(
                "/usr/bin/codesign",
                "--force",
                "--sign",
                args.sign_identity,
                str(dmg),
            )
            signing = "development"
        stage = root / "package"
        shutil.copytree(source, stage, ignore=shutil.ignore_patterns("dist", "README.md"))
        if args.development_publisher_id:
            if signing != "development":
                raise ValueError(
                    "--development-publisher-id is only valid for development signing"
                )
            staged_service_path = stage / "service.yaml"
            staged_service = yaml.safe_load(staged_service_path.read_text(encoding="utf-8"))
            staged_service.setdefault("publisher", {})["id"] = (
                args.development_publisher_id
            )
            staged_service_path.write_text(
                yaml.safe_dump(staged_service, sort_keys=False),
                encoding="utf-8",
            )
        variant = stage / "variants" / "darwin-arm64"
        variant.mkdir(parents=True)
        # The runtime descriptor and variant contract deliberately use a stable
        # in-package payload path. Release build filenames may contain versions
        # or signing suffixes, but those names must not leak into the archive or
        # variant selection will reject the otherwise compatible payload.
        shutil.copy2(dmg, variant / payload_name)
        (stage / "META" / "runtime-manifest.json").write_text(
            json.dumps(
                (
                    knowledge_descriptor
                    if knowledge_runtime
                    else descriptor
                )(
                    version,
                    signing,
                    team_id,
                    list(manifest.get("capabilities", [])),
                ),
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        if signing == "development":
            local = build_local_service_package(
                stage,
                output,
                args.private_key.resolve(strict=True) if args.private_key is not None else None,
                keychain_secret=args.keychain_secret,
                keychain_namespace=args.keychain_namespace,
                key_id=args.key_id,
            )
            artifact_hash = hashlib.sha256()
            with output.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    artifact_hash.update(chunk)
            result = {
                "artifact": str(output),
                "publisher": local["publisher"],
                "packageId": (
                    "ai2apps/runtime-knowledge-rag"
                    if knowledge_runtime
                    else "ai2apps/runtime-omlx"
                ),
                "version": version,
                "packageDigest": local["digest"],
                "sha256": artifact_hash.hexdigest(),
                "size": output.stat().st_size,
            }
        else:
            inspected = build_package(stage, output)
            result = {
                "artifact": str(output),
                "packageId": inspected.manifest["package"]["id"],
                "version": inspected.manifest["package"]["version"],
                "sha256": inspected.sha256,
                "size": inspected.size,
            }
        if signing != "development" and (
            args.private_key is not None or args.keychain_secret is not None
        ):
            if not args.publisher_id or not args.key_id:
                raise ValueError("--publisher-id and --key-id are required for release signing")
            if args.private_key is not None and args.keychain_secret is not None:
                raise ValueError("Choose either --private-key or --keychain-secret")
            if args.private_key is not None:
                private_key = args.private_key.resolve(strict=True).read_text(encoding="ascii")
            else:
                if not args.keychain_namespace:
                    raise ValueError("--keychain-namespace is required with --keychain-secret")
                backend = create_secret_backend(
                    Path.home() / ".omlx" / "platform" / "secrets",
                    namespace=args.keychain_namespace,
                )
                private_key = backend.load(args.keychain_secret)
            envelope = create_signature_envelope(
                inspected,
                private_key,
                publisher_id=args.publisher_id,
                publisher_key_id=args.key_id,
            )
            envelope_path = output.with_suffix(output.suffix + ".envelope.json")
            temporary_envelope = envelope_path.with_name(
                f".{envelope_path.name}.{os.getpid()}.tmp"
            )
            temporary_envelope.write_text(
                json.dumps(envelope, indent=2) + "\n", encoding="utf-8"
            )
            os.replace(temporary_envelope, envelope_path)
            result["envelope"] = str(envelope_path)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
