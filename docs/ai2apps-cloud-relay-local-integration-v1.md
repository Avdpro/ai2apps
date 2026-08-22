# AI2Apps Cloud Relay — Local Integration v1

## Current Local readiness (implemented 2026-08-16)

Parent capability calls now pass through one replaceable transport boundary:

```text
ParentTransport
  probe(parent, credential)
  invoke_tool(parent, credential, name, arguments, actor context)
  open_model(parent, credential, payload, stream, actor context)
```

`DirectParentTransport` implements the existing LAN Share Grant flow. The
Parent manager owns routing, Node/ancestry validation, health, MCP projection,
activity metadata, and secure credential lookup. Model Server and Tool Gateway
no longer construct direct Parent HTTP requests themselves.

`CloudRelayParentTransport` now implements the OpenAPI 1.10.0 NodeLink data
plane. Schema v34 stores `transport_kind`, `node_link_id`, upstream/downstream
Installation IDs and only a SecretBackend key; the NodeLink credential and
pending pairing code never enter SQLite or browser persistence. Direct Parent
rows remain compatible and default to `direct`.

The Sharing App now provides the full pairing workflow: downstream creates a
ten-minute code/QR, upstream Core accepts it with a one-use purpose-bound Owner
grant, and downstream exchanges it once into a Cloud parent. Model/MCP calls
carry the current downstream actor and membership epoch, not the Core identity.

Cloud NodeLink lifecycle management is also exposed in Sharing: Core can list
links, assign a NodeGrant from the currently active Local exports, set Cloud
concurrency/monthly-point/expiry limits, rotate the one-time credential by QR,
install that credential on the downstream Local, and revoke the link. A Cloud
revocation observed during refresh immediately disables the saved Local route.

Active Agent exports now register six `mcp.agent` connectors (`create_session`,
`send_message`, `get_status`, `get_messages`, `cancel`, `close_session`). Relay
Agent Sessions are isolated by NodeLink just as LAN sessions are isolated by
Share Grant. Relay cancellation endpoints now require the same signed Relay
assertion and request/export binding as the call itself. Cloud policy/quota
HTTP failures are recorded as policy failures and no longer mark the parent as
a transport outage.

The upstream connector exposes only `/federation/models/*` and
`/federation/mcp/*`. It fetches the public Federation JWKS, verifies EdDSA,
issuer/audience, request/export/Installation binding, two-node ancestry and
the 120-second maximum assertion lifetime. These routes bypass the Local API
key but reject every request without a valid `Relay` assertion.

## Mapping required from the Cloud contract

| Local operation | Required Cloud operation |
| --- | --- |
| `probe` models | list current NodeGrant model exports |
| `probe` MCP identity | return serving `nodeId` and complete `ancestorNodeIds` |
| `probe` MCP tools | list current NodeGrant Tool/Service/Agent projections |
| `invoke_tool` | forward one MCP `tools/call` with cancel/disconnect semantics |
| `open_model` | OpenAI-compatible non-stream or streaming chat completion |

Cloud errors must distinguish credential/epoch/revoke/quota/policy failures
from transport unavailability. Policy failures are recorded but do not mark a
healthy parent offline; connection, timeout, and invalid-relay-response failures do.

## Credential rules

- Browser Cloud cookies are not valid relay credentials.
- Device/NodeLink and short relay tokens stay in Local `SecretBackend`.
- SQLite stores only non-secret IDs, transport type, revision, health, and
  capability metadata.
- A short token is audience- and purpose-bound to one serving Node and
  NodeGrant; it cannot call Account, Apps, Platform management, or Mobile APIs.
- Credential refresh is single-flight and does not replay a model or Tool
  request unless the Cloud contract declares the operation idempotent.

## Response validation

The adapter rejects:

- a serving Node different from the configured Parent;
- a path containing this Local Node or any duplicate Node;
- a response whose NodeGrant/epoch differs from the admitted request;
- MCP tools outside the granted export set;
- redirects, non-HTTPS production origins, and oversized responses;
- streams without a terminal event unless cancellation/disconnect is recorded.

Live Node identity is still revalidated by the Parent manager after every
probe, so LAN and Cloud transports receive identical loop protection.

## Production verification

Verified against `https://coder.ai2apps.com` on 2026-08-16:

- `GET /v1/federation/jwks.json`: 200, EdDSA key available;
- Device-authenticated `POST /v1/federation/pairings`: 201;
- pairing code stored only in Local SecretBackend;
- Local schema v34 startup and bound Installation access refresh: successful;
- unauthenticated connector call: 401 `federation_relay_auth_required`;
- 60 Remote/Sharing/Upstream/Platform API tests passed, 1 optional test skipped.

Accept/exchange and actual relayed model/MCP invocation require a second
Cloud-registered Local Installation and an upstream NodeGrant, so they cannot
be completed by pairing this Installation to itself (Cloud correctly rejects
that as a loop).

## Cloud compatibility issue found

The deployed `tools/list` implementation currently filters connector rows with
`item.kind === "mcp.tool"`. The public schema permits `mcp.tool`,
`mcp.service`, and `mcp.agent`; therefore Service and Agent exports are omitted
from discovery even though admission accepts `kind.startsWith("mcp.")`.
Cloud must change the projection filter to include all three MCP kinds and add
a regression test. Local now registers Tool, Service and Agent connectors, but
Service/Agent discovery from a downstream remains incomplete until that Cloud
filter is deployed. Direct `tools/call` admission already accepts all `mcp.*`
kinds.

## Contract acceptance fixtures requested from Cloud

1. successful model/MCP discovery;
2. streaming completion and client cancellation;
3. NodeGrant revoked/epoch mismatch;
4. quota/concurrency rejection;
5. serving Node/path mismatch and cycle;
6. expired short token followed by one safe refresh;
7. connector offline and later recovery.
