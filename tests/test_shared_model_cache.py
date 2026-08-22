from __future__ import annotations

import hashlib
import json
import os
import queue
from multiprocessing import get_context
from pathlib import Path

import pytest
from ai2apps.shared_model_cache import (
    SharedModelCacheError,
    collect_unreferenced_hf_snapshots,
    list_shared_model_references,
    mark_shared_model_snapshot_managed,
    publish_configured_shared_model_reference,
    publish_shared_model_reference,
    reconcile_configured_shared_model_references,
    remove_shared_model_reference,
    shared_model_cache_gate,
)


def _publish_reference_worker(
    hub_value: str,
    instance_id: str,
    repo_id: str,
    revision: str,
    events,
) -> None:
    events.put("started")
    publish_shared_model_reference(
        Path(hub_value),
        instance_id=instance_id,
        repo_id=repo_id,
        revision=revision,
    )
    events.put("published")


def _snapshot(hub: Path, repo_id: str, revision: str, payload: bytes) -> Path:
    repo = hub / ("models--" + repo_id.replace("/", "--"))
    blob = repo / "blobs" / hashlib.sha256(payload).hexdigest()
    blob.parent.mkdir(parents=True, exist_ok=True)
    blob.write_bytes(payload)
    snapshot = repo / "snapshots" / revision
    snapshot.mkdir(parents=True)
    (snapshot / "config.json").symlink_to(
        Path(os.path.relpath(blob, snapshot))
    )
    return snapshot


def test_reference_is_owner_only_and_round_trips(tmp_path: Path):
    hub = tmp_path / "hub"
    revision = "a" * 40

    published = publish_shared_model_reference(
        hub,
        instance_id="app-one",
        repo_id="owner/model",
        revision=revision,
    )

    assert list_shared_model_references(hub) == (published,)
    root = hub / ".ai2apps-references"
    assert root.stat().st_mode & 0o777 == 0o700
    assert (root / "app-one").stat().st_mode & 0o777 == 0o700
    reference_file = next((root / "app-one").iterdir())
    assert reference_file.stat().st_mode & 0o777 == 0o600
    assert remove_shared_model_reference(
        hub,
        instance_id="app-one",
        repo_id="owner/model",
        revision=revision,
    )
    assert list_shared_model_references(hub) == ()


def test_reconcile_publishes_missing_and_removes_only_current_instance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    model_root = tmp_path / "model-weights"
    hub = model_root / "huggingface" / "hub"
    monkeypatch.setenv("AI2APPS_MODEL_CACHE_MODE", "shared")
    monkeypatch.setenv("AI2APPS_INSTANCE_ID", "app-one")
    monkeypatch.setenv("AI2APPS_MODEL_CACHE_ROOT", str(model_root))
    monkeypatch.setenv("HF_HUB_CACHE", str(hub))
    publish_shared_model_reference(
        hub, instance_id="app-one", repo_id="owner/stale", revision="a" * 40
    )
    publish_shared_model_reference(
        hub, instance_id="app-two", repo_id="owner/shared", revision="b" * 40
    )

    result = reconcile_configured_shared_model_references(
        (("owner/shared", "b" * 40), ("owner/new", "c" * 40))
    )

    assert result.expected_references == 2
    assert result.published_references == 2
    assert result.removed_references == 1
    references = list_shared_model_references(hub)
    assert {(item.instance_id, item.repo_id) for item in references} == {
        ("app-one", "owner/shared"),
        ("app-one", "owner/new"),
        ("app-two", "owner/shared"),
    }


def test_reconcile_invalid_existing_reference_fails_before_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    model_root = tmp_path / "model-weights"
    hub = model_root / "huggingface" / "hub"
    monkeypatch.setenv("AI2APPS_MODEL_CACHE_MODE", "shared")
    monkeypatch.setenv("AI2APPS_INSTANCE_ID", "app-one")
    monkeypatch.setenv("AI2APPS_MODEL_CACHE_ROOT", str(model_root))
    monkeypatch.setenv("HF_HUB_CACHE", str(hub))
    current = publish_shared_model_reference(
        hub, instance_id="app-one", repo_id="owner/current", revision="a" * 40
    )
    invalid = hub / ".ai2apps-references" / "app-two" / "invalid.json"
    invalid.parent.mkdir(mode=0o700)
    invalid.write_text("{}")
    invalid.chmod(0o600)

    with pytest.raises(SharedModelCacheError):
        reconcile_configured_shared_model_references((("owner/new", "b" * 40),))

    current_path = hub / ".ai2apps-references" / "app-one" / f"{current.identity}.json"
    new_identity = hashlib.sha256(
        f"model\0owner/new\0{'b' * 40}".encode()
    ).hexdigest()
    assert current_path.is_file()
    assert not (
        hub / ".ai2apps-references" / "app-one" / f"{new_identity}.json"
    ).exists()


