from __future__ import annotations

import json
from pathlib import Path

import pytest
from ai2apps_test.catalog import build_catalog_bundle
from ai2apps_test.catalog_service import CatalogService
from ai2apps_test.catalog_store import CatalogConflictError
from ai2apps_test.model import Component
from ai2apps_test.runner import (
    compile_pipeline,
    finalize_run,
    get_next,
    record_result,
    start_run,
)
from ai2apps_test.state import read_json


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    catalog = root / "tests" / "ats" / "catalog"
    catalog.mkdir(parents=True)
    (catalog / "base.json").write_text(
        json.dumps({"schemaVersion": "ai2apps.test-catalog.v1", "cases": []}),
        encoding="utf-8",
    )
    (root / "ai2apps" / "apps").mkdir(parents=True)
    (root / "ai2apps" / "apps" / "system.py").write_text(
        "_SYSTEM_APP_MANIFESTS_BASE = []\n", encoding="utf-8"
    )
    return root


def test_generated_case_shared_content(tmp_path, monkeypatch):
    root = _repo(tmp_path)
    components = [Component("ai2apps.agents", "app", "Agents", "Main Apps")]
    monkeypatch.setattr("ai2apps_test.catalog_service.discover_inventory", lambda _: components)
    service = CatalogService(root)
    case_id = "component.app.ai2apps.agents.launch-smoke"
    initial = service.shared_case(case_id)
    payload = {"revision": initial.get("revision", ""), "content": {"name": "Shared Agents", "instructions": ["Open Agents"]}}
    updated = service.save_shared_case(case_id, payload)
    assert updated["name"] == "Shared Agents"
    assert updated["groupId"] == initial["groupId"]
    cases = build_catalog_bundle(root, components)[1]
    assert next(case for case in cases if case.id == case_id).instructions == ("Open Agents",)
    with pytest.raises(CatalogConflictError):
        service.save_shared_case(case_id, payload)
    with pytest.raises(KeyError):
        service.shared_case("missing-case")
    path = root / "tests/ats/catalog/case-content" / f"{case_id}.yaml"
    path.write_text(f"id: {case_id}\ncontent:\n  group_id: wrong\n")
    with pytest.raises(ValueError, match="structural fields"):
        build_catalog_bundle(root, components)


def test_case_timing_uses_harness_start():
    from ai2apps_test.runner import _record_timing
    result = {"completedAt": "2026-09-09T01:00:12+00:00"}
    _record_timing({"caseStartedAt": {"sample": "2026-09-09T01:00:00+00:00"}}, "sample", result)
    assert result["durationSeconds"] == 12
    assert result["startedAt"] == "2026-09-09T01:00:00+00:00"


def _group() -> dict:
    return {
        "schemaVersion": 1,
        "id": "pipeline-cases",
        "name": "Pipeline Cases",
        "kind": "on-demand",
        "enabled": True,
        "defaultSelected": False,
        "lifecycle": "enabled",
    }


def _case() -> dict:
    return {
        "schemaVersion": 1,
        "id": "pipeline.expected-failure",
        "name": "Expected Failure",
        "groupId": "pipeline-cases",
        "priority": None,
        "enabled": True,
        "required": False,
        "executor": "codex-ui",
        "timeoutSeconds": 60,
        "requires": [],
        "tags": [],
        "instructions": ["Exercise the visible failure path."],
        "expectations": ["Record the real observed outcome."],
        "cleanup": [],
        "lifecycle": "enabled",
    }


def _pipeline() -> dict:
    return {
        "schemaVersion": 1,
        "id": "failure-recovery",
        "name": "Failure Recovery",
        "description": "Restart around an expected failure.",
        "enabled": True,
        "steps": [
            {"id": "restart-before", "type": "action", "action": "restart-local"},
            {
                "id": "expected-failure",
                "type": "case",
                "caseId": "pipeline.expected-failure",
                "expectedStatus": "failed",
            },
            {"id": "restart-after", "type": "action", "action": "restart-app"},
            {
                "id": "verify-after",
                "type": "case",
                "caseId": "pipeline.expected-failure",
                "expectedStatus": "passed",
            },
        ],
    }


def test_latest_pipeline_result_survives_reopening(tmp_path):
    root = _repo(tmp_path)
    service = CatalogService(root)
    assert service.latest_pipeline_run("failure-recovery") == {"run": None}
    directory = root / "ai2apps-test-system" / "artifacts" / "runs" / "saved-run"
    directory.mkdir(parents=True)
    state = {
        "runId": "saved-run", "createdAt": "2026-09-09T07:00:00Z", "status": "completed",
        "plan": {"pipeline": {"id": "failure-recovery", "revision": "original"}, "cases": [
            {"id": "pipeline.step-1", "pipelineStepId": "step-1", "sourceCaseId": "source-case", "expectedStatus": "passed"},
            {"id": "pipeline.step-2", "pipelineStepId": "step-2", "action": "restart-local"},
        ]},
        "results": {"pipeline.step-1": {"status": "blocked", "summary": "missing fixture"},
                    "pipeline.step-2": {"status": "passed"}},
    }
    (directory / "state.json").write_text(json.dumps(state))
    run = CatalogService(root).latest_pipeline_run("failure-recovery")["run"]
    assert run["conclusion"] == "BLOCKED"
    assert run["revision"] == "original"
    assert run["steps"]["step-1"]["summary"] == "missing fixture"
    assert run["steps"]["step-2"]["status"] == "passed"
    assert service.latest_pipeline_run("other") == {"run": None}


