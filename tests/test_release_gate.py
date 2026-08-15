import io
import json
import tarfile
import zipfile
from pathlib import Path

from ai2apps.model_installer import CATALOG
from ai2apps.release_gate import (
    check_archives,
    check_catalog,
    check_evidence,
    evidence_template,
    main,
)


def test_catalog_release_checks_pass():
    checks = []
    check_catalog(checks)

    assert checks
    assert {item.status for item in checks} == {"pass"}
    assert sum(item.check == "catalog.pinned_revision" for item in checks) == 3


def test_evidence_gate_enforces_parity_speed_and_memory(tmp_path: Path):
    evidence = evidence_template()
    for recipe in CATALOG:
        model = evidence["models"][recipe["id"]]
        for key in model["correctness"]:
            if key != "long_decode_tokens":
                model["correctness"][key] = True
        model["performance"] = {
            "resident_tps": 100.0,
            "oracle_tps": 86.0,
            "deployed_tps": 30.0,
        }
        model["memory"] = {"resident_gb": 100.0, "cache_gb": 60.0}
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(evidence))
    checks = []

    check_evidence(checks, path)

    assert checks
    assert {item.status for item in checks} == {"pass"}


def test_preflight_cli_writes_reports(tmp_path: Path):
    json_path = tmp_path / "gate.json"
    markdown_path = tmp_path / "gate.md"

    result = main(
        [
            "--mode",
            "preflight",
            "--json",
            str(json_path),
            "--markdown",
            str(markdown_path),
        ]
    )

    assert result == 0
    assert json.loads(json_path.read_text())["overall"] == "pass"
    assert "Overall: **PASS**" in markdown_path.read_text()


def _write_test_wheel(path: Path, requirement: str) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("ai2apps/model_installer.py", "")
        archive.writestr(
            "ai2apps/engines/deepseek_v4_flash/scope-pack.json", "{}"
        )
        archive.writestr(
            "ai2apps/engines/qwen3_6_35b_a3b/scope-pack.json", "{}"
        )
        archive.writestr("ai2apps/remote/bin/darwin-arm64/frpc", "arm64")
        archive.writestr("ai2apps/remote/bin/darwin-x86_64/frpc", "x86_64")
        archive.writestr("ai2apps/remote/third_party/frp-LICENSE", "license")
        archive.writestr(
            "ai2apps/remote/third_party/frp-0.62.1-source.json", "{}"
        )
        archive.writestr(
            "ai2apps-0.1.dist-info/METADATA",
            f"Metadata-Version: 2.4\nName: ai2apps\nVersion: 0.1\nRequires-Dist: {requirement}\n",
        )


def test_archive_gate_accepts_index_dependency(tmp_path: Path):
    wheel = tmp_path / "ai2apps.whl"
    _write_test_wheel(wheel, "mlx-lm==0.31.3")
    checks = []

    check_archives(checks, [wheel])

    dependency = next(
        item for item in checks if item.check == "package.index_dependencies"
    )
    assert dependency.status == "pass"


def test_archive_gate_rejects_direct_url_dependency(tmp_path: Path):
    wheel = tmp_path / "ai2apps.whl"
    _write_test_wheel(
        wheel,
        "mlx-lm @ git+https://github.com/ml-explore/mlx-lm@deadbeef",
    )
    checks = []

    check_archives(checks, [wheel])

    dependency = next(
        item for item in checks if item.check == "package.index_dependencies"
    )
    assert dependency.status == "fail"
    assert "mlx-lm" in dependency.detail


def test_sdist_gate_reads_top_level_metadata_when_egg_info_is_present(
    tmp_path: Path,
):
    sdist = tmp_path / "ai2apps.tar.gz"
    metadata = (
        b"Metadata-Version: 2.4\nName: ai2apps\nVersion: 0.1\n"
        b"Requires-Dist: mlx-lm==0.31.3\n"
    )
    files = {
        "ai2apps-0.1/PKG-INFO": metadata,
        "ai2apps-0.1/ai2apps.egg-info/PKG-INFO": metadata,
        "ai2apps-0.1/ai2apps/model_installer.py": b"",
        "ai2apps-0.1/ai2apps/engines/deepseek_v4_flash/scope-pack.json": b"{}",
        "ai2apps-0.1/ai2apps/engines/qwen3_6_35b_a3b/scope-pack.json": b"{}",
        "ai2apps-0.1/ai2apps/remote/bin/darwin-arm64/frpc": b"arm64",
        "ai2apps-0.1/ai2apps/remote/bin/darwin-x86_64/frpc": b"x86_64",
        "ai2apps-0.1/ai2apps/remote/third_party/frp-LICENSE": b"license",
        "ai2apps-0.1/ai2apps/remote/third_party/frp-0.62.1-source.json": b"{}",
    }
    with tarfile.open(sdist, "w:gz") as archive:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    checks = []

    check_archives(checks, [sdist])

    assert {item.status for item in checks} == {"pass"}


def test_archive_gate_rejects_private_and_runtime_data(tmp_path: Path):
    wheel = tmp_path / "ai2apps.whl"
    _write_test_wheel(wheel, "mlx-lm==0.31.3")
    with zipfile.ZipFile(wheel, "a") as archive:
        archive.writestr("ai2apps/platform/secrets/vault.key", "not-a-real-key")
        archive.writestr("ai2apps/cache.private.pem", "not-a-real-key")
        archive.writestr("ai2apps/platform/ai2apps-platform.sqlite3", "")
    checks = []

    check_archives(checks, [wheel])

    package = next(item for item in checks if item.check == "package.archive")
    assert package.status == "fail"
    assert "leaked=3" in package.detail
