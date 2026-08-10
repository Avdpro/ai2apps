import json
import zipfile
from pathlib import Path

from dynamoe.model_installer import CATALOG
from dynamoe.release_gate import (
    check_catalog,
    check_archives,
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
        archive.writestr("dynamoe/model_installer.py", "")
        archive.writestr(
            "dynamoe/engines/deepseek_v4_flash/scope-pack.json", "{}"
        )
        archive.writestr(
            "dynamoe/engines/qwen3_6_35b_a3b/scope-pack.json", "{}"
        )
        archive.writestr(
            "dynamoe-0.1.dist-info/METADATA",
            f"Metadata-Version: 2.4\nName: dynamoe\nVersion: 0.1\nRequires-Dist: {requirement}\n",
        )


def test_archive_gate_accepts_index_dependency(tmp_path: Path):
    wheel = tmp_path / "dynamoe.whl"
    _write_test_wheel(wheel, "mlx-lm==0.31.3")
    checks = []

    check_archives(checks, [wheel])

    dependency = next(
        item for item in checks if item.check == "package.index_dependencies"
    )
    assert dependency.status == "pass"


def test_archive_gate_rejects_direct_url_dependency(tmp_path: Path):
    wheel = tmp_path / "dynamoe.whl"
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
