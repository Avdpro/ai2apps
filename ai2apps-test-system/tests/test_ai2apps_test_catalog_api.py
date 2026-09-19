from __future__ import annotations

import base64
import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import pytest
from ai2apps_test.selector import HTML, control


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "tests" / "ats" / "catalog").mkdir(parents=True)
    (root / "tests" / "ats" / "catalog" / "base.json").write_text(
        '{"schemaVersion":"ai2apps.test-catalog.v1","cases":[]}', encoding="utf-8"
    )
    (root / "ai2apps" / "apps").mkdir(parents=True)
    (root / "ai2apps" / "apps" / "system.py").write_text(
        "_SYSTEM_APP_MANIFESTS_BASE = []\n", encoding="utf-8"
    )
    return root


def test_test_center_catalog_api_requires_token_and_origin(
    tmp_path: Path, monkeypatch
) -> None:
    printed: list[str] = []
    monkeypatch.setattr(
        "builtins.print", lambda value, **_kwargs: printed.append(str(value))
    )
    monkeypatch.setattr(
        "ai2apps_test.catalog_service.CatalogService.generate_case",
        lambda _service, description, group_id: {
            "id": "generated.case",
            "name": description,
            "groupId": group_id,
            "enabled": False,
            "lifecycle": "draft",
        },
    )
    outcome: list[dict] = []
    errors: list[Exception] = []

    def serve() -> None:
        try:
            outcome.append(
                control(
                    {"priority": "P1", "groups": []},
                    lambda *_: {},
                    open_browser=False,
                    repo_root=_repo(tmp_path),
                )
            )
        except Exception as error:
            errors.append(error)

    thread = threading.Thread(target=serve)
    thread.start()
    for _ in range(100):
        if printed:
            break
        time.sleep(0.01)
    if not printed and errors and isinstance(errors[0], PermissionError):
        pytest.skip("sandbox does not permit loopback listeners")
    url = json.loads(printed[0])["selectorUrl"]
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    token = parsed.fragment
    catalog = json.loads(
        urllib.request.urlopen(f"{origin}/api/catalog?token={token}").read()
    )
    assert catalog["groups"] == []
    group = {
        "schemaVersion": 1,
        "id": "api-group",
        "name": "API Group",
        "kind": "on-demand",
        "enabled": False,
        "defaultSelected": False,
        "lifecycle": "draft",
    }
    rejected = urllib.request.Request(
        f"{origin}/api/catalog/groups?token={token}",
        data=json.dumps(group).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as denied:
        urllib.request.urlopen(rejected)
    assert denied.value.code == 404
    request = urllib.request.Request(
        f"{origin}/api/catalog/groups?token={token}",
        data=json.dumps(group).encode(),
        headers={"Content-Type": "application/json", "Origin": origin},
        method="POST",
    )
    created = json.loads(urllib.request.urlopen(request).read())
    assert created["id"] == "api-group"
    generate = urllib.request.Request(
        f"{origin}/api/catalog/cases/generate?token={token}",
        data=json.dumps(
            {"description": "验证设置页面", "groupId": "api-group"}
        ).encode(),
        headers={"Content-Type": "application/json", "Origin": origin},
        method="POST",
    )
    generated = json.loads(urllib.request.urlopen(generate).read())
    assert generated["name"] == "验证设置页面"
    assert generated["enabled"] is False
    case = {
        "schemaVersion": 1,
        "id": "api.case",
        "name": "API Case",
        "groupId": "api-group",
        "priority": None,
        "enabled": False,
        "required": False,
        "executor": "codex-ui",
        "timeoutSeconds": 300,
        "requires": [],
        "tags": [],
        "componentId": None,
        "description": "trial return contract",
        "instructions": ["Open the visible test UI."],
        "expectations": ["The UI remains available."],
        "cleanup": [],
        "lifecycle": "draft",
    }
    create_case = urllib.request.Request(
        f"{origin}/api/catalog/cases?token={token}",
        data=json.dumps(case).encode(),
        headers={"Content-Type": "application/json", "Origin": origin},
        method="POST",
    )
    urllib.request.urlopen(create_case).read()
    trial = urllib.request.Request(
        f"{origin}/api/catalog/cases/api.case/trial-run?token={token}",
        data=b"{}",
        headers={"Content-Type": "application/json", "Origin": origin},
        method="POST",
    )
    urllib.request.urlopen(trial).read()
    upload = urllib.request.Request(
        f"{origin}/api/catalog/cases/api.case/fixtures?token={token}",
        data=json.dumps(
            {
                "filename": "sample.png",
                "contentBase64": base64.b64encode(b"\x89PNG\r\n\x1a\nfixture").decode(),
            }
        ).encode(),
        headers={"Content-Type": "application/json", "Origin": origin},
        method="POST",
    )
    uploaded = json.loads(urllib.request.urlopen(upload).read())
    assert uploaded["path"].startswith("tests/ats/fixtures/api.case/")
    returned = None
    for _ in range(100):
        return_request = urllib.request.Request(
            f"{origin}/api/catalog/trial/return?token={token}",
            data=b"{}",
            headers={"Content-Type": "application/json", "Origin": origin},
            method="POST",
        )
        try:
            returned = json.loads(urllib.request.urlopen(return_request).read())
            break
        except urllib.error.HTTPError as error:
            assert error.code == 409
            time.sleep(0.01)
    assert returned == {"status": "selecting"}
    assert (
        json.loads(
            urllib.request.urlopen(f"{origin}/api/catalog?token={token}").read()
        )["cases"][0]["id"]
        == "api.case"
    )
    cancel = urllib.request.Request(
        f"{origin}/api/submit?token={token}",
        data=b'{"cancelled":true}',
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(cancel).read()
    thread.join(timeout=2)
    assert outcome[0]["phase"] == "cancelled"


def test_management_ui_exposes_crud_diff_trial_and_diagnostics() -> None:
    for text in (
        "测试资产管理",
        "Diff 预览",
        "试运行",
        "复制为自定义",
        "覆盖诊断",
        "RUN MANIFEST",
        "由 Codex 生成参数",
        "描述要测试什么",
        "返回编辑 Case",
        "让 Codex 改进 Case",
        "需要用户补充",
        "Pipeline 测试轨迹",
        "全部退出再启动",
    ):
        assert text in HTML
    assert "/* __TEST_CENTER_STYLE__ */" not in HTML
    assert "/* __TEST_CENTER_SCRIPT__ */" not in HTML
    assert 'id="catalog-form"' in HTML
    assert 'id="lifecycle-stepper"' in HTML
    assert 'id="return-to-case"' in HTML
    assert 'id="improve-case"' in HTML
    assert 'id="review-dialog"' in HTML
    assert 'id="pipeline-editor-shell"' in HTML
    assert 'id="pipeline-cases-dialog"' in HTML
    assert 'class="library-shell"' in HTML
    assert 'class="inspector-scroll"' in HTML
    assert "#generate-description" in HTML
