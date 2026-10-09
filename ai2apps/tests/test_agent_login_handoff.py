import json
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from ai2apps.api.router import create_ai2apps_router
from ai2apps.config import PlatformConfig
from ai2apps.identity import RequestPrincipal
from ai2apps.platform_runtime import PlatformRuntime


def test_login_handoff_rejects_navigation_only_completion_and_exposes_labels(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    prompts = []
    replies = iter([
        {"decision": "complete", "reason": "Opened Weibo"},
        {"decision": "needs_user", "assistance_kind": "authentication", "reason": "请扫码登录，完成后继续"},
        {"decision": "needs_user", "assistance_kind": "preview_approval", "reason": "请先批准普通输入"},
        {"decision": "act", "step": {"name": "login", "desc": "打开微博登录入口", "operation": "click",
            "target": {"intent": "登录/注册"}, "on": {"success": "done", "failed": "failed"}}},
        {"decision": "act", "step": {"name": "type", "desc": "输入文案", "operation": "input", "target": {"intent": "发布框"}}},
        {"decision": "act", "step": {"name": "type", "desc": "输入文案", "operation": "input", "target": {"intent": "发布框"}, "arguments": {"text": "上手数字人制作"}}},
    ])

    class Invocations:
        def model(self, model_id):
            return SimpleNamespace(id=model_id, endpoints=["chat_completions"])

        def context_for_actor(self, actor, **kwargs):
            return SimpleNamespace(actor=actor)

        async def invoke_foreground_json(self, model_id, endpoint, payload, **kwargs):
            prompts.append(payload["messages"])
            return JSONResponse({"choices": [{"message": {"content": json.dumps(next(replies))}}]})

    runtime.model_invocations = Invocations()
    runtime.model_manager = SimpleNamespace(resolve_default_model=lambda purpose: "model")
    principal = RequestPrincipal.legacy_local()
    app = FastAPI()
    app.include_router(create_ai2apps_router(runtime_provider=lambda: runtime, principal_provider=lambda: principal))
    request = {"goal": "用附件发布微博", "page": {"url": "https://weibo.com/newlogin"},
        "observation": {"controls": [{"role": "button", "name": "登录/注册"}], "text_sample": "请扫码登录", "html": "<button data-ai2apps-ref=\"e12\">登录</button>"},
        "attempts": [{"outcome": "success", "source_step": {"operation": "open"}, "evidence": {"result": {"url": "https://weibo.com/"}}}]}
    try:
        with TestClient(app) as client:
            response = client.post("/v1/platform/agent-explorations/next", json=request)
            assert response.status_code == 200, response.text
            assert response.json()["decision"] == "needs_user"
            assert any("登录/注册" in message["content"] for message in prompts[0])
            assert any("data-ai2apps-ref" in message["content"] for message in prompts[0])
            response = client.post("/v1/platform/agent-explorations/next", json=request)
            assert response.status_code == 200, response.text
            assert response.json()["compiled_step"]["operation"] == "click"
            assert any("concrete assistance_kind" in msg["content"] for msg in prompts[-1])
            request["goal"] = "发布微博，内容是：上手数字人制作"
            response = client.post("/v1/platform/agent-explorations/next", json=request)
            assert response.status_code == 200, response.text
            assert response.json()["compiled_step"]["arguments"]["value"] == "上手数字人制作"
            assert any("input requires arguments.value" in msg["content"] for msg in prompts[-1])
    finally:
        runtime.stop()
