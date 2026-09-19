from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .case_generator import SECRET_ASSIGNMENT, CaseGenerationError
from .codex_driver import read_codex_output
from .redact import redact_text
from .state import read_json

REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "resultAssessment": {"type": "string"},
        "automaticChanges": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "field": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["field", "reason"],
            },
        },
        "userRequests": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string", "pattern": "^[a-z0-9-]{1,64}$"},
                    "kind": {"enum": ["image", "text", "confirmation"]},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "why": {"type": "string"},
                    "acceptanceCriteria": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "required": {"type": "boolean"},
                },
                "required": [
                    "id",
                    "kind",
                    "title",
                    "description",
                    "why",
                    "acceptanceCriteria",
                    "required",
                ],
            },
        },
        "nonCaseIssues": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "category": {
                        "enum": ["product", "environment", "harness", "testability-gap"]
                    },
                    "summary": {"type": "string"},
                    "recommendation": {"type": "string"},
                },
                "required": ["category", "summary", "recommendation"],
            },
        },
        "proposal": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "name": {"type": "string"},
                "priority": {
                    "type": ["string", "null"],
                    "enum": ["P0", "P1", "P2", "P3", None],
                },
                "required": {"type": "boolean"},
                "timeoutSeconds": {"type": "integer", "minimum": 5, "maximum": 3600},
                "requires": {"type": "array", "items": {"type": "string"}},
                "tags": {"type": "array", "items": {"type": "string"}},
                "componentId": {"type": ["string", "null"]},
                "description": {"type": "string"},
                "instructions": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string"},
                },
                "expectations": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string"},
                },
                "cleanup": {"type": "array", "items": {"type": "string"}},
                "fixtures": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
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
            ],
        },
    },
    "required": [
        "summary",
        "resultAssessment",
        "automaticChanges",
        "userRequests",
        "nonCaseIssues",
        "proposal",
    ],
}


def _safe_supplements(values: Any) -> list[dict[str, str]]:
    if values is None:
        return []
    if not isinstance(values, list) or len(values) > 20:
        raise ValueError("supplements must be a list with at most 20 items")
    result: list[dict[str, str]] = []
    for value in values:
        if not isinstance(value, dict):
            raise ValueError("each supplement must be an object")
        request_id = str(value.get("requestId", ""))
        if not re.fullmatch(r"[a-z0-9-]{1,64}", request_id):
            raise ValueError("invalid supplement request ID")
        note = str(value.get("note", "")).strip()
        fixture_path = str(value.get("fixturePath", "")).strip()
        if len(note) > 2_000 or len(fixture_path) > 300:
            raise ValueError("supplement is too long")
        if SECRET_ASSIGNMENT.search(note) or "authorization: bearer " in note.lower():
            raise ValueError("supplement must not contain secret-like values")
        result.append(
            {"requestId": request_id, "note": note, "fixturePath": fixture_path}
        )
    return result


def trial_context(
    project_root: Path, run_directory: Path, case_id: str
) -> dict[str, Any]:
    run_root = (project_root / "artifacts" / "runs").resolve()
    run_directory = run_directory.resolve()
    if run_root not in run_directory.parents:
        raise ValueError("trial run directory is outside the managed run root")
    state = read_json(run_directory / "state.json")
    case = next(
        (
            item
            for item in state.get("plan", {}).get("cases", [])
            if item.get("id") == case_id
        ),
        None,
    )
    if not isinstance(case, dict):
        raise ValueError("trial run does not contain the requested case")
    result = state.get("results", {}).get(case_id, {})
    process: list[dict[str, str]] = []
    driver = state.get("codexDriver")
    if isinstance(driver, dict) and driver.get("log"):
        log_path = Path(str(driver["log"]))
        if log_path.resolve().parent == (run_directory / "logs").resolve():
            for entry in read_codex_output(log_path).get("entries", [])[-80:]:
                process.append(
                    {
                        "title": str(entry.get("title", ""))[:500],
                        "detail": str(entry.get("detail", ""))[:2_000],
                        "status": str(entry.get("status", ""))[:40],
                    }
                )
    serialized = redact_text(
        json.dumps(
            {"case": case, "result": result, "process": process},
            ensure_ascii=False,
        )
    )
    return json.loads(serialized)


