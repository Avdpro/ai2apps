from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from ai2apps_test.case_generator import generate_case_draft, generation_prompt


def _generated() -> dict:
    return {
        "id": "gallery.drag-to-composer",
        "name": "拖动图片到视频编辑器",
        "priority": "P1",
        "required": True,
        "timeoutSeconds": 420,
        "requires": ["test-account"],
        "tags": ["gallery", "drag-drop"],
        "componentId": "ai2apps.gallery",
        "description": "验证 Gallery 到 Video Composer 的拖放流程。",
        "instructions": ["打开 Gallery。", "把第一张图片拖到 Video Composer。"],
        "expectations": ["目标轨道出现对应 Clip。"],
        "cleanup": ["删除本 Case 创建的临时工程。"],
    }


def test_generate_case_uses_structured_codex_draft_and_forces_safe_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict = {}

    def fake_run(command: list[str], **options) -> subprocess.CompletedProcess[str]:
        assert options["env"]["PATH"] == "/resolved/bin:/usr/bin"
        captured.update(command=command, options=options)
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(json.dumps(_generated()), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stderr="")

    monkeypatch.setattr("ai2apps_test.case_generator.codex_environment", lambda: ("/usr/bin/codex", {"PATH": "/resolved/bin:/usr/bin"}))
    monkeypatch.setattr("ai2apps_test.case_generator.subprocess.run", fake_run)
    group = {"id": "corner-cases", "name": "Corner Cases", "kind": "on-demand"}

    draft = generate_case_draft(tmp_path, "测试 Gallery 拖放", group)

    assert draft["groupId"] == "corner-cases"
    assert draft["priority"] is None
    assert draft["executor"] == "codex-ui"
    assert draft["enabled"] is False
    assert draft["lifecycle"] == "draft"
    assert draft["fixtures"] == []
    assert "--sandbox" in captured["command"]
    assert "read-only" in captured["command"]
    assert "--ephemeral" in captured["command"]
    assert "--ignore-user-config" in captured["command"]
    assert captured["options"]["stdout"] is subprocess.DEVNULL
    assert "AI2Apps Shell" in captured["options"]["input"]


def test_generate_case_rejects_empty_or_secret_like_description(tmp_path: Path) -> None:
    group = {"id": "corner-cases", "name": "Corner Cases", "kind": "on-demand"}
    with pytest.raises(ValueError, match="required"):
        generate_case_draft(tmp_path, " ", group)
    with pytest.raises(ValueError, match="secret-like"):
        generate_case_draft(tmp_path, "测试登录，password: do-not-store", group)


def test_generation_prompt_keeps_shell_on_computer_use() -> None:
    prompt = generation_prompt(
        "打开设置并验证页面",
        {"id": "regular", "name": "Regular", "kind": "regular"},
    )
    assert "Computer Use" in prompt
    assert "P0、P1、P2 或 P3" in prompt
    assert "不生成 Shell 命令" in prompt
