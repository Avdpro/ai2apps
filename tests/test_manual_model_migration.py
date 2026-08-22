from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def migration_module():
    local = Path(__file__).with_name("migrate-installed-model.py")
    packaged = (
        Path(__file__).parents[1]
        / "apps"
        / "ai2apps-acefox"
        / "scripts"
        / "migrate-installed-model.py"
    )
    path = local if local.exists() else packaged
    spec = importlib.util.spec_from_file_location("model_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def model_fixture(root: Path, external: Path) -> Path:
    model = root / "source"
    model.mkdir()
    (model / "config.json").write_text("{}", encoding="utf-8")
    external.write_bytes(b"weights")
    (model / "model.safetensors").symlink_to(external)
    return model


def test_migration_materializes_external_file_links(tmp_path: Path, migration_module) -> None:
    source = model_fixture(tmp_path, tmp_path / "external.safetensors")
    destination = tmp_path / "models" / "owner" / "model"
    inventory = migration_module.validate_source(
        source, "owner/model", "a" * 40
    )
    staging = tmp_path / "staging"

    migration_module.copy_tree(source, staging, allow_full_copy=True)

    copied = staging / "model.safetensors"
    assert copied.read_bytes() == b"weights"
    assert not copied.is_symlink()
    assert inventory == {"files": 2, "materialized_links": 1, "logical_bytes": 9}
    assert destination.exists() is False


def test_migration_rejects_mismatched_source_contract(tmp_path: Path, migration_module) -> None:
    source = model_fixture(tmp_path, tmp_path / "external.safetensors")
    contract = source / ".ai2apps" / "source.json"
    contract.parent.mkdir()
    contract.write_text(
        json.dumps({"repo_id": "other/model", "revision": "b" * 40}),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="does not match"):
        migration_module.validate_source(source, "owner/model", "a" * 40)
