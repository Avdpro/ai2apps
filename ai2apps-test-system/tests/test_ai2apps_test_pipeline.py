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
    resume_human_pipeline,
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


def test_pipeline_save_as_preserves_source_and_rejects_existing_id(tmp_path):
    import copy
    root = _repo(tmp_path)
    service = CatalogService(root)
    service.save('groups', _group())
    service.save('cases', _case())
    original = _pipeline()
    service.save('pipelines', original)
    duplicate = copy.deepcopy(original)
    duplicate.update(id='pipeline-copy', name='副本')
    duplicate['steps'][1]['executionMode'] = 'manual'
    service.save('pipelines', duplicate)
    from ai2apps_test.catalog_store import CatalogStore
    store = CatalogStore(root)
    assert 'executionMode' not in store.get('pipelines', original['id'])['steps'][1]
    assert store.get('pipelines', duplicate['id'])['steps'][1]['executionMode'] == 'manual'
    with pytest.raises(CatalogConflictError):
        service.save('pipelines', duplicate)


def test_controller_owns_manual_timeout_after_record_returns(tmp_path, monkeypatch):
    import threading
    from ai2apps_test.runner import resume_human_pipeline
    from ai2apps_test.selector import _status_payload
    root = _repo(tmp_path)
    service = CatalogService(root)
    service.save('groups', _group())
    service.save('cases', _case())
    pipeline = _pipeline()
    automatic = pipeline['steps'][1]
    automatic['expectedStatus'] = 'passed'
    pipeline['steps'] = [automatic, {'id':'human', 'type':'action', 'action':'human-test',
        'humanInstructions':'Test manually', 'confirmTimeoutSeconds':1}]
    service.save('pipelines', pipeline)
    plan = compile_pipeline(root, pipeline['id'])
    run_id, directory, _ = start_run(root, plan)
    evidence = directory / 'proof.txt'
    evidence.write_text('test evidence')
    monkeypatch.setattr('ai2apps_test.human_action.subprocess.Popen', lambda *args, **kwargs: None)
    record_result(root, run_id, plan['cases'][0]['id'], {'status':'passed', 'summary':'done', 'evidence':['proof.txt']})
    assert read_json(directory / 'state.json')['status'] == 'waiting_human'
    assert not (directory / 'human-action.json').exists()  # record did not start a waiting subprocess
    assert get_next(root, run_id)['status'] == 'waiting_human'
    payload = _status_payload({'runDirectory':str(directory)}, threading.Lock())
    assert [c['id'] for g in payload['groups'] for c in g['cases']] == [c['id'] for c in plan['cases']]
    state = resume_human_pipeline(root, directory, lambda:False)
    assert state['status'] == 'ready_to_finalize'
    assert state['results']['pipeline.human']['status'] == 'skipped'
    assert '超时' in state['results']['pipeline.human']['summary']
    assert get_next(root, run_id)['status'] == 'done'


@pytest.mark.parametrize('mode', ['run', 'skip', 'manual'])
def test_case_execution_modes(tmp_path, mode, monkeypatch):
    root = _repo(tmp_path)
    service = CatalogService(root)
    service.save('groups', _group())
    service.save('cases', _case())
    pipeline = _pipeline()
    step = pipeline['steps'][1]
    step['executionMode'] = mode
    pipeline['steps'] = [step]
    service.save('pipelines', pipeline)
    plan = compile_pipeline(root, pipeline['id'])
    case = plan['cases'][0]
    assert case['sourceCaseId'] == _case()['id']
    assert case['stepEnabled'] == (mode != 'skip')
    assert case['executionMode'] == mode
    if mode == 'manual':
        assert case['action'] == 'human-test'
        assert case['confirmTimeoutSeconds'] == 120
        assert _case()['instructions'][0] in case['humanInstructions']
        assert _case()['expectations'][0] in case['humanInstructions']
        calls = []
        monkeypatch.setattr('ai2apps_test.human_action.execute', lambda directory, item, cancelled: calls.append(item['id']) or {'status':'failed', 'summary':'用户报告失败'})
        _, _, state = start_run(root, plan)
        assert calls == [case['id']]
        assert state['results'][case['id']]['observedStatus'] == 'failed'
        assert state['results'][case['id']]['status'] == 'passed'  # existing expected-failed policy
    else:
        assert case['executor'] == 'codex-ui'


