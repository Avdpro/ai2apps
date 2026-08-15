"""Reproducible release checks for AI2Apps Cache-MoE engines."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
import tarfile
import time
import zipfile
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from ai2apps._version import __version__
from ai2apps.model_installer import CATALOG, AI2AppsInstaller

EVIDENCE_FORMAT = "ai2apps-release-evidence"
EVIDENCE_VERSION = 1
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class GateCheck:
    check: str
    status: str
    detail: str
    model_id: str | None = None


def _check(
    checks: list[GateCheck],
    name: str,
    condition: bool,
    detail: str,
    *,
    model_id: str | None = None,
) -> None:
    checks.append(
        GateCheck(name, "pass" if condition else "fail", detail, model_id)
    )


def _pending(
    checks: list[GateCheck], name: str, detail: str, model_id: str | None = None
) -> None:
    checks.append(GateCheck(name, "pending", detail, model_id))


def _scope_pack(recipe: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    root = Path(__file__).parent
    path = root / recipe["engine"]["scope_pack"]
    return path, json.loads(path.read_text())


def check_catalog(checks: list[GateCheck]) -> None:
    expected_ids = {recipe["id"] for recipe in CATALOG}
    exposed = {item["id"] for item in AI2AppsInstaller.catalog()}
    _check(
        checks,
        "catalog.engines",
        exposed == expected_ids,
        f"exposed {len(exposed)}/{len(expected_ids)} dedicated engines",
    )
    for recipe in CATALOG:
        model_id = recipe["id"]
        source = recipe["sources"][0]
        revision = str(source.get("revision", ""))
        _check(
            checks,
            "catalog.pinned_revision",
            bool(_SHA_RE.fullmatch(revision)),
            f"{source['repo_id']}@{revision or '<missing>'}",
            model_id=model_id,
        )
        pack_path, pack = _scope_pack(recipe)
        profile = pack_path.parent / pack["profile"]["file"]
        actual = hashlib.sha256(profile.read_bytes()).hexdigest()
        expected = pack["profile"]["sha256"]
        _check(
            checks,
            "scope_pack.checksum",
            actual == expected,
            f"{pack['id']} {pack['pack_version']} sha256={actual}",
            model_id=model_id,
        )
        compatible_revision = (
            pack.get("compatibility", {})
            .get("source_revisions", {})
            .get(model_id)
        )
        _check(
            checks,
            "scope_pack.checkpoint_compatibility",
            compatible_revision == revision,
            f"Scope Pack declares checkpoint {compatible_revision!s}",
            model_id=model_id,
        )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def check_installations(checks: list[GateCheck], model_root: Path) -> None:
    for recipe in CATALOG:
        model_id = recipe["id"]
        source = recipe["sources"][0]
        model_dir = model_root / source["repo_id"]
        manifest_path = model_dir / "ai2apps-model.json"
        if not manifest_path.is_file():
            legacy_manifest = model_dir / "dynamoe-model.json"
            if legacy_manifest.is_file():
                manifest_path = legacy_manifest
            else:
                _pending(
                    checks,
                    "install.present",
                    f"not installed at {model_dir}",
                    model_id,
                )
                continue
        try:
            manifest = _read_json(manifest_path)
        except (OSError, TypeError, json.JSONDecodeError) as exc:
            _check(
                checks,
                "install.manifest",
                False,
                f"invalid {manifest_path}: {exc}",
                model_id=model_id,
            )
            continue
        expected_source = {
            "provider": source["id"],
            "repo_id": source["repo_id"],
            "revision": source["revision"],
        }
        _check(
            checks,
            "install.manifest",
            manifest.get("format") in {
                "ai2apps-cache-moe-model",
                "dynamoe-cache-moe-model",
            }
            and int(manifest.get("version", 0)) >= 2,
            f"manifest version {manifest.get('version')!r}",
            model_id=model_id,
        )
        _check(
            checks,
            "install.pinned_source",
            manifest.get("source") == expected_source,
            f"expected {source['repo_id']}@{source['revision']}",
            model_id=model_id,
        )
        _check(
            checks,
            "install.conversion",
            manifest.get("conversion") == recipe["conversion"],
            f"expected {recipe['conversion']['variant']}",
            model_id=model_id,
        )
        scope = manifest.get("scope", {}).get("pack", {})
        _pack_path, pack = _scope_pack(recipe)
        _check(
            checks,
            "install.scope_pack",
            scope.get("sha256") == pack["profile"]["sha256"]
            and scope.get("version") == pack["pack_version"],
            f"expected {pack['id']} {pack['pack_version']}",
            model_id=model_id,
        )
        store = Path(str(manifest.get("expert_store", ""))).expanduser()
        store_manifest = store / "manifest.json"
        _check(
            checks,
            "install.expert_store",
            store_manifest.is_file(),
            str(store_manifest),
            model_id=model_id,
        )
        if store_manifest.is_file():
            try:
                store_metadata = _read_json(store_manifest)
            except (OSError, TypeError, json.JSONDecodeError):
                store_metadata = {}
            _check(
                checks,
                "install.expert_store_revision",
                store_metadata.get("source")
                == {
                    "repo_id": source["repo_id"],
                    "revision": source["revision"],
                }
                and store_metadata.get("conversion") == recipe["conversion"],
                f"expected {source['revision']} / {recipe['conversion']['variant']}",
                model_id=model_id,
            )


def _archive_names(path: Path) -> set[str]:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            return set(archive.namelist())
    with tarfile.open(path) as archive:
        return set(archive.getnames())


def _archive_core_metadata(path: Path) -> str:
    """Read Core Metadata without installing an archive."""

    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            members = [
                name
                for name in archive.namelist()
                if name.endswith(".dist-info/METADATA")
            ]
            if len(members) != 1:
                raise ValueError(f"expected one METADATA file, found {len(members)}")
            return archive.read(members[0]).decode("utf-8")
    with tarfile.open(path) as archive:
        candidates = [
            member
            for member in archive.getmembers()
            if member.name.endswith("/PKG-INFO")
        ]
        minimum_depth = min(
            (len(PurePosixPath(member.name).parts) for member in candidates),
            default=0,
        )
        members = [
            member
            for member in candidates
            if len(PurePosixPath(member.name).parts) == minimum_depth
        ]
        if len(members) != 1:
            raise ValueError(
                f"expected one top-level PKG-INFO file, found {len(members)}"
            )
        stream = archive.extractfile(members[0])
        if stream is None:
            raise ValueError("PKG-INFO is not readable")
        return stream.read().decode("utf-8")


def check_archives(checks: list[GateCheck], archives: Iterable[Path]) -> None:
    for archive in archives:
        try:
            names = _archive_names(archive)
        except (OSError, tarfile.TarError, zipfile.BadZipFile) as exc:
            _check(checks, "package.archive", False, f"{archive}: {exc}")
            continue
        required_suffixes = (
            "ai2apps/model_installer.py",
            "ai2apps/engines/deepseek_v4_flash/scope-pack.json",
            "ai2apps/engines/qwen3_6_35b_a3b/scope-pack.json",
            "ai2apps/remote/bin/darwin-arm64/frpc",
            "ai2apps/remote/bin/darwin-x86_64/frpc",
            "ai2apps/remote/third_party/frp-LICENSE",
            "ai2apps/remote/third_party/frp-0.62.1-source.json",
        )
        missing = [
            suffix
            for suffix in required_suffixes
            if not any(name.endswith(suffix) for name in names)
        ]
        forbidden_names = {
            "vault.key",
            "vault.aesgcm",
        }
        forbidden_suffixes = (
            ".private.pem",
            ".sqlite",
            ".sqlite3",
            ".sqlite3-shm",
            ".sqlite3-wal",
        )
        leaked = [
            name
            for name in names
            if "/artifacts/" in f"/{name}"
            or "/expert-store/" in f"/{name}"
            or "/output/" in f"/{name}"
            or PurePosixPath(name).name in forbidden_names
            or PurePosixPath(name).name.endswith(forbidden_suffixes)
        ]
        _check(
            checks,
            "package.archive",
            not missing and not leaked,
            f"{archive.name}: missing={missing or 'none'}, leaked={len(leaked)}",
        )
        try:
            metadata = _archive_core_metadata(archive)
            direct_dependencies = [
                line.removeprefix("Requires-Dist:").strip()
                for line in metadata.splitlines()
                if line.startswith("Requires-Dist:")
                and re.search(r"\s@\s+(?:git\+|https?://)", line)
            ]
        except (OSError, UnicodeDecodeError, ValueError, tarfile.TarError, zipfile.BadZipFile) as exc:
            _check(checks, "package.index_dependencies", False, f"{archive.name}: {exc}")
        else:
            _check(
                checks,
                "package.index_dependencies",
                not direct_dependencies,
                (
                    f"{archive.name}: index-only dependencies"
                    if not direct_dependencies
                    else f"{archive.name}: direct dependencies={direct_dependencies}"
                ),
            )


def check_evidence(checks: list[GateCheck], evidence_path: Path) -> None:
    try:
        evidence = _read_json(evidence_path)
    except (OSError, TypeError, json.JSONDecodeError) as exc:
        _check(checks, "benchmark.evidence", False, str(exc))
        return
    _check(
        checks,
        "benchmark.evidence_format",
        evidence.get("format") == EVIDENCE_FORMAT
        and evidence.get("version") == EVIDENCE_VERSION,
        f"{evidence.get('format')!r} v{evidence.get('version')!r}",
    )
    models = evidence.get("models", {})
    for recipe in CATALOG:
        model_id = recipe["id"]
        result = models.get(model_id)
        if not isinstance(result, dict):
            _pending(checks, "benchmark.model", "no evidence", model_id)
            continue
        expected_revision = recipe["sources"][0]["revision"]
        _check(
            checks,
            "benchmark.checkpoint_revision",
            result.get("checkpoint_revision") == expected_revision,
            f"expected {expected_revision}",
            model_id=model_id,
        )
        correctness = result.get("correctness", {})
        performance = result.get("performance", {})
        memory = result.get("memory", {})
        required_parity = [
            "top10_parity",
            "zero_runtime_misses",
            "long_decode_parity",
            "multi_turn_parity",
        ]
        if recipe["family"] == "qwen3_6":
            required_parity.extend(["three_engine_parity", "auto_l1_parity"])
        parity_ok = all(correctness.get(key) is True for key in required_parity)
        _check(
            checks,
            "benchmark.correctness",
            parity_ok and int(correctness.get("long_decode_tokens", 0)) >= 1024,
            f"required={required_parity}, long={correctness.get('long_decode_tokens', 0)}",
            model_id=model_id,
        )
        resident_tps = float(performance.get("resident_tps", 0) or 0)
        oracle_tps = float(performance.get("oracle_tps", 0) or 0)
        ratio = oracle_tps / resident_tps if resident_tps > 0 else 0.0
        _check(
            checks,
            "benchmark.performance",
            ratio >= 0.85,
            f"oracle={oracle_tps:.3f} TPS, resident={resident_tps:.3f} TPS, ratio={ratio:.1%}",
            model_id=model_id,
        )
        resident_gb = float(memory.get("resident_gb", 0) or 0)
        cache_gb = float(memory.get("cache_gb", 0) or 0)
        _check(
            checks,
            "benchmark.memory",
            resident_gb > 0 and 0 < cache_gb < resident_gb,
            f"cache={cache_gb:.2f} GiB, resident={resident_gb:.2f} GiB",
            model_id=model_id,
        )


def run_tests(checks: list[GateCheck], repo_root: Path) -> None:
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests/test_ai2apps_installer.py",
        "tests/test_ai2apps_scope_pack.py",
        "tests/test_hf_downloader.py",
        "tests/test_release_gate.py",
        "tests/test_fusion_engine.py",
        "tests/test_fusion_profiles.py",
        "tests/test_fusion_transport.py",
    ]
    completed = subprocess.run(
        command, cwd=repo_root, text=True, capture_output=True, check=False
    )
    output = (completed.stdout + "\n" + completed.stderr).strip().splitlines()
    detail = output[-1] if output else f"exit {completed.returncode}"
    _check(checks, "tests.focused", completed.returncode == 0, detail)


def _overall(checks: list[GateCheck]) -> str:
    if any(item.status == "fail" for item in checks):
        return "fail"
    if any(item.status == "pending" for item in checks):
        return "pending"
    return "pass"


def _markdown(report: dict[str, Any]) -> str:
    icons = {"pass": "PASS", "fail": "FAIL", "pending": "PENDING"}
    lines = [
        "# AI2Apps Release Gate",
        "",
        f"Overall: **{report['overall'].upper()}**",
        "",
        f"AI2Apps: `{report['ai2apps_version']}`",
        "",
        "| Status | Model | Check | Detail |",
        "|---|---|---|---|",
    ]
    for item in report["checks"]:
        detail = str(item["detail"]).replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {icons[item['status']]} | {item['model_id'] or '-'} | "
            f"`{item['check']}` | {detail} |"
        )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("preflight", "installed", "release"), default="preflight"
    )
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--archive", type=Path, action="append", default=[])
    parser.add_argument("--run-tests", action="store_true")
    parser.add_argument("--json", type=Path, dest="json_path")
    parser.add_argument("--markdown", type=Path, dest="markdown_path")
    parser.add_argument("--write-evidence-template", type=Path)
    return parser


def evidence_template() -> dict[str, Any]:
    models: dict[str, Any] = {}
    for recipe in CATALOG:
        parity = {
            "top10_parity": False,
            "zero_runtime_misses": False,
            "long_decode_parity": False,
            "long_decode_tokens": 1024,
            "multi_turn_parity": False,
        }
        if recipe["family"] == "qwen3_6":
            parity.update({"three_engine_parity": False, "auto_l1_parity": False})
        models[recipe["id"]] = {
            "checkpoint_revision": recipe["sources"][0]["revision"],
            "correctness": parity,
            "performance": {
                "resident_tps": 0.0,
                "oracle_tps": 0.0,
                "deployed_tps": 0.0,
            },
            "memory": {"resident_gb": 0.0, "cache_gb": 0.0},
        }
    return {"format": EVIDENCE_FORMAT, "version": EVIDENCE_VERSION, "models": models}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.write_evidence_template:
        args.write_evidence_template.parent.mkdir(parents=True, exist_ok=True)
        args.write_evidence_template.write_text(
            json.dumps(evidence_template(), indent=2, sort_keys=True) + "\n"
        )

    checks: list[GateCheck] = []
    check_catalog(checks)
    check_archives(checks, args.archive)
    repo_root = Path(__file__).parents[1]
    if args.run_tests:
        run_tests(checks, repo_root)
    if args.mode in {"installed", "release"}:
        if args.model_dir:
            check_installations(checks, args.model_dir.expanduser().resolve())
        else:
            _check(checks, "install.model_dir", False, "--model-dir is required")
    if args.mode == "release":
        if args.evidence:
            check_evidence(checks, args.evidence)
        else:
            _check(checks, "benchmark.evidence", False, "--evidence is required")

    report = {
        "format": "ai2apps-release-gate-report",
        "version": 1,
        "created_at": time.time(),
        "ai2apps_version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "mode": args.mode,
        "overall": _overall(checks),
        "checks": [asdict(item) for item in checks],
    }
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(encoded)
    if args.markdown_path:
        args.markdown_path.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_path.write_text(_markdown(report))
    print(_markdown(report), end="")
    return 0 if report["overall"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