def review_prompt(
    context: dict[str, Any], supplements: list[dict[str, str]], group: dict[str, Any]
) -> str:
    priority_rule = (
        "proposal.priority 必须保持为 null。"
        if group.get("kind") == "on-demand"
        else "proposal.priority 必须是 P0、P1、P2 或 P3。"
    )
    return f"""复盘一次 AI2Apps Test Center 隔离试运行，并生成 Case 修订候选。

试运行上下文（已脱敏）：
{json.dumps(context, ensure_ascii=False)}

用户补充（已脱敏）：
{json.dumps(supplements, ensure_ascii=False)}

要求：
- 只输出符合 JSON Schema 的对象，使用原 Case 的语言。
- 无论测试通过、失败或阻断，都检查步骤、断言、fixture、超时和 cleanup 是否可重放。
- 先区分 Case 定义问题、需要用户材料、产品缺陷、环境/Executor/Harness 问题。
- 绝不能通过删除、弱化或改写关键预期来掩盖产品失败；产品问题放入 nonCaseIssues。
- 缺少图片时创建明确的 image userRequest，并另建 text userRequest 要求用户提供可核对的主体、属性、数量或其他标准答案。说明缺什么、为什么、验收条件和补充后会执行什么。
- 不得自行从网络寻找或虚构测试素材。只有用户补充中的受管理 fixturePath 才能加入 proposal.fixtures。
- 已满足的 userRequest 不再输出；仍缺少的必需输入必须继续输出。
- proposal 必须包含完整的可编辑字段。保留原测试意图，使用可见、可判定的 UI 步骤，不生成 Shell 命令或秘密。
- AI2Apps Shell 操作使用 Computer Use；仅明确测试 AI Browser 网页时使用受保护的 BiDi Gateway。
- {priority_rule}
"""


def generate_trial_review(
    project_root: Path,
    context: dict[str, Any],
    supplements: Any,
    group: dict[str, Any],
    *,
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    safe_supplements = _safe_supplements(supplements)
    executable = shutil.which("codex")
    if executable is None:
        raise CaseGenerationError("Codex CLI is not installed or unavailable on PATH")
    with tempfile.TemporaryDirectory(prefix="ai2apps-trial-review-") as temporary:
        root = Path(temporary)
        schema_path = root / "schema.json"
        output_path = root / "review.json"
        schema_path.write_text(json.dumps(REVIEW_SCHEMA), encoding="utf-8")
        command = [
            executable,
            "exec",
            "--sandbox",
            "read-only",
            "--ephemeral",
            "--ignore-user-config",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            "-C",
            str(project_root),
            "-",
        ]
        environment = {
            key: os.environ[key]
            for key in ("PATH", "HOME", "CODEX_HOME", "LANG", "LC_ALL", "TMPDIR")
            if key in os.environ
        }
        try:
            completed = subprocess.run(
                command,
                input=review_prompt(context, safe_supplements, group),
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=timeout_seconds,
                check=False,
                env=environment,
            )
        except subprocess.TimeoutExpired as error:
            raise CaseGenerationError("Codex trial review timed out") from error
        except OSError as error:
            raise CaseGenerationError("Codex trial review could not start") from error
        if completed.returncode != 0 or not output_path.is_file():
            detail = redact_text(completed.stderr or "").strip()[-800:]
            raise CaseGenerationError(
                "Codex could not review the trial run"
                + (f": {detail}" if detail else "")
            )
        try:
            review = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CaseGenerationError(
                "Codex returned an invalid trial review"
            ) from error
    if not isinstance(review, dict):
        raise CaseGenerationError("Codex returned an invalid trial review")
    if SECRET_ASSIGNMENT.search(json.dumps(review, ensure_ascii=False)):
        raise CaseGenerationError("Codex generated secret-like review content")
    return review