def test_pipeline_store_validates_references_and_compiles_unique_steps(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    service = CatalogService(root)
    service.save("groups", _group())
    service.save("cases", _case())
    service.save("pipelines", _pipeline())

    plan = compile_pipeline(root, "failure-recovery")

    assert plan["pipeline"]["id"] == "failure-recovery"
    assert [case["executor"] for case in plan["cases"]] == [
        "pipeline-action",
        "codex-ui",
        "pipeline-action",
        "codex-ui",
    ]
    assert len({case["id"] for case in plan["cases"]}) == 4
    assert plan["cases"][1]["sourceCaseId"] == "pipeline.expected-failure"
    assert plan["cases"][1]["expectedStatus"] == "failed"


def test_pipeline_case_content_is_shared_and_structural_fields_are_locked(tmp_path):
    root = _repo(tmp_path)
    service = CatalogService(root)
    service.save("groups", _group())
    service.save("cases", _case())
    pipeline = _pipeline()
    content = {"name": "Customized name", "description": "Detailed goal", "instructions": ["Open Chat"], "expectations": ["Chat ready"], "cleanup": ["Close Chat"]}
    service.save("pipelines", pipeline)
    original = compile_pipeline(root, pipeline["id"])
    service.save("pipelines", {**pipeline, "id": "another-pipeline"})
    revision = service.shared_case(_case()["id"])["revision"]
    service.save_shared_case(_case()["id"], {"revision": revision, "content": content})
    plan = compile_pipeline(root, pipeline["id"])
    assert plan["cases"][1]["instructions"] == ["Open Chat"]
    assert plan["cases"][1]["name"] == "2. Customized name"
    assert plan["cases"][3]["instructions"] == ["Open Chat"]
    assert compile_pipeline(root, "another-pipeline")["cases"][1]["instructions"] == ["Open Chat"]
    assert original["cases"][1]["instructions"] == _case()["instructions"]
    assert service.get("cases", _case()["id"])["name"] == "Customized name"
    revision = service.shared_case(_case()["id"])["revision"]
    for field in ("id", "groupId", "executor", "command", "requires", "enabled"):
        with pytest.raises(ValueError, match="structural fields"):
            service.save_shared_case(_case()["id"], {"revision": revision, "content": {**content, field: "changed"}})


def test_pipeline_waits_at_ui_barrier_and_normalizes_expected_failure(
    tmp_path: Path, monkeypatch
) -> None:
    root = _repo(tmp_path)
    service = CatalogService(root)
    service.save("groups", _group())
    service.save("cases", _case())
    service.save("pipelines", _pipeline())
    plan = compile_pipeline(root, "failure-recovery")
    actions: list[str] = []
    monkeypatch.setattr(
        "ai2apps_test.runner.execute_pipeline_action",
        lambda _root, action, _state: actions.append(action)
        or {"status": "passed", "summary": action},
    )

    run_id, run_dir, state = start_run(root, plan)

    assert actions == ["restart-local"]
    assert state["pipelineCursor"] == 1
    ui_step = plan["cases"][1]
    with pytest.raises(ValueError, match="current ordered step"):
        record_result(
            root,
            run_id,
            plan["cases"][3]["id"],
            {"status": "blocked", "summary": "out of order", "evidence": []},
        )
    evidence = run_dir / "screenshots" / "expected-failure.txt"
    evidence.parent.mkdir(parents=True)
    evidence.write_text("visible failure", encoding="utf-8")
    result = record_result(
        root,
        run_id,
        ui_step["id"],
        {
            "status": "failed",
            "summary": "failure was visible",
            "evidence": [str(evidence)],
        },
    )

    assert result["status"] == "passed"
    assert result["observedStatus"] == "failed"
    assert result["expectedStatus"] == "failed"
    assert actions == ["restart-local", "restart-app"]


@pytest.mark.parametrize("executor", ["codex-ui", "builtin"])
@pytest.mark.parametrize("policy,observed,stops", [
    ("stop-when-failed", "failed", True),
    ("stop-when-failed", "passed", False),
    ("stop-when-succeed", "passed", True),
    ("stop-when-succeed", "failed", False),
    ("stop-when-succeed", "blocked", False),
])
def test_pipeline_conditional_stop(tmp_path, monkeypatch, executor, policy, observed, stops):
    root = _repo(tmp_path)
    service = CatalogService(root)
    service.save("groups", _group())
    service.save("cases", {**_case(), "executor": executor})
    pipeline = _pipeline()
    pipeline["steps"] = pipeline["steps"][1:3]
    pipeline["steps"][0]["expectedStatus"] = policy
    service.save("pipelines", pipeline)
    actions = []
    monkeypatch.setattr("ai2apps_test.runner.execute_pipeline_action",
                        lambda _root, action, _state: actions.append(action) or
                        {"status": "passed", "summary": action})
    monkeypatch.setattr("ai2apps_test.runner.execute_builtin",
                        lambda *args: {"status": observed, "summary": "actual outcome"})
    plan = compile_pipeline(root, pipeline["id"])
    run_id, run_dir, _ = start_run(root, plan)
    if executor == "codex-ui":
        evidence = run_dir / "evidence.txt"
        evidence.write_text("observed outcome")
        record_result(root, run_id, plan["cases"][0]["id"], {
            "status": observed, "summary": "actual outcome", "evidence": [str(evidence)],
        })
    state = read_json(run_dir / "state.json")
    assert bool(state.get("pipelineStop")) == stops
    assert actions == ([] if stops else ["restart-app"])
    assert get_next(root, run_id)["status"] == "done"
    assert state["results"][plan["cases"][0]["id"]]["observedStatus"] == observed
    if stops:
        assert state["results"][plan["cases"][1]["id"]]["skipReason"] == "pipeline-stop"
    report = finalize_run(root, run_id)
    assert report["conclusion"] == {"passed": "PASS", "failed": "FAIL", "blocked": "BLOCKED"}[observed]
