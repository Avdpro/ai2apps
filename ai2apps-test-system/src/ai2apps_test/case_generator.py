from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .catalog_validation import CatalogValidationError, require_valid, validate_case
from .redact import redact_text


class CaseGenerationError(RuntimeError):
    pass


SECRET_ASSIGNMENT = re.compile(
    r"(?i)(password|token|cookie|credential|authorization|lease[ -]?token)\s*[:=]"
)


OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9.-]{0,127}$"},
        "name": {"type": "string", "minLength": 1},
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
        "id",
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
}


def generation_prompt(description: str, group: dict[str, Any]) -> str:
    priority_rule = (
        "priority 必须是 null，因为目标 Group 是按需测试。"
        if group.get("kind") == "on-demand"
        else "根据风险与运行成本选择 P0、P1、P2 或 P3。"
    )
    return f"""为 AI2Apps Test Center 生成一个结构化 codex-ui Test Case 草稿。

用户描述：
{description}

目标 Group：{group.get('name')}（ID: {group.get('id')}，类型: {group.get('kind')}）

要求：
- 只输出符合给定 JSON Schema 的对象。
- 使用稳定、简短、全局可读的英文小写 ID；name、description、步骤和预期使用用户描述所用语言。
- {priority_rule}
- instructions 必须是可观察、可执行的 UI 步骤；expectations 必须是逐项可判定的结果；cleanup 只包含本 Case 创建状态的清理。
- AI2Apps Shell、App/Mini-Entry 启动、原生窗口和 macOS 交互使用 Computer Use，不把它们描述成 WebDriver BiDi 操作。
- 只有明确测试 AI Browser 网页浏览上下文时才可以提及受保护的 AI2Apps WebDriver BiDi Gateway。
- 不生成 Shell 命令、任意代码、密码、Token、Cookie、Credential、Bearer 或账号秘密。
- requires 只在确有依赖时使用稳定能力名，例如 test-account；不要猜测秘密或本机路径。
- 新建草稿时 fixtures 使用空数组；测试素材必须由用户通过 Test Center 的受管理上传流程补充。
- timeoutSeconds 给出保守但合理的单 Case 超时；required 表示该 Case 被明确选中后是否影响本轮结论。
"""


def generate_case_draft(
    project_root: Path,
    description: str,
    group: dict[str, Any],
    *,
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    description = description.strip()
    if not description:
        raise ValueError("test description is required")
    if len(description) > 4_000:
        raise ValueError("test description must not exceed 4000 characters")
    if SECRET_ASSIGNMENT.search(description) or "authorization: bearer " in description.lower():
        raise ValueError("test description must not contain secret-like values")
    executable = shutil.which("codex")
    if executable is None:
        raise CaseGenerationError("Codex CLI is not installed or unavailable on PATH")

    with tempfile.TemporaryDirectory(prefix="ai2apps-case-draft-") as temporary:
        temporary_root = Path(temporary)
        schema_path = temporary_root / "schema.json"
        output_path = temporary_root / "draft.json"
        schema_path.write_text(json.dumps(OUTPUT_SCHEMA), encoding="utf-8")
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
        try:
            environment = {
                key: os.environ[key]
                for key in ("PATH", "HOME", "CODEX_HOME", "LANG", "LC_ALL", "TMPDIR")
                if key in os.environ
            }
            completed = subprocess.run(
                command,
                input=generation_prompt(description, group),
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=timeout_seconds,
                check=False,
                env=environment,
            )
        except subprocess.TimeoutExpired as error:
            raise CaseGenerationError("Codex case generation timed out") from error
        except OSError as error:
            raise CaseGenerationError("Codex case generation could not start") from error
        if completed.returncode != 0 or not output_path.is_file():
            detail = redact_text(completed.stderr or "").strip()[-800:]
            message = "Codex could not generate a case draft"
            if detail:
                message += f": {detail}"
            raise CaseGenerationError(message)
        try:
            generated = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CaseGenerationError("Codex returned an invalid case draft") from error
    if not isinstance(generated, dict):
        raise CaseGenerationError("Codex returned an invalid case draft")
    if SECRET_ASSIGNMENT.search(json.dumps(generated, ensure_ascii=False)):
        raise CaseGenerationError("Codex generated secret-like content")

    draft = {
        "schemaVersion": 1,
        "id": generated.get("id"),
        "name": generated.get("name"),
        "groupId": group["id"],
        "priority": (
            None if group.get("kind") == "on-demand" else generated.get("priority")
        ),
        "enabled": False,
        "required": bool(generated.get("required", False)),
        "executor": "codex-ui",
        "timeoutSeconds": generated.get("timeoutSeconds"),
        "requires": generated.get("requires", []),
        "tags": generated.get("tags", []),
        "componentId": generated.get("componentId"),
        "description": generated.get("description", ""),
        "instructions": generated.get("instructions", []),
        "expectations": generated.get("expectations", []),
        "cleanup": generated.get("cleanup", []),
        "fixtures": [],
        "lifecycle": "draft",
    }
    errors = validate_case(draft, {str(group["id"]): group})
    try:
        require_valid(errors)
    except CatalogValidationError as error:
        raise CaseGenerationError(f"Codex generated an invalid case: {error}") from error
    return draft
