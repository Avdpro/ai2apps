from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from ai2apps_test.trial_review import generate_trial_review, review_prompt


def _review() -> dict:
    return {
        "summary": "缺少用户提供的图片样本。",
        "resultAssessment": "Case 被正确阻断，尚不能判断产品能力。",
        "automaticChanges": [
            {"field": "instructions", "reason": "明确使用受管理的图片样本。"}
        ],
        "userRequests": [
            {
                "id": "sample-image",
                "kind": "image",
                "title": "提供图片样本",
                "description": "选择一张无隐私内容的图片。",
                "why": "两种模型必须使用同一输入。",
                "acceptanceCriteria": ["PNG、JPEG、WebP 或 GIF"],
                "required": True,
            }
        ],
        "nonCaseIssues": [],
        "proposal": {
            "name": "图片对话",
            "priority": None,
            "required": False,
            "timeoutSeconds": 720,
            "requires": ["test-account"],
            "tags": ["multimodal"],
            "componentId": None,
            "description": "比较两种模型的图片理解。",
            "instructions": ["上传同一张受管理图片。"],
            "expectations": ["两个回答都与图片事实一致。"],
            "cleanup": ["删除测试对话。"],
            "fixtures": [],
        },
    }


def test_trial_review_uses_read_only_codex_and_requests_user_material(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict = {}

    def fake_run(command: list[str], **options) -> subprocess.CompletedProcess[str]:
        assert options["env"]["PATH"] == "/resolved/bin:/usr/bin"
        captured.update(command=command, options=options)
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(json.dumps(_review(), ensure_ascii=False), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stderr="")

    monkeypatch.setattr(
        "ai2apps_test.trial_review.codex_environment", lambda: ("/usr/bin/codex", {"PATH": "/resolved/bin:/usr/bin"})
    )
    monkeypatch.setattr("ai2apps_test.trial_review.subprocess.run", fake_run)

    result = generate_trial_review(
        tmp_path,
        {"case": {"id": "picture-chat"}, "result": {"status": "blocked"}},
        [],
        {"id": "pictures", "kind": "on-demand"},
    )

    assert result["userRequests"][0]["kind"] == "image"
    assert "read-only" in captured["command"]
    assert "--ephemeral" in captured["command"]
    assert "不能通过删除、弱化" in captured["options"]["input"]
    assert "不得自行从网络寻找" in captured["options"]["input"]


def test_trial_review_rejects_secret_like_user_supplement(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="secret-like"):
        generate_trial_review(
            tmp_path,
            {},
            [{"requestId": "details", "note": "password: private", "fixturePath": ""}],
            {"id": "pictures", "kind": "on-demand"},
        )


def test_review_prompt_keeps_product_failure_out_of_case_rewrite() -> None:
    prompt = review_prompt({}, [], {"id": "regular", "kind": "regular"})
    assert "产品问题放入 nonCaseIssues" in prompt
    assert "Computer Use" in prompt
    assert "P0、P1、P2 或 P3" in prompt
