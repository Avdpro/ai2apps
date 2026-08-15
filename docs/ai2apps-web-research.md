# AI2Apps Web Research

AI2Apps includes a first-party, read-only research vertical slice:

- `web.search` discovers public web sources and returns structured titles, URLs,
  snippets, and stable source IDs.
- `web.fetch` reads a selected source and returns bounded extracted text plus its
  final URL, title, media type, source ID, fetch time, and truncation state.
- `ai2apps.research-agent` uses those Tools through the durable server-side Agent
  loop and is visible in the Chat Agent selector.

The bundled provider uses Bing's public HTML search endpoint and does not require
an account or API key. The `WebProvider` protocol is the replacement boundary
for future Brave, Tavily, Serper, self-hosted, or MCP-backed providers.

## Safety and permissions

Both Tools require the `network.outbound` capability. The platform's default
fail-closed policy therefore presents an approval checkpoint before the first
network call unless the user has already created a suitable scoped GrantLease.

The HTTP client accepts only public HTTP(S) targets. It rejects credentials in
URLs and any DNS result which is local, private, link-local, reserved, multicast,
or otherwise non-global. Every redirect is checked again. Response media types,
redirect count, time, bytes, and extracted character count are bounded.

Fetched page text is treated as untrusted source data. The Research Agent is
limited to read-only web, Workspace, Resource, and Artifact Tools; its allowlist
does not include Workspace writes, processes, external actions, or delegation.

## Citation contract

Search snippets are discovery hints, not evidence. The Research Agent is
instructed to fetch supporting pages, prefer authoritative primary sources, and
place Markdown links next to supported factual claims. Search and fetch Tool
results remain durable Run Steps, so their source records, latency, failures,
and final answer can be inspected from the normal Agent Run trace.

## Current limits

- HTML, XHTML, plain text, and JSON are supported. PDF/document extraction is a
  separate future Tool layer.
- Search cache is process-local and short-lived. A durable content cache and
  source freshness policy remain future work.
- The initial provider is injectable in Python but does not yet have a provider
  selection or credentials screen in the WebUI.