def test_collector_gate_blocks_cross_process_reference_publication(tmp_path: Path):
    hub = tmp_path / "hub"
    context = get_context("spawn")
    events = context.Queue()
    process = context.Process(
        target=_publish_reference_worker,
        args=(str(hub), "app-two", "owner/model", "a" * 40, events),
    )

    with shared_model_cache_gate(hub, exclusive=True):
        process.start()
        assert events.get(timeout=5) == "started"
        with pytest.raises(queue.Empty):
            events.get(timeout=0.25)

    assert events.get(timeout=5) == "published"
    process.join(timeout=5)
    assert process.exitcode == 0
    assert [(item.instance_id, item.repo_id) for item in list_shared_model_references(hub)] == [
        ("app-two", "owner/model")
    ]


def test_reference_precedes_managed_marker_across_publication_failure(
    tmp_path: Path, monkeypatch
):
    import ai2apps.shared_model_cache as cache_module

    hub = tmp_path / "hub"
    snapshot = _snapshot(hub, "owner/model", "9" * 40, b"protected")
    original = cache_module._atomic_write_private

    def fail_managed_marker(path: Path, payload: bytes) -> None:
        if path.parent.name == ".ai2apps-managed":
            raise SharedModelCacheError("simulated managed marker failure")
        original(path, payload)

    monkeypatch.setattr(cache_module, "_atomic_write_private", fail_managed_marker)
    with pytest.raises(SharedModelCacheError):
        publish_shared_model_reference(
            hub,
            instance_id="app-one",
            repo_id="owner/model",
            revision="9" * 40,
        )

    report = collect_unreferenced_hf_snapshots(hub, dry_run=False)
    assert snapshot.is_dir()
    assert len(report.protected_snapshots) == 1
    assert report.collected_snapshots == ()


def test_supervised_shared_mode_publishes_to_exact_configured_hub(
    tmp_path: Path, monkeypatch
):
    model_root = tmp_path / "shared" / "model-weights"
    hub = model_root / "huggingface" / "hub"
    monkeypatch.setenv("AI2APPS_MODEL_CACHE_MODE", "shared")
    monkeypatch.setenv("AI2APPS_INSTANCE_ID", "app-one")
    monkeypatch.setenv("AI2APPS_MODEL_CACHE_ROOT", str(model_root))
    monkeypatch.setenv("HF_HUB_CACHE", str(hub))

    reference = publish_configured_shared_model_reference(
        repo_id="owner/model", revision="1" * 40
    )

    assert reference is not None
    assert list_shared_model_references(hub) == (reference,)


def test_isolated_or_unsupervised_mode_does_not_publish(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("AI2APPS_MODEL_CACHE_MODE", raising=False)
    assert (
        publish_configured_shared_model_reference(
            repo_id="owner/model", revision="2" * 40
        )
        is None
    )
    monkeypatch.setenv("AI2APPS_MODEL_CACHE_MODE", "isolated")
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hub"))
    assert (
        publish_configured_shared_model_reference(
            repo_id="owner/model", revision="2" * 40
        )
        is None
    )


def test_shared_mode_rejects_mismatched_supervisor_paths(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AI2APPS_MODEL_CACHE_MODE", "shared")
    monkeypatch.setenv("AI2APPS_INSTANCE_ID", "app-one")
    monkeypatch.setenv("AI2APPS_MODEL_CACHE_ROOT", str(tmp_path / "root"))
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "other" / "hub"))

    with pytest.raises(SharedModelCacheError):
        publish_configured_shared_model_reference(
            repo_id="owner/model", revision="3" * 40
        )


def test_shared_cache_cli_reports_counts_without_paths_or_instance(
    tmp_path: Path, monkeypatch, capsys
):
    from ai2apps.cli import _shared_cache_command

    model_root = tmp_path / "shared" / "model-weights"
    hub = model_root / "huggingface" / "hub"
    _snapshot(hub, "owner/model", "4" * 40, b"reclaimable")
    mark_shared_model_snapshot_managed(
        hub, repo_id="owner/model", revision="4" * 40
    )
    monkeypatch.setenv("AI2APPS_MODEL_CACHE_MODE", "shared")
    monkeypatch.setenv("AI2APPS_INSTANCE_ID", "secret-instance")
    monkeypatch.setenv("AI2APPS_MODEL_CACHE_ROOT", str(model_root))
    monkeypatch.setenv("HF_HUB_CACHE", str(hub))

    assert _shared_cache_command(["inspect"]) == 0
    output = capsys.readouterr().out
    report = json.loads(output)
    assert report == {
        "format": "ai2apps-shared-model-cache-report",
        "version": 1,
        "operation": "inspect",
        "scanned_snapshots": 1,
        "protected_snapshots": 0,
        "unmanaged_snapshots": 0,
        "collectible_snapshots": 1,
        "collectible_blobs": 1,
        "reclaimable_bytes": len(b"reclaimable"),
    }
    assert "secret-instance" not in output
    assert str(tmp_path) not in output


