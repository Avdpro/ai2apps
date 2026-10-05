import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import Response

from ai2apps.api.agent_platform import (
    AgentPresentationSpec,
    _create_presentation_for_result,
)


def test_model_schema_includes_the_paths_required_by_runtime_validation():
    schema = AgentPresentationSpec.model_json_schema()
    assert schema["properties"]["data_path"]["pattern"].startswith(r"^\$")
    assert "pattern" in schema["$defs"]["AgentPresentationField"]["properties"]["path"]


def completion(spec, finish="stop"):
    return Response(
        content=json.dumps(
            {
                "choices": [
                    {
                        "finish_reason": finish,
                        "message": {
                            "content": spec
                            if isinstance(spec, str)
                            else json.dumps(spec)
                        },
                    }
                ]
            }
        ),
        media_type="application/json",
    )


async def present(responses):
    invoke = AsyncMock(side_effect=responses)
    model = SimpleNamespace(
        id="standard", endpoints={"chat_completions": "/v1/chat/completions"}
    )
    runtime = SimpleNamespace(
        model_manager=SimpleNamespace(resolve_default_model=lambda _: model.id),
        model_invocations=SimpleNamespace(
            model=lambda _: model,
            context_for_actor=lambda *a, **kw: None,
            invoke_foreground_json=invoke,
        ),
    )
    response = await _create_presentation_for_result(
        runtime=runtime,
        principal=SimpleNamespace(actor_user_id="owner"),
        http_request=None,
        result={"items": [{"title": "Result", "url": "https://example.com/"}]},
        locale="zh",
        request_id="recovery-check",
        session_id="session",
    )
    return response, invoke


VALID = {
    "version": 1,
    "view": "table",
    "data_path": "$.items",
    "fields": [{"path": "title", "label": "标题"}],
}


@pytest.mark.asyncio
async def test_invalid_path_repaired_once_without_modifying_results():
    invalid = {**VALID, "data_path": "$.missing"}
    result, invoke = await present([completion(invalid), completion(VALID)])
    assert result["presentation"]["data_path"] == "$.items"
    assert invoke.await_count == 2
    payload = invoke.await_args_list[1].args[2]
    assert "data_path does not exist" in payload["messages"][-1]["content"]
    assert payload["max_tokens"] == 3000
    assert invoke.await_args_list[1].kwargs["request_id"] == "recovery-check-repair"


@pytest.mark.asyncio
async def test_truncated_json_repaired_once(caplog):
    result, invoke = await present(
        [completion('{"version":1', "length"), completion(VALID)]
    )
    assert result["presentation"]["view"] == "table"
    assert invoke.await_count == 2
    assert "finish=length" in caplog.text


@pytest.mark.asyncio
async def test_repeated_invalid_schema_reports_safe_diagnostics(caplog):
    invalid = {**VALID, "html": "PRIVATE RESPONSE CONTENT"}
    response, invoke = await present([completion(invalid), completion(invalid)])
    body = json.loads(response.body)
    assert response.status_code == 422
    assert invoke.await_count == 2
    assert body["error"]["details"]["attempts"] == 2
    assert "html" in body["error"]["details"]["reason"]
    assert "PRIVATE RESPONSE CONTENT" not in response.body.decode()
    assert "PRIVATE RESPONSE CONTENT" not in caplog.text


@pytest.mark.asyncio
async def test_model_http_failure_is_not_retried_as_schema_repair():
    response, invoke = await present([Response(status_code=503)])
    assert response.status_code == 502
    assert invoke.await_count == 1
