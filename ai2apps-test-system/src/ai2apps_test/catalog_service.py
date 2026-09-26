from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml

from .case_generator import generate_case_draft
from .catalog import build_catalog_bundle, catalog_diagnostics
from .catalog_store import CatalogConflictError, CatalogStore
from .catalog_validation import (
    CASE_CONTENT_FIELDS,
    require_valid,
    validate_case,
    validate_group,
    validate_pipeline,
)
from .inventory import discover_inventory
from .report import conclusion
from .state import read_json, runs_root
from .trial_review import generate_trial_review, trial_context


class CatalogService:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.store = CatalogStore(repo_root)

    def snapshot(self) -> dict[str, Any]:
        components = discover_inventory(self.repo_root)
        groups, runnable_cases = build_catalog_bundle(self.repo_root, components)
        management_cases = {
            case.id: {**case.to_dict(), "runnable": True} for case in runnable_cases
        }
        group_names = {group.id: group.name for group in groups}
        for stored in self.store.list_objects("cases"):
            case_id = str(stored.get("id", ""))
            source_type = str(stored.get("sourceType", "user-authored"))
            existing = management_cases.get(case_id, {})
            management_cases[case_id] = {
                **existing,
                **stored,
                "group": group_names.get(
                    str(stored.get("groupId", "")),
                    str(stored.get("groupId", "")),
                ),
                "sourceType": source_type,
                "editable": source_type == "user-authored",
                "runnable": case_id in management_cases,
            }
            if existing:
                management_cases[case_id].update({key: existing[key] for key in CASE_CONTENT_FIELDS | {"revision"} if key in existing})
        cases = sorted(
            management_cases.values(),
            key=lambda case: (
                str(case.get("group", "")),
                str(case.get("lifecycle", "")),
                str(case.get("id", "")),
            ),
        )
        return {
            "groups": [group.to_dict() for group in groups],
            "cases": cases,
            "pipelines": self.store.list_objects("pipelines"),
            "archived": {
                "groups": self.store.list_objects("groups", True),
                "cases": self.store.list_objects("cases", True),
            },
            "diagnostics": catalog_diagnostics(
                components,
                runnable_cases,
                {
                    "groups": len(self.store.list_objects("groups", True)),
                    "cases": len(self.store.list_objects("cases", True)),
                },
                self.repo_root,
            ),
        }

    def get(self, kind: str, object_id: str, archived: bool = False) -> dict[str, Any]:
        return self.store.get(kind, object_id, archived)

    def shared_case(self, case_id: str) -> dict[str, Any]:
        case = next((item for item in self.snapshot()["cases"] if item["id"] == case_id), None)
        if case is None:
            raise KeyError(case_id)
        return case

    def save_shared_case(self, case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        current = self.shared_case(case_id)
        if set(payload) - {"revision", "content"}:
            raise ValueError("structural fields cannot be changed")
        if payload.get("revision") != current.get("revision", ""):
            raise CatalogConflictError("Case changed; reopen the editor")
        content = payload.get("content")
        probe = {"id": "validation", "name": "validation", "steps": [{"id": "step", "type": "case", "caseId": case_id, "caseContent": content}]}
        require_valid(validate_pipeline(probe, allow_case_content=True))
        if current.get("sourceType") == "user-authored":
            path = self.store._path("cases", case_id)
            stored = self.store.get("cases", case_id)
            value = {key: value for key, value in stored.items() if key not in {"revision", "sourcePath"}}
            value.update(content)
        else:
            path = self.store._path("case-content", case_id)
            value = {"id": case_id, "content": content}
        data = yaml.safe_dump(value, allow_unicode=True, sort_keys=False)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(data, encoding="utf-8")
        os.replace(temporary, path)
        return self.shared_case(case_id)

    def latest_pipeline_run(self, pipeline_id: str) -> dict[str, Any]:
        latest = None
        for path in runs_root(self.repo_root).glob("*/state.json"):
            try:
                state = read_json(path)
            except (OSError, json.JSONDecodeError):
                continue
            plan = state.get("plan", {})
            if plan.get("pipeline", {}).get("id") != pipeline_id:
                continue
            if state.get("status") not in {"completed", "cancelled"}:
                continue
            if latest is None or state.get("createdAt", "") > latest.get("createdAt", ""):
                latest = state
        if latest is None:
            return {"run": None}
        steps = {}
        for index, case in enumerate(latest["plan"]["cases"]):
            steps[case.get("pipelineStepId", case["id"])] = {
                "index": index, "sourceCaseId": case.get("sourceCaseId"),
                "action": case.get("action"), "expectedStatus": case.get("expectedStatus", "passed"),
                "caseRevision": case.get("revision"),
                "executionMode": case.get("executionMode", 'run' if case.get('stepEnabled', True) else 'skip'),
                "caseContent": case.get("caseContent", {}),
                "loginMode": case.get("loginMode", "none"), "accountEmail": case.get("accountEmail"),
                **latest.get("results", {}).get(case["id"], {"status": "pending"}),
            }
        root_snapshot = latest['plan'].get('pipelineSources', {}).get(pipeline_id, {})
        for index, step in enumerate(root_snapshot.get('steps', [])):
            if step.get('action') != 'include-pipeline':
                if step['id'] in steps:
                    steps[step['id']]['index'] = index
                continue
            children = [case for case in latest['plan']['cases']
                        if case.get('pipelineStepPath', [None])[0] == step['id']]
            statuses = [latest.get('results', {}).get(case['id'], {}).get('status', 'pending') for case in children]
            status = next((s for s in ('failed', 'blocked', 'pending') if s in statuses),
                          'skipped' if statuses and all(s == 'skipped' for s in statuses) else 'passed')
            steps[step['id']] = {'index': index, 'action': 'include-pipeline',
                'pipelineId': step['pipelineId'], 'expectedStatus': 'passed', 'status': status,
                'summary': f"引入 {step['pipelineId']}：共 {len(children)} 步"}
        return {"run": {
            "runId": latest["runId"], "createdAt": latest.get("createdAt"),
            "conclusion": conclusion(latest), "steps": steps,
            "revision": latest["plan"]["pipeline"].get("revision"),
        }}

    def _conflict(
        self, kind: str, object_id: str, updating: bool = False
    ) -> str | None:
        groups, cases = build_catalog_bundle(
            self.repo_root, discover_inventory(self.repo_root)
        )
        if kind == "pipelines":
            return None
        objects = groups if kind == "groups" else cases
        match = next((item for item in objects if item.id == object_id), None)
        if match is None:
            return None
        if updating and match.source_type == "user-authored":
            return None
        return f"ID already exists in {match.source_type} source: {match.source_path}"

    def validate(self, kind: str, value: dict[str, Any]) -> dict[str, Any]:
        if kind == "groups":
            errors = validate_group(value)
        elif kind == "cases":
            errors = validate_case(
                value, {item["id"]: item for item in self.store.list_objects("groups")}
            ) + self.store.fixture_errors(value)
        else:
            _, cases = build_catalog_bundle(
                self.repo_root, discover_inventory(self.repo_root)
            )
            errors = validate_pipeline(value, {case.id for case in cases})
            if not errors:
                from .pipeline_expansion import expand_pipeline
                try:
                    expand_pipeline(value, self.store, {case.id for case in cases})
                except (ValueError, KeyError, FileNotFoundError) as error:
                    errors.append(str(error))
        conflict = self._conflict(
            kind, str(value.get("id", "")), updating=bool(value.get("revision"))
        )
        if conflict:
            errors.append(conflict)
        return {
            "ok": not errors,
            "errors": errors,
            "diff": self.store.preview(kind, value) if not errors else "",
        }

    def save(
        self, kind: str, value: dict[str, Any], expected_revision: str | None = None
    ) -> dict[str, Any]:
        if kind == "pipelines":
            _, cases = build_catalog_bundle(
                self.repo_root, discover_inventory(self.repo_root)
            )
            require_valid(validate_pipeline(value, {case.id for case in cases}))
            from .pipeline_expansion import expand_pipeline
            expand_pipeline(value, self.store, {case.id for case in cases})
        conflict = self._conflict(
            kind, str(value.get("id", "")), updating=expected_revision is not None
        )
        if conflict:
            raise ValueError(conflict)
        return self.store.save(kind, value, expected_revision)

    def archive(self, kind: str, object_id: str, revision: str) -> dict[str, Any]:
        if kind == "groups":
            for case in self.store.list_objects("cases"):
                if case.get("groupId") == object_id:
                    self.store.archive("cases", str(case["id"]), str(case["revision"]))
        return self.store.archive(kind, object_id, revision)

    def restore(self, kind: str, object_id: str, revision: str) -> dict[str, Any]:
        restored = self.store.restore(kind, object_id, revision)
        if kind == "groups":
            for case in list(self.store.list_objects("cases", True)):
                if case.get("groupId") == object_id:
                    self.store.restore("cases", str(case["id"]), str(case["revision"]))
        return restored

    def copy_case(self, case_id: str, new_id: str, group_id: str) -> dict[str, Any]:
        _, cases = build_catalog_bundle(
            self.repo_root, discover_inventory(self.repo_root)
        )
        source = next((case for case in cases if case.id == case_id), None)
        if source is None:
            raise KeyError(case_id)
        conflict = self._conflict("cases", new_id)
        if conflict:
            raise ValueError(conflict)
        target_group = self.store.get("groups", group_id)
        priority = None if target_group.get("kind") == "on-demand" else source.priority
        value = {
            "schemaVersion": 1,
            "id": new_id,
            "name": f"{source.name} (Copy)",
            "groupId": group_id,
            "priority": priority,
            "enabled": False,
            "required": False,
            "executor": "codex-ui" if source.executor == "codex-ui" else "builtin",
            "timeoutSeconds": source.timeout_seconds,
            "requires": list(source.requires),
            "tags": list(source.tags),
            "componentId": source.component_id,
            "description": source.description,
            "instructions": list(source.instructions)
            or ["Execute the copied test contract."],
            "expectations": list(source.expectations),
            "cleanup": list(source.cleanup),
            "fixtures": list(source.fixtures),
            "lifecycle": "draft",
        }
        return self.store.save("cases", value)

    def generate_case(self, description: str, group_id: str) -> dict[str, Any]:
        group = self.store.get("groups", group_id)
        return generate_case_draft(
            self.repo_root / "ai2apps-test-system", description, group
        )

    def store_image_fixture(
        self, case_id: str, filename: str, encoded_content: str
    ) -> dict[str, Any]:
        return self.store.store_image_fixture(case_id, filename, encoded_content)

    def review_trial(
        self,
        case_id: str,
        run_directory: Path,
        supplements: Any,
    ) -> dict[str, Any]:
        current = self.store.get("cases", case_id)
        group = self.store.get("groups", str(current.get("groupId", "")))
        context = trial_context(
            self.repo_root / "ai2apps-test-system", run_directory, case_id
        )
        review = generate_trial_review(
            self.repo_root / "ai2apps-test-system",
            context,
            supplements,
            group,
        )
        proposal = review.get("proposal")
        if not isinstance(proposal, dict):
            raise ValueError("Codex review did not include a valid proposal")
        mutable = {
            "name",
            "priority",
            "required",
            "timeoutSeconds",
            "requires",
            "tags",
            "componentId",
            "description",
            "instructions",
            "expectations",
            "cleanup",
            "fixtures",
        }
        candidate = {
            key: value
            for key, value in current.items()
            if key not in {"revision", "sourcePath", "sourceType", "editable"}
        }
        defaults: dict[str, Any] = {
            "required": False,
            "timeoutSeconds": 300,
            "requires": [],
            "tags": [],
            "componentId": None,
            "description": "",
            "instructions": [],
            "expectations": [],
            "cleanup": [],
            "fixtures": [],
        }
        changed = any(
            proposal.get(key, current.get(key, defaults.get(key)))
            != current.get(key, defaults.get(key))
            for key in mutable
        )
        candidate.update(
            {
                key: proposal[key]
                for key in mutable
                if key in proposal
                and (key in current or proposal[key] != defaults.get(key))
            }
        )
        candidate.update(
            id=current["id"],
            groupId=current["groupId"],
            executor=current["executor"],
            enabled=False if changed else bool(current.get("enabled", False)),
            lifecycle="draft" if changed else current.get("lifecycle", "draft"),
        )
        errors = validate_case(candidate, {str(group["id"]): group})
        errors.extend(self.store.fixture_errors(candidate))
        if errors:
            raise ValueError(
                "Codex generated an invalid revision: " + "; ".join(errors)
            )
        requests = review.get("userRequests", [])
        if not isinstance(requests, list):
            raise ValueError("Codex review returned invalid user requests")
        return {
            **review,
            "proposal": {**candidate, "revision": current["revision"]},
            "diff": self.store.preview("cases", candidate),
            "hasChanges": changed,
            "readyToApply": not any(
                isinstance(item, dict) and item.get("required") for item in requests
            ),
        }
