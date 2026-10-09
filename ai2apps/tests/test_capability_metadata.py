import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai2apps.agent_builder.sites import normalize_site_agent_source


@pytest.mark.asyncio
async def test_creation_uses_simple_model_and_preserves_complete_goal():
    tree = ast.parse(Path(__file__).parents[1].joinpath('api/agent_platform.py').read_text())
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == 'summarize_capability')
    calls = []

    async def invoke(*args, **kwargs):
        calls.append(kwargs)
        return {'title': '读取文章列表', 'description': '提取首页文章的标题和链接。'}

    tiers = []
    def resolve(tier):
        tiers.append(tier)
        return 'small-model'

    env = {'json': json, '_invoke_compile_model': invoke,
           'new_entity_id': lambda kind: 'test', 'EntityIdKind': SimpleNamespace(AGENT_RUN='run')}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), 'metadata', 'exec'), env)
    goal = '打开 https://example.com，处理 Cookie，然后读取文章列表，包含 title 和 url。'
    source = {'name': goal[:42], 'description': goal, 'steps': [], 'site_scope': ['https://example.com/**']}
    await env['summarize_capability'](SimpleNamespace(model_manager=SimpleNamespace(resolve_default_model=resolve)), None, None, source, goal)
    assert tiers == ['work_simple']
    assert calls[0]['model_id'] == 'small-model'
    assert json.loads(calls[0]['payload']['messages'][1]['content'])['goal'] == goal
    assert source['description'] == goal
    site = normalize_site_agent_source(source)
    assert site['description'] == goal
    assert site['capabilities'][0]['title'] == '读取文章列表'
    assert site['capabilities'][0]['description'] == '提取首页文章的标题和链接。'
    assert site['capabilities'][0]['steps'] == []
