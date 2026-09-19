from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from ai2apps_test.catalog import (
    CASE_TEMPLATES,
    build_catalog_bundle,
    migrate_base_catalog,
    select_cases,
)
from ai2apps_test.catalog_service import CatalogService
from ai2apps_test.catalog_store import CatalogConflictError, CatalogStore
from ai2apps_test.catalog_validation import CatalogValidationError
from ai2apps_test.inventory import discover_inventory


def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    catalog = root / "tests" / "ats" / "catalog"
    catalog.mkdir(parents=True)
    (catalog / "base.json").write_text(
        json.dumps(
            {
                "schemaVersion": "ai2apps.test-catalog.v1",
                "cases": [
                    {
                        "id": "base.smoke",
                        "name": "Smoke",
                        "priority": "P0",
                        "group": "Base",
                        "executor": "builtin",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / "ai2apps" / "apps").mkdir(parents=True)
    (root / "ai2apps" / "apps" / "system.py").write_text(
        "_SYSTEM_APP_MANIFESTS_BASE = []\n", encoding="utf-8"
    )
    return root


def group_value(group_id: str = "corner-cases") -> dict:
    return {
        "schemaVersion": 1,
        "id": group_id,
        "name": "Corner Cases",
        "kind": "on-demand",
        "enabled": True,
        "defaultSelected": False,
        "lifecycle": "enabled",
        "order": 500,
        "tags": [],
    }


def case_value(case_id: str = "corner.drag") -> dict:
    return {
        "schemaVersion": 1,
        "id": case_id,
        "name": "Drag",
        "groupId": "corner-cases",
        "priority": None,
        "enabled": True,
        "required": False,
        "executor": "codex-ui",
        "timeoutSeconds": 60,
        "requires": [],
        "tags": [],
        "instructions": ["Perform the drag with Computer Use."],
        "expectations": ["The target accepts it."],
        "cleanup": [],
        "lifecycle": "enabled",
    }


def test_on_demand_case_never_enters_priority_and_can_be_included(
    tmp_path: Path,
) -> None:
    root = repo(tmp_path)
    store = CatalogStore(root)
    store.save("groups", group_value())
    store.save("cases", case_value())
    _, cases = build_catalog_bundle(root, [])
    assert [case.id for case in select_cases(cases, "P3")] == ["base.smoke"]
    assert {
        case.id for case in select_cases(cases, "P0", include_groups={"corner-cases"})
    } == {"base.smoke", "corner.drag"}


def test_store_requires_revision_and_supports_archive_restore(tmp_path: Path) -> None:
    store = CatalogStore(repo(tmp_path))
    created = store.save("groups", group_value())
    with pytest.raises(CatalogConflictError):
        store.save("groups", {**group_value(), "name": "Changed"})
    updated = store.save(
        "groups", {**group_value(), "name": "Changed"}, created["revision"]
    )
    archived = store.archive("groups", "corner-cases", updated["revision"])
    assert archived["id"] == "corner-cases"
    restored = store.restore("groups", "corner-cases", archived["revision"])
    assert restored["name"] == "Changed"


def test_store_rejects_paths_commands_and_secrets(tmp_path: Path) -> None:
    store = CatalogStore(repo(tmp_path))
    with pytest.raises(ValueError):
        store.save("groups", group_value("../escape"))
    store.save("groups", group_value())
    with pytest.raises(CatalogValidationError):
        store.save(
            "cases",
            {**case_value(), "executor": "command", "command": ["sh", "-c", "id"]},
        )
    with pytest.raises(CatalogValidationError):
        store.save("cases", {**case_value(), "password": "not-allowed"})


def test_duplicate_case_ids_fail_closed(tmp_path: Path) -> None:
    root = repo(tmp_path)
    store = CatalogStore(root)
    store.save("groups", group_value())
    store.save("cases", case_value("base.smoke"))
    with pytest.raises(CatalogValidationError, match="duplicate case ID"):
        build_catalog_bundle(root, [])


def test_service_rejects_duplicate_before_it_reaches_disk(tmp_path: Path) -> None:
    root = repo(tmp_path)
    service = CatalogService(root)
    service.save("groups", group_value())
    with pytest.raises(ValueError, match="ID already exists"):
        service.save("cases", case_value("base.smoke"))
    assert service.store.list_objects("cases") == []


def test_diff_preview_does_not_write(tmp_path: Path) -> None:
    store = CatalogStore(repo(tmp_path))
    diff = store.preview("groups", group_value())
    assert "+id: corner-cases" in diff
    assert store.list_objects("groups") == []


def test_group_archive_and_restore_preserve_child_cases(tmp_path: Path) -> None:
    root = repo(tmp_path)
    service = CatalogService(root)
    group = service.save("groups", group_value())
    service.save("cases", case_value())
    archived = service.archive("groups", "corner-cases", group["revision"])
    assert service.store.list_objects("cases") == []
    service.restore("groups", "corner-cases", archived["revision"])
    assert service.store.get("cases", "corner.drag")["groupId"] == "corner-cases"


def test_generated_case_copy_becomes_safe_on_demand_draft(tmp_path: Path) -> None:
    root = repo(tmp_path)
    service = CatalogService(root)
    service.save("groups", group_value())
    copied = service.copy_case("base.smoke", "copied.smoke", "corner-cases")
    assert copied["priority"] is None
    assert copied["executor"] == "builtin"
    assert copied["lifecycle"] == "draft"
    assert copied["enabled"] is False


def test_management_snapshot_includes_draft_without_making_it_runnable(
    tmp_path: Path,
) -> None:
    root = repo(tmp_path)
    service = CatalogService(root)
    service.save("groups", group_value())
    service.save(
        "cases",
        {
            **case_value(),
            "enabled": False,
            "lifecycle": "draft",
        },
    )

    snapshot = service.snapshot()
    draft = next(case for case in snapshot["cases"] if case["id"] == "corner.drag")

    assert draft["lifecycle"] == "draft"
    assert draft["enabled"] is False
    assert draft["editable"] is True
    assert draft["runnable"] is False
    _, runnable = build_catalog_bundle(root, [])
    assert [case.id for case in runnable] == ["base.smoke"]


def test_current_priority_manifests_match_legacy_id_rules() -> None:
    root = Path(__file__).resolve().parents[2]
    _, cases = build_catalog_bundle(root, discover_inventory(root))
    base = json.loads(
        (root / "tests" / "ats" / "catalog" / "base.json").read_text(encoding="utf-8")
    )["cases"]
    generated: list[tuple[str, str]] = []
    for component in discover_inventory(root):
        templates = CASE_TEMPLATES.get(component.kind)
        if templates is None and component.kind.startswith("package-"):
            templates = (
                ("contract", "", "P0", ""),
                ("lifecycle", "", "P1", ""),
                ("upgrade-rollback", "", "P2", ""),
                ("clean-release", "", "P3", ""),
            )
        for suffix, _name, priority, _executor in templates or ():
            generated.append(
                (f"component.{component.kind}.{component.id}.{suffix}", priority)
            )
    rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    for priority in rank:
        expected = {
            item["id"] for item in base if rank[item["priority"]] <= rank[priority]
        }
        expected.update(
            case_id
            for case_id, case_priority in generated
            if rank[case_priority] <= rank[priority]
        )
        assert {case.id for case in select_cases(cases, priority)} == expected


def test_editing_trialled_execution_contract_requires_retrial(tmp_path: Path) -> None:
    store = CatalogStore(repo(tmp_path))
    store.save("groups", group_value())
    created = store.save("cases", case_value())
    updated = store.save(
        "cases",
        {**case_value(), "instructions": ["Changed action"]},
        created["revision"],
    )
    assert updated["enabled"] is False
    assert updated["lifecycle"] == "valid"


def test_managed_image_fixture_is_content_addressed_and_case_scoped(
    tmp_path: Path,
) -> None:
    store = CatalogStore(repo(tmp_path))
    store.save("groups", group_value())
    created = store.save("cases", case_value())
    content = b"\x89PNG\r\n\x1a\nfixture"

    fixture = store.store_image_fixture(
        "corner.drag", "Sample Image.png", base64.b64encode(content).decode()
    )

    assert fixture["path"].startswith("tests/ats/fixtures/corner.drag/")
    assert fixture["path"].endswith("-sample-image.png")
    assert (store.repo_root / fixture["path"]).read_bytes() == content
    updated = store.save(
        "cases",
        {**case_value(), "fixtures": [fixture["path"]]},
        created["revision"],
    )
    assert updated["fixtures"] == [fixture["path"]]
    with pytest.raises(ValueError, match="PNG, JPEG"):
        store.store_image_fixture(
            "corner.drag", "script.sh", base64.b64encode(b"echo unsafe").decode()
        )


def test_trial_review_proposal_preserves_identity_and_requires_user_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repo(tmp_path)
    service = CatalogService(root)
    service.save("groups", group_value())
    service.save("cases", case_value())
    monkeypatch.setattr(
        "ai2apps_test.catalog_service.trial_context",
        lambda *_: {"result": {"status": "blocked"}},
    )
    proposal = {
        "name": "Improved Drag",
        "priority": None,
        "required": False,
        "timeoutSeconds": 120,
        "requires": [],
        "tags": [],
        "componentId": None,
        "description": "Use a user-provided image.",
        "instructions": ["Upload the managed image with Computer Use."],
        "expectations": ["The target accepts the same image."],
        "cleanup": [],
        "fixtures": [],
    }
    monkeypatch.setattr(
        "ai2apps_test.catalog_service.generate_trial_review",
        lambda *_: {
            "summary": "Image required",
            "resultAssessment": "blocked",
            "automaticChanges": [],
            "userRequests": [
                {
                    "id": "sample-image",
                    "kind": "image",
                    "title": "Image",
                    "description": "Provide one image",
                    "why": "Required input",
                    "acceptanceCriteria": ["No private data"],
                    "required": True,
                }
            ],
            "nonCaseIssues": [],
            "proposal": proposal,
        },
    )

    review = service.review_trial("corner.drag", tmp_path / "run", [])

    assert review["proposal"]["id"] == "corner.drag"
    assert review["proposal"]["groupId"] == "corner-cases"
    assert review["proposal"]["enabled"] is False
    assert review["proposal"]["lifecycle"] == "draft"
    assert review["readyToApply"] is False
    assert review["hasChanges"] is True
    assert "+name: Improved Drag" in review["diff"]


def test_catalog_schema_documents_are_valid_json() -> None:
    root = Path(__file__).resolve().parents[2] / "tests" / "ats" / "catalog" / "schemas"
    for name in ("group.schema.json", "case.schema.json", "pipeline.schema.json"):
        assert json.loads((root / name).read_text(encoding="utf-8"))["type"] == "object"


def test_base_catalog_migration_preserves_ids_and_becomes_read_only_yaml(
    tmp_path: Path,
) -> None:
    root = repo(tmp_path)
    assert migrate_base_catalog(root)["status"] == "ready"
    assert migrate_base_catalog(root, apply=True)["status"] == "migrated"
    groups, cases = build_catalog_bundle(root, [])
    assert [case.id for case in cases] == ["base.smoke"]
    assert cases[0].source_type == "built-in"
    assert cases[0].editable is False
    assert groups[0].source_type == "built-in"
    assert (
        json.loads((root / "tests" / "ats" / "catalog" / "base.json").read_text())[
            "migrated"
        ]
        is True
    )