@pytest.mark.parametrize("mode", ["none", "auto", "selected"])
def test_explicit_start_login_modes(tmp_path, monkeypatch, mode):
    root = _repo(tmp_path)
    service = CatalogService(root)
    service.save("groups", _group())
    service.save("cases", _case())
    pipeline = _pipeline()
    start = {"id": "boot", "type": "action", "action": "start-helper", "loginMode": mode}
    if mode == "selected":
        start["accountEmail"] = "test3@ai2apps.com"
    pipeline["steps"] = [start, pipeline["steps"][1]]
    service.save("pipelines", pipeline)
    actions, logins = [], []
    monkeypatch.setattr("ai2apps_test.runner.execute_pipeline_action", lambda root, action, state: actions.append(action) or {"status": "passed"})
    def acquire(*args, **kwargs):
        assert not actions, 'must prepare login before starting the instance'
        logins.append(kwargs)
        return True
    monkeypatch.setattr("ai2apps_test.runner.acquire_for_run", acquire)
    plan = compile_pipeline(root, pipeline["id"])
    start_run(root, plan)
    assert actions == ["start-helper"]
    assert len(logins) == (0 if mode == "none" else 1)
    if logins:
        assert logins[0]["only_case_id"] == "pipeline.boot"
        assert logins[0]["account_email"] == start.get("accountEmail")
    pipeline["steps"] = pipeline["steps"][1:]
    pipeline["id"] = "without-start"
    service.save("pipelines", pipeline)
    actions.clear()
    logins.clear()
    monkeypatch.setattr("ai2apps_test.state.runs_root", lambda _: root / "second-runs")
    start_run(root, compile_pipeline(root, pipeline["id"]))
    assert actions == [] and logins == []


def test_login_failure_only_blocks_start_action(tmp_path, monkeypatch):
    root = _repo(tmp_path)
    service = CatalogService(root)
    service.save("groups", _group())
    service.save("cases", _case())
    pipeline = _pipeline()
    pipeline["steps"] = [{"id": "boot", "type": "action", "action": "start-helper", "loginMode": "auto"}, pipeline["steps"][1]]
    service.save("pipelines", pipeline)
    monkeypatch.setattr("ai2apps_test.runner.execute_pipeline_action", lambda *args: pytest.fail('must not launch after login preparation fails'))
    def fail(root, directory, state, **kwargs):
        state["results"][kwargs["only_case_id"]] = {"status": "blocked", "summary": "accessibility-permission"}
        return False
    monkeypatch.setattr("ai2apps_test.runner.acquire_for_run", fail)
    _, _, state = start_run(root, compile_pipeline(root, pipeline["id"]))
    assert state["results"]["pipeline.boot"]["status"] == "blocked"
    assert len(state["results"]) == 2
    dependent = next(value for key, value in state["results"].items() if key != "pipeline.boot")
    assert dependent["details"]["executed"] is False
    assert dependent["status"] == "blocked"
    assert state["status"] != "awaiting_agent"


def test_disabled_steps_do_not_execute(tmp_path, monkeypatch):
    root = _repo(tmp_path)
    service = CatalogService(root)
    service.save("groups", _group())
    service.save("cases", _case())
    pipeline = _pipeline()
    for step in pipeline["steps"]:
        step["enabled"] = False
    service.save("pipelines", pipeline)
    def unexpected(*args, **kwargs):
        pytest.fail("disabled step executed")
    monkeypatch.setattr("ai2apps_test.runner.execute_pipeline_action", unexpected)
    monkeypatch.setattr("ai2apps_test.runner.acquire_for_run", unexpected)
    run_id, _, state = start_run(root, compile_pipeline(root, pipeline["id"]))
    assert len(state["results"]) == len(pipeline["steps"])
    assert all(result["skipReason"] == "step-disabled" for result in state["results"].values())
    assert get_next(root, run_id)["status"] == "done"
    assert finalize_run(root, run_id)["conclusion"] != "BLOCKED"


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


