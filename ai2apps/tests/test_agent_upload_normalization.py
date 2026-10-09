"""Exercise the actual nested Source normalizer without starting a server."""
import ast
import json
from pathlib import Path
import re
from types import SimpleNamespace
from typing import Any


def test_upload_assets_survive_source_normalization_and_compilation():
    from ai2apps.agent_builder.compiler import compile_source

    tree = ast.parse((Path(__file__).parents[1] / "api/agent_platform.py").read_text())
    function = next(node for node in ast.walk(tree)
                    if isinstance(node, ast.FunctionDef)
                    and node.name == "_sanitize_compiled_source")
    namespace = {"Any": Any, "AgentFromChatRequest": SimpleNamespace,
                 "re": re, "json": json}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "normalizer", "exec"), namespace)
    request = SimpleNamespace(name="图片微博", prompt="上传附件发布微博",
                              session_id=None, model_tier="medium")
    source = namespace[function.name](request, ["https://weibo.com/**"], {
        "steps": [{"name": "upload", "operation": "input",
                   "target": {"ref": "e168", "intent": "图片上传"},
                   "arguments": {"asset_ids": ["gala-supplied"]}}]}, "test-model")
    assert source["steps"][0]["arguments"] == {"asset_ids": ["gala-supplied"]}
    compiled = compile_source(source)
    assert compiled.valid, compiled.report
    assert compiled.ir["steps"][0]["arguments"]["asset_ids"] == ["gala-supplied"]


def test_current_blank_page_goal_keeps_required_navigation():
    from ai2apps.agent_builder.compiler import compile_source
    tree = ast.parse((Path(__file__).parents[1] / "api/agent_platform.py").read_text())
    function = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "_sanitize_compiled_source")
    namespace = {"Any": Any, "AgentFromChatRequest": SimpleNamespace, "re": re, "json": json}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "normalizer", "exec"), namespace)
    request = SimpleNamespace(name="微博", prompt="从当前空白页面打开微博", page={"url": "about:newtab"}, session_id=None, model_tier="standard")
    source = namespace[function.name](request, [], {"steps": [{"name":"open", "operation":"open", "arguments":{"url":"https://weibo.com/"}}]}, "test")
    assert source["steps"][0]["operation"] == "open"
    assert compile_source(source).valid
