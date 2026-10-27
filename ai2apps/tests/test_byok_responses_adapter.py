import json

import httpx
import pytest
from fastapi import HTTPException

from ai2apps.cloud_gateway import proxy_cloud_chat_completion, _RESPONSES_TOOL_MODELS, _MODERN_TOKEN_PARAMETER_MODELS
from ai2apps.fusion.openai_responses import responses_body


PROVIDER = {"base_url": "https://api.openai.com/v1", "api_key": "secret-fixture-key",
            "model_id": "arbitrary-reasoning-model", "protocol": "openai"}


class Store:
    def resolve_cloud_model(self, model):
        return dict(PROVIDER)


class Request:
    model = "cloud/openai/arbitrary-reasoning-model"
    stream = False

    def model_dump(self, **kwargs):
        return {"model": self.model, "stream": self.stream, "max_tokens": 4000,
                "reasoning_effort": "high", "temperature": 0.2,
                "messages": [{"role": "system", "content": "Use registered tools"},
                             {"role": "user", "content": "List tasks"}],
                "tools": [{"type": "function", "function": {"name": "some_tool", "parameters": {"type": "object"}}}]}


def result(output, status="completed"):
    return {"id": "resp_fixture", "model": PROVIDER["model_id"], "status": status, "output": output,
            "usage": {"input_tokens": 22, "output_tokens": 9, "total_tokens": 31,
                      "output_tokens_details": {"reasoning_tokens": 5}}}


@pytest.fixture(autouse=True)
def reset_routes():
    _RESPONSES_TOOL_MODELS.clear()
    _MODERN_TOKEN_PARAMETER_MODELS.clear()
    yield
    _RESPONSES_TOOL_MODELS.clear()
    _MODERN_TOKEN_PARAMETER_MODELS.clear()


@pytest.mark.asyncio
async def test_endpoint_adaptation_then_tool_result_and_final_answer():
    seen = []
    def handler(request):
        body = json.loads(request.content)
        seen.append((request.url.path, body))
        if len(seen) == 1:
            return httpx.Response(400, json={"error": {"message": "max_tokens unsupported; use max_completion_tokens"}})
        if len(seen) == 2:
            return httpx.Response(400, json={"error": {"message": "Function tools with reasoning_effort are not supported. Use Responses API."}})
        assert request.url.path == "/v1/responses"
        assert body["reasoning"] == {"effort": "high"}
        assert body["max_output_tokens"] == 4000
        assert body["store"] is False
        assert "temperature" not in body
        assert body["tools"][0]["name"] == "some_tool"
        assert body["tools"][0]["strict"] is False
        if len(seen) == 3:
            return httpx.Response(200, json=result([{"type": "function_call", "call_id": "call_real",
                "name": "some_tool", "arguments": '{"priority":"A"}'}]))
        assert body["input"][-2]["call_id"] == body["input"][-1]["call_id"] == "call_real"
        assert body["input"][-1]["output"] == '{"count":3}'
        return httpx.Response(200, json=result([{"type": "message", "content": [{"type": "output_text", "text": "3 tasks"}]}]))

    transport = httpx.MockTransport(handler)
    request = Request()
    response = await proxy_cloud_chat_completion(request, base_path=None, model_manager=Store(), transport=transport)
    data = json.loads(response.body)
    message = data["choices"][0]["message"]
    assert message["tool_calls"][0]["id"] == "call_real"
    assert data["choices"][0]["finish_reason"] == "tool_calls"
    original = request.model_dump()
    request.model_dump = lambda **_: {**original, "messages": original["messages"] + [message,
        {"role": "tool", "tool_call_id": "call_real", "content": '{"count":3}'}]}
    response = await proxy_cloud_chat_completion(request, base_path=None, model_manager=Store(), transport=transport)
    data = json.loads(response.body)
    assert data["choices"][0]["message"]["content"] == "3 tasks"
    assert data["usage"]["total_tokens"] == 31
    assert data["usage"]["completion_tokens_details"]["reasoning_tokens"] == 5
    assert len(seen) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("status,base_url,error", [
    (401, PROVIDER["base_url"], "tools require Responses"),
    (400, "https://other.example/v1", "tools require Responses"),
    (400, PROVIDER["base_url"], "Invalid tool arguments"),
])
async def test_no_adaptation_for_unrelated_failures(status, base_url, error):
    class OtherStore(Store):
        def resolve_cloud_model(self, model):
            return {**PROVIDER, "base_url": base_url}
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": {"message": error}})
    with pytest.raises(HTTPException) as caught:
        await proxy_cloud_chat_completion(Request(), base_path=None, model_manager=OtherStore(), transport=httpx.MockTransport(handler))
    assert caught.value.status_code == status
    assert len(calls) == 1


