"""Test the production serving-meter seam without loading MLX or user models."""

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest


def meter_fixture():
    tree = ast.parse(Path("omlx/server.py").read_text())
    function = next(
        n
        for n in tree.body
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "_measure_agent_context"
    )
    state = {"released": False, "tools": None}

    class Lease:
        async def release(self):
            state["released"] = True

    class Engine:
        tokenizer = object()
        supports_kv_continuity = True

        def count_chat_tokens(self, messages, tools, **kwargs):
            state["tools"] = tools
            state["template"] = kwargs
            return 500

    async def get_engine(model, lease):
        return Engine()

    class Request:
        @staticmethod
        def model_validate(payload):
            return SimpleNamespace(
                model=payload["model"],
                messages=[
                    SimpleNamespace(content=m["content"]) for m in payload["messages"]
                ],
                chat_template_kwargs=None,
                reasoning_effort=None,
                tool_choice="auto",
                tools=payload.get("tools"),
            )

    namespace = {
        "ChatCompletionRequest": Request,
        "resolve_model_id": lambda model: model,
        "_server_state": SimpleNamespace(
            default_model="test",
            engine_pool=SimpleNamespace(get_entry=lambda model: object()),
            mcp_manager=None,
            sampling=SimpleNamespace(max_tokens=32768),
        ),
        "_LLMEngineLease": Lease,
        "get_engine_for_model": get_engine,
        "_serving_model_id": lambda lease, model: "actual",
        "VLMBatchedEngine": type("VLM", (), {}),
        "get_model_settings_for_request": lambda model: None,
        "merge_chat_template_request_kwargs": lambda ms, kwargs: kwargs,
        "merge_reasoning_effort_chat_template_kwargs": lambda kwargs, effort: kwargs,
        "uses_native_reasoning_content": lambda *args, **kwargs: False,
        "extract_text_content": lambda *args, **kwargs: [
            {"role": "user", "content": "test"}
        ],
        "detect_and_strip_partial": lambda messages: False,
        "convert_tools_for_template": lambda tools: tools,
        "enrich_tool_params_for_gemma4": lambda tools: tools,
        "prepare_system_messages_for_template": lambda messages, tokenizer, **kwargs: (
            messages
        ),
        "_unsupported_mid_system_policy": lambda: "merge",
        "get_max_context_window": lambda model: 8192 if model == "actual" else 32768,
    }
    exec(
        compile(
            ast.Module(body=[function], type_ignores=[]), "<serving-meter>", "exec"
        ),
        namespace,
    )
    return namespace["_measure_agent_context"], state


@pytest.mark.asyncio
async def test_actual_route_schema_reservation_and_lease_release():
    measure, state = meter_fixture()
    tools = [{"type": "function", "function": {"name": "echo"}}]
    result = await measure(
        {
            "model": "requested",
            "messages": [{"role": "user", "content": "test"}],
            "tools": tools,
        },
        SimpleNamespace(cache_namespace="session"),
    )
    assert result["model"] == "actual" and result["capacity"] == 8192
    assert result["input_tokens"] == 500 and result["token_count_exact"]
    assert result["output_reservation"] == 2048
    assert state["tools"] == tools and state["released"]
    assert state["template"]["chat_template_kwargs"]["drop_thinking"] is False


@pytest.mark.asyncio
async def test_multimodal_meter_declares_fallback():
    measure, state = meter_fixture()
    result = await measure(
        {
            "model": "test",
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "image_url", "image_url": {"url": "image"}}],
                }
            ],
        },
        SimpleNamespace(cache_namespace="session"),
    )
    assert result is None
    assert not state["released"]  # No engine lease was acquired.