def test_collector_preserves_referenced_snapshot_and_shared_blob(tmp_path: Path):
    hub = tmp_path / "hub"
    protected_revision = "b" * 40
    stale_revision = "c" * 40
    payload = b"same immutable blob"
    protected = _snapshot(hub, "owner/model", protected_revision, payload)
    stale = _snapshot(hub, "owner/model", stale_revision, payload)
    publish_shared_model_reference(
        hub,
        instance_id="app-one",
        repo_id="owner/model",
        revision=protected_revision,
    )
    mark_shared_model_snapshot_managed(
        hub, repo_id="owner/model", revision=stale_revision
    )

    result = collect_unreferenced_hf_snapshots(hub, dry_run=False)

    assert protected.is_dir()
    assert not stale.exists()
    assert result.scanned_snapshots == 2
    assert result.reclaimed_bytes == 0
    assert len(result.protected_snapshots) == 1
    assert len(result.collected_snapshots) == 1
    assert result.collected_blobs == ()
    assert (protected / "config.json").resolve().is_file()


def test_collector_removes_unreferenced_snapshot_and_orphan_blob(tmp_path: Path):
    hub = tmp_path / "hub"
    snapshot = _snapshot(hub, "owner/model", "d" * 40, b"orphan")
    blob = (snapshot / "config.json").resolve()
    mark_shared_model_snapshot_managed(
        hub, repo_id="owner/model", revision="d" * 40
    )

    preview = collect_unreferenced_hf_snapshots(hub)
    assert preview.dry_run
    assert snapshot.exists() and blob.exists()
    assert preview.reclaimed_bytes == len(b"orphan")

    applied = collect_unreferenced_hf_snapshots(hub, dry_run=False)
    assert not snapshot.exists()
    assert not blob.exists()
    assert not applied.dry_run


def test_invalid_reference_fails_closed_without_deleting_cache(tmp_path: Path):
    hub = tmp_path / "hub"
    snapshot = _snapshot(hub, "owner/model", "e" * 40, b"weights")
    publish_shared_model_reference(
        hub,
        instance_id="app-one",
        repo_id="owner/model",
        revision="e" * 40,
    )
    reference = next((hub / ".ai2apps-references" / "app-one").iterdir())
    reference.write_text("{}")
    reference.chmod(0o600)

    with pytest.raises(SharedModelCacheError):
        collect_unreferenced_hf_snapshots(hub, dry_run=False)

    assert snapshot.exists()


@pytest.mark.parametrize(
    ("instance_id", "repo_id", "revision"),
    [
        ("../other", "owner/model", "f" * 40),
        ("app-one", "../model", "f" * 40),
        ("app-one", "owner/model", "main"),
    ],
)
def test_reference_identity_rejects_traversal_and_mutable_revision(
    tmp_path: Path, instance_id: str, repo_id: str, revision: str
):
    with pytest.raises(SharedModelCacheError):
        publish_shared_model_reference(
            tmp_path / "hub",
            instance_id=instance_id,
            repo_id=repo_id,
            revision=revision,
        )


def test_collector_rejects_snapshot_symlink(tmp_path: Path):
    hub = tmp_path / "hub"
    outside = tmp_path / "outside"
    outside.mkdir()
    snapshots = hub / "models--owner--model" / "snapshots"
    snapshots.mkdir(parents=True)
    (snapshots / ("a" * 40)).symlink_to(outside, target_is_directory=True)

    with pytest.raises(SharedModelCacheError):
        collect_unreferenced_hf_snapshots(hub, dry_run=False)

    assert outside.is_dir()


def test_legacy_snapshot_without_managed_marker_is_never_collected(tmp_path: Path):
    hub = tmp_path / "hub"
    snapshot = _snapshot(hub, "owner/legacy", "5" * 40, b"legacy")

    report = collect_unreferenced_hf_snapshots(hub, dry_run=False)

    assert snapshot.is_dir()
    assert report.collected_snapshots == ()
    assert len(report.unmanaged_snapshots) == 1
