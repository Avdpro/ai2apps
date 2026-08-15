# SPDX-License-Identifier: Apache-2.0
"""First-party web research Service and Agent contracts."""

from __future__ import annotations

import socket

import pytest

from ai2apps.config import PlatformConfig
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.research.provider import (
    BingWebProvider,
    HttpResponse,
    SafeHttpClient,
    WebProviderError,
)
from ai2apps.services import ToolCallContext


class _FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def get(self, url):
        self.urls.append(url)
        return self.responses.pop(0)


def _runtime(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    return runtime


def test_web_provider_search_fetch_and_cache_are_structured():
    search_html = b"""
    <div class="result">
      <li class="b_algo"><h2><a href="https://example.com/guide">Example Guide</a></h2>
      <div class="b_caption"><p>A useful primary source.</p></div></li>
    </div>
    """
    page_html = b"""
    <html><head><title>Example Guide</title><style>hidden</style></head>
    <body><main><h1>Reliable heading</h1><p>Evidence from the page.</p></main>
    <script>ignore me</script></body></html>
    """
    client = _FakeClient(
        [
            HttpResponse(
                "https://www.bing.com/search?q=test",
                "text/html",
                search_html,
                False,
            ),
            HttpResponse(
                "https://example.com/guide", "text/html", page_html, False
            ),
        ]
    )
    provider = BingWebProvider(client, cache_ttl=60)

    search = provider.search("  test  ", limit=3)
    fetched = provider.fetch(search["results"][0]["url"])
    cached = provider.fetch(search["results"][0]["url"])

    assert search["results"] == [
        {
            "title": "Example Guide",
            "url": "https://example.com/guide",
            "snippet": "A useful primary source.",
            "source_id": search["results"][0]["source_id"],
        }
    ]
    assert fetched["source_id"] == search["results"][0]["source_id"]
    assert fetched["title"] == "Example Guide"
    assert "Reliable heading" in fetched["text"]
    assert "Evidence from the page." in fetched["text"]
    assert "ignore me" not in fetched["text"]
    assert cached["cached"] is True
    assert len(client.urls) == 2


def test_safe_http_client_rejects_private_and_credentialed_targets():
    def resolver(_host, port, **_kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]

    client = SafeHttpClient(resolver=resolver)

    with pytest.raises(WebProviderError, match="private"):
        client._validate_url("http://example.test/secret")
    with pytest.raises(WebProviderError, match="no credentials"):
        client._validate_url("https://user:pass@example.test/")
    with pytest.raises(WebProviderError, match="HTTP"):
        client._validate_url("file:///etc/passwd")


@pytest.mark.asyncio
async def test_platform_registers_web_tools_and_research_agent(tmp_path):
    runtime = _runtime(tmp_path)
    provider = BingWebProvider(
        _FakeClient(
            [
                HttpResponse(
                    "https://www.bing.com/search?q=ai2apps",
                    "text/html",
                    b'<li class="b_algo"><h2><a href="https://example.com/">Example</a></h2></li>',
                    False,
                )
            ]
        )
    )
    # Replace only the bound handler through an isolated service reinstall.
    from ai2apps.research import install_web_research_service

    install_web_research_service(runtime.services, runtime.service_registry, provider)
    agent = runtime.agents.get_definition("ai2apps.research-agent")
    search_tool = runtime.services.get_tool("web.search")

    assert agent.executor_key == "builtin:general-agent"
    assert agent.manifest["discoverable"] is True
    assert agent.manifest["allowed_tools"][:2] == ["web.search", "web.fetch"]
    assert search_tool.required_capabilities == ("network.outbound",)

    result = await runtime.tools.execute(
        "web.search",
        {"query": "ai2apps", "limit": 1},
        context=ToolCallContext(
            caller_id="agent:ai2apps.research-agent",
            granted_capabilities=frozenset({"network.outbound"}),
        ),
    )
    assert result.output["count"] == 1
    assert result.output["results"][0]["url"] == "https://example.com/"


def test_research_agent_is_read_only_by_tool_policy(tmp_path):
    runtime = _runtime(tmp_path)
    agent = runtime.agents.get_definition("ai2apps.research-agent")
    allowed = set(agent.manifest["allowed_tools"])

    assert "workspace.write" not in allowed
    assert "workspace.apply_patch" not in allowed
    assert "process.start" not in allowed
    assert "agent.delegate" not in allowed