def test_multimodal_and_named_choice_mapping():
    body = responses_body({"model": "any", "reasoning_effort": "none", "tool_choice": {"type": "function", "function": {"name": "f"}},
        "messages": [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "https://image.example/a"}},
                                                    {"type": "text", "text": "Describe"}]}]})
    assert body["reasoning"]["effort"] == "none"
    assert body["tool_choice"] == {"type": "function", "name": "f"}
    assert body["input"][0]["content"][0]["type"] == "input_image"


@pytest.mark.asyncio
async def test_responses_failure_redacted_and_not_cached():
    def handler(request):
        if request.url.path.endswith("completions"):
            return httpx.Response(400, json={"error": {"message": "Function tools require Responses API"}})
        return httpx.Response(400, json={"error": {"message": "Unsupported option secret-fixture-key"}})
    with pytest.raises(HTTPException) as caught:
        await proxy_cloud_chat_completion(Request(), base_path=None, model_manager=Store(), transport=httpx.MockTransport(handler))
    assert caught.value.detail == "Unsupported option [redacted]"
    assert not _RESPONSES_TOOL_MODELS


@pytest.mark.asyncio
async def test_supported_chat_tools_keep_endpoint_and_explicit_no_reasoning():
    request = Request()
    original = request.model_dump()
    request.model_dump = lambda **_: {**original, "reasoning_effort": "none"}
    def handler(upstream):
        assert upstream.url.path == "/v1/chat/completions"
        assert json.loads(upstream.content)["reasoning_effort"] == "none"
        return httpx.Response(200, json={"choices": []})
    response = await proxy_cloud_chat_completion(request, base_path=None, model_manager=Store(), transport=httpx.MockTransport(handler))
    assert response.status_code == 200
    assert not _RESPONSES_TOOL_MODELS


@pytest.mark.asyncio
async def test_streaming_function_arguments_and_usage():
    _RESPONSES_TOOL_MODELS.add((PROVIDER["base_url"], PROVIDER["model_id"]))
    events = [
        {"type": "response.created", "response": {"id": "resp_fixture"}},
        {"type": "response.output_item.added", "item": {"id": "fc_item", "type": "function_call", "call_id": "call_one", "name": "some_tool", "arguments": ""}},
        {"type": "response.function_call_arguments.delta", "item_id": "fc_item", "delta": "{}"},
        {"type": "response.completed", "response": result([{"type": "function_call", "call_id": "call_one", "name": "some_tool", "arguments": "{}"}])},
    ]
    def handler(request):
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(200, text="".join("data: " + json.dumps(e) + "\n\n" for e in events))
    request = Request()
    request.stream = True
    response = await proxy_cloud_chat_completion(request, base_path=None, model_manager=Store(), transport=httpx.MockTransport(handler))
    chunks = [chunk async for chunk in response.body_iterator]
    values = [json.loads(chunk[6:]) for chunk in chunks[:-1]]
    assert values[1]["choices"][0]["delta"]["tool_calls"][0]["id"] == "call_one"
    assert values[2]["choices"][0]["delta"]["tool_calls"][0]["function"]["arguments"] == "{}"
    assert values[-1]["choices"][0]["finish_reason"] == "tool_calls"
    assert values[-1]["usage"]["total_tokens"] == 31
    assert chunks[-1] == "data: [DONE]\n\n"


@pytest.mark.parametrize("tool_name", ["arbitrary_lookup", "vendor_x.inspect", "unknown_business.action"])
def test_wire_adapter_preserves_arbitrary_tool_identity_and_payload(tool_name):
    from ai2apps.fusion.openai_responses import chat_response

    arguments = '{"opaque_business_field":{"value":3}}'
    body = responses_body({"model": "arbitrary-model", "messages": [
        {"role": "assistant", "tool_calls": [{"id": "call_opaque", "function": {
            "name": tool_name, "arguments": arguments}}]},
        {"role": "tool", "tool_call_id": "call_opaque", "content": "uninterpreted result"},
    ]})
    assert body["input"] == [
        {"type": "function_call", "call_id": "call_opaque", "name": tool_name, "arguments": arguments},
        {"type": "function_call_output", "call_id": "call_opaque", "output": "uninterpreted result"},
    ]
    reply = chat_response(result([body["input"][0]]))
    assert reply["choices"][0]["message"]["tool_calls"][0]["function"] == {
        "name": tool_name, "arguments": arguments}


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,status", [(httpx.ReadTimeout, 504), (httpx.ConnectError, 502)])
async def test_transport_failures_are_not_retried_or_leaked(failure, status):
    from ai2apps.fusion.openai_responses import proxy_responses

    calls = []
    def handler(request):
        calls.append(request)
        raise failure("secret-fixture-key", request=request)
    with pytest.raises(HTTPException) as caught:
        await proxy_responses(Request().model_dump(), provider=PROVIDER, transport=httpx.MockTransport(handler))
    assert caught.value.status_code == status
    assert PROVIDER["api_key"] not in caught.value.detail
    assert len(calls) == 1