def test_include_pipeline_expansion_and_validation(tmp_path):
    root = _repo(tmp_path)
    service = CatalogService(root)
    service.save('groups', _group())
    service.save('cases', _case())
    child = {**_pipeline(), 'id': 'child', 'steps': [_pipeline()['steps'][1]]}
    service.save('pipelines', child)
    parent = {**_pipeline(), 'id': 'parent', 'steps': [
        {'id': 'first', 'type': 'action', 'action': 'include-pipeline', 'pipelineId': 'child'},
        {'id': 'second', 'type': 'action', 'action': 'include-pipeline', 'pipelineId': 'child', 'enabled': False},
        _pipeline()['steps'][3],
    ]}
    service.save('pipelines', parent)
    plan = compile_pipeline(root, 'parent')
    assert [c['sourcePipelineId'] for c in plan['cases']] == ['child', 'child', 'parent']
    assert [c['stepEnabled'] for c in plan['cases']] == [True, False, True]
    assert len({c['id'] for c in plan['cases']}) == 3
    assert plan['cases'][0]['pipelineStepPath'] == ['first', 'expected-failure']
    assert set(plan['pipelineSources']) == {'parent', 'child'}
    run_id, directory, _ = start_run(root, plan)
    assert get_next(root, run_id)['case']['id'] == plan['cases'][0]['id']
    record_result(root, run_id, plan['cases'][0]['id'], {'status': 'blocked', 'summary': 'test blocker'})
    assert get_next(root, run_id)['case']['id'] == plan['cases'][2]['id']
    assert read_json(directory / 'state.json')['results'][plan['cases'][1]['id']]['status'] == 'skipped'
    cyclic = {**child, 'steps': [{'id': 'loop', 'type': 'action', 'action': 'include-pipeline', 'pipelineId': 'parent'}]}
    with pytest.raises(ValueError, match='cycle'):
        service.save('pipelines', cyclic)
    assert not service.validate('pipelines', cyclic)['ok']
    missing = {**parent, 'id': 'missing-parent', 'steps': [
        {'id': 'missing', 'type': 'action', 'action': 'include-pipeline', 'pipelineId': 'absent'}]}
    with pytest.raises(ValueError, match='not found'):
        service.save('pipelines', missing)
    service.save('pipelines', {**child, 'id': 'disabled-child', 'enabled': False})
    missing['steps'][0]['pipelineId'] = 'disabled-child'
    with pytest.raises(ValueError, match='disabled'):
        service.save('pipelines', missing)


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


@pytest.mark.parametrize('restart_status', ['passed', 'blocked'])
def test_pipeline_waits_at_ui_barrier_and_normalizes_expected_failure(
    tmp_path: Path, monkeypatch, restart_status
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
        or {"status": restart_status, "summary": action},
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
    assert actions == ["restart-local"]
    assert get_next(root, run_id)['status'] == 'waiting_controller'
    with pytest.raises(ValueError, match='pending controller'):
        finalize_run(root, run_id)
    resume_human_pipeline(root, run_dir, lambda: False)
    assert actions == ["restart-local", "restart-app"]
    assert read_json(run_dir / 'state.json')['results']['pipeline.restart-after']['status'] == restart_status
    assert get_next(root, run_id)['case']['id'] == plan['cases'][3]['id']
    resume_human_pipeline(root, run_dir, lambda: False)
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
    state = resume_human_pipeline(root, run_dir, lambda: False)
    assert bool(state.get("pipelineStop")) == stops
    assert actions == ([] if stops else ["restart-app"])
    assert get_next(root, run_id)["status"] == "done"
    assert state["results"][plan["cases"][0]["id"]]["observedStatus"] == observed
    if stops:
        assert state["results"][plan["cases"][1]["id"]]["skipReason"] == "pipeline-stop"
    report = finalize_run(root, run_id)
    assert report["conclusion"] == {"passed": "PASS", "failed": "FAIL", "blocked": "BLOCKED"}[observed]
