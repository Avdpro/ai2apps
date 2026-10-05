from ai2apps.agent_builder import compile_source
from ai2apps.api.agent_platform import _parameterize_exploration_steps


def test_recorded_search_becomes_reusable_input():
    steps = [
        {
            "name": "search",
            "operation": "input",
            "desc": "Search for OpenAI",
            "target": {"intent": "Search box"},
            "arguments": {"value": "OpenAI"},
            "on": {"success": "done", "failed": "failed"},
        }
    ]
    schema = _parameterize_exploration_steps(steps)
    assert schema["properties"]["query"]["default"] == "OpenAI"
    assert steps[0]["arguments"]["value"] == "${input.query}"
    assert steps[0]["target"] == {"intent": "Search box"}
    source = {
        "schema": "ai2apps.agent-source/v1",
        "agent_type": "web",
        "name": "Search",
        "site_scope": ["https://www.google.com/**"],
        "inputs": schema,
        "outputs": {"type": "object"},
        "steps": steps,
    }
    compiled = compile_source(source)
    assert compiled.valid, compiled.report
    assert compiled.ir["inputs"]["properties"]["query"]["default"] == "OpenAI"
    assert compiled.ir["steps"][0]["arguments"]["value"] == "${input.query}"


def test_distinct_inputs_and_repeated_values():
    steps = [
        {
            "operation": "input",
            "arguments": {"value": v},
            "target": {"intent": "Text field"},
        }
        for v in ["first", "second", "first"]
    ]
    schema = _parameterize_exploration_steps(steps)
    assert len(schema["properties"]) == 2
    assert steps[0]["arguments"]["value"] == steps[2]["arguments"]["value"]


def test_other_actions_remain_fixed():
    steps = [
        {"operation": "open", "arguments": {"url": "https://example.com/"}},
        {"operation": "input", "arguments": {"value": "${input.existing}"}},
    ]
    assert _parameterize_exploration_steps(steps)["properties"] == {}
    assert steps[0]["arguments"]["url"] == "https://example.com/"


def test_direct_search_url_parameterizes_query_only():
    steps = [
        {
            "operation": "open",
            "arguments": {
                "url": "https://www.google.com/search?q=OpenAI%E4%B8%8A%E5%B8%82&hl=zh"
            },
        }
    ]
    schema = _parameterize_exploration_steps(steps)
    assert schema["properties"]["query"]["default"] == "OpenAI上市"
    assert (
        steps[0]["arguments"]["url"]
        == "https://www.google.com/search?q=${input.query}&hl=zh"
    )


def test_quoted_description_value_becomes_parameter_and_compiled_binding():
    steps = [
        {
            "name": "search",
            "operation": "input",
            "desc": "在Google搜索框中输入“OpenAI”。",
            "target": {"intent": "搜索输入框"},
            "on": {"success": "done", "failed": "failed"},
        }
    ]
    schema = _parameterize_exploration_steps(steps)
    assert schema["properties"]["query"]["default"] == "OpenAI"
    assert steps[0]["arguments"]["value"] == "${input.query}"
    assert "${input.query}" in steps[0]["desc"]
    result = compile_source(
        {
            "schema": "ai2apps.agent-source/v1",
            "agent_type": "web",
            "name": "Search",
            "site_scope": ["https://www.google.com/**"],
            "inputs": schema,
            "outputs": {"type": "object"},
            "steps": steps,
        }
    )
    assert result.valid, result.report
    assert result.ir["steps"][0]["arguments"]["value"] == "${input.query}"


def test_inference_preserves_existing_optional_inputs_and_is_idempotent():
    existing = {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "default": 10},
            "optional": {"type": "string", "default": "old"},
        },
        "required": [],
    }
    steps = [
        {"operation": "input", "desc": "Type 'new'", "target": {"intent": "Search box"}}
    ]
    schema = _parameterize_exploration_steps(steps, existing)
    assert schema["required"] == ["query"]
    assert schema["properties"]["limit"]["default"] == 10
    assert _parameterize_exploration_steps(steps, schema) == schema
