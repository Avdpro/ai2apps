# AI2Apps Local Capability Sharing v1

## Scope

This release publishes explicitly selected capabilities from one AI2Apps Local
installation to trusted clients on the same LAN. It has no Cloud discovery,
relay, account, billing, or Node Federation dependency.

Core controls a dedicated LAN listener independently from the localhost server:

- `disabled` (default): no LAN listener;
- `share_only`: only `/v1/share/*` is reachable;
- `full`: the Local web Shell and APIs are reachable, with all existing login,
  member Role, App capability, and resource-ownership checks still enforced.

The default LAN port is `8011`. Changing the mode takes effect immediately and
is persisted across restarts. No upgrade automatically enables LAN access.

The first release supports:

- local model discovery and chat through an OpenAI-compatible base URL;
- Core-selected Local BYOK Provider models through the same endpoint, with
  usage billed to the API Key stored on the upstream device;
- safe Tools through MCP Streamable HTTP and the existing Tool Gateway;
- Core-selected Services projected as their enabled, effect-free MCP methods;
- Core-selected Agents as isolated, asynchronous MCP Session tools;
- independent client credentials, expiry, concurrency limits, rotation, and
  immediate revocation;
- metadata-only invocation audit and request counters;
- a Core-only `Sharing` system App;
- Bonjour/mDNS gateway discovery and client-side QR import;
- downstream health, metadata-only recent activity, and fail-closed projection
  degradation after a transport failure.

Models, Tools, Services, and Agents use the same explicit `CapabilityExport`
and `ShareGrant` contracts. None is exported by default.

## Security boundary

Nothing is exported implicitly. A Core user must create a `CapabilityExport`
and attach it to a `ShareGrant` before the data plane can dispatch it.

The LAN MVP refuses:

- AI2Apps Cloud point-billed models and models projected from another gateway;
- Tools declaring effects, required capabilities, or conditional capability
  rules;
- Terminal, Secrets, browser control, device management, arbitrary processes,
  and App/iframe access;
- caller-supplied actor, installation, organization, billing, or capability
  authority.

An Agent is shareable only when it is enabled and discoverable, and only after
Core explicitly creates an Agent export. Each client Grant receives isolated,
unlisted temporary Sessions. Every Session and Run operation verifies both the
Grant and Agent binding, so one client cannot use another client's Session.
The shared MCP surface deliberately omits interaction approval; a remote
client cannot approve a sensitive action. Revoking a Grant, or pausing or
revoking its Agent export, cancels active Runs and closes the shared Sessions.

A Service export projects only enabled Tools owned by that Service that declare
no effects, required capabilities, or conditional capability rules. Service
lifecycle controls and raw provider endpoints are not exposed.

Share tokens are generated independently from installation API keys, account
cookies, member sessions, and remote connector credentials. SQLite stores only
their SHA-256 digests. A newly issued or rotated token is returned once.

Model eligibility uses explicit source metadata: `local_runtime` and
`local_byok` are shareable; `ai2apps_cloud` and `upstream_gateway` are not.
Legacy `cloud/<provider>/<model>` IDs remain compatible, but Sharing no longer
uses that prefix alone as its authorization decision. A Local BYOK Provider
key never leaves the upstream, and Provider errors redact the stored key.

Audit rows contain grant/export identifiers, operation, status, duration, and
an error code. Prompts, model output, Tool arguments, Tool output, account
cookies, and secrets are not copied into the sharing audit table.

## Management plane

All management routes require the current device Core account:

```text
GET    /v1/platform/sharing/candidates
GET    /v1/platform/sharing/network
PATCH  /v1/platform/sharing/network
GET    /v1/platform/sharing/discovery
POST   /v1/platform/sharing/discovery/refresh
GET    /v1/platform/sharing/exports
POST   /v1/platform/sharing/exports
PATCH  /v1/platform/sharing/exports/{exportId}
GET    /v1/platform/sharing/grants
GET    /v1/platform/sharing/audit
POST   /v1/platform/sharing/grants
POST   /v1/platform/sharing/grants/{grantId}/rotate
POST   /v1/platform/sharing/grants/{grantId}/revoke
```

Creating or rotating a Grant returns:

- the one-time Bearer token;
- an OpenAI-compatible base URL;
- an MCP URL;
- a QR code containing the same connection data.

A Grant may also set a maximum request count. Admission and increment happen
atomically, so concurrent calls cannot exceed that request budget. It provides
a simple BYOK spend guard in addition to expiry and concurrency.

Only Core can change LAN visibility. Network writes use an expected revision
to prevent stale browser tabs from overwriting newer settings. If the selected
port cannot bind, Local fails closed, persists `disabled`, and keeps the
localhost server running.

When LAN access is enabled, Local advertises
`_ai2apps-gateway._tcp.local.` over Bonjour. Its TXT record contains only the
gateway id, display label, listener mode, port, schema and public endpoint
paths. It never contains Share Tokens or capability lists. Discovery does not
grant access: the downstream must still scan or paste a scoped client access
credential issued by the upstream Core user.

The Sharing App can scan a QR with the camera or read a QR image. Parsed
connection data remains in the local browser until the user confirms the
connection; the token is then stored by the Local secure credential backend.

## OpenAI-compatible data plane

Given a returned base URL such as:

```text
http://192.168.1.20:8000/v1/share/shr_...
```

a client uses the one-time token as its API key:

```bash
curl http://192.168.1.20:8000/v1/share/shr_.../models \
  -H 'Authorization: Bearer SHARE_TOKEN'

curl http://192.168.1.20:8000/v1/share/shr_.../chat/completions \
  -H 'Authorization: Bearer SHARE_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"model":"EXPORTED_MODEL","messages":[{"role":"user","content":"Hello"}]}'
```

`/models` filters the underlying runtime response to model IDs explicitly
attached to the Grant. Chat rejects any other model before it reaches the model
runtime. Streaming keeps the Grant concurrency slot until the response stream
finishes or disconnects.

## MCP data plane

The MCP URL is:

```text
http://192.168.1.20:8000/v1/share/shr_.../mcp
```

Every HTTP request must carry the Grant Bearer token. The endpoint implements
the MCP initialization, ping, `tools/list`, and `tools/call` contracts over
Streamable HTTP. `tools/list` contains only active Tool, Service, and Agent
exports attached to the Grant. Service methods still pass through the existing
Tool Gateway for JSON Schema validation, provider identity checks, timeout
handling, and invocation audit.

Each exported Agent contributes `create_session`, `send_message`, `get_status`,
`get_messages`, `cancel`, and `close_session` under
`agent.<agent-key>.*`. `send_message` starts an asynchronous Run and returns its
Run ID. Clients poll status or read the isolated Session. Prompts and Agent
outputs are not copied into the Sharing audit table.

## Persistence

Migration 27 adds:

- `capability_exports`;
- `capability_share_grants`;
- `capability_share_grant_exports`;
- `capability_share_audit`.

Grant revocation is permanent. Export revocation removes the capability from
all attached Grants; a Core user may later create a new export for the same
underlying capability.

Migration 28 adds the Core-controlled LAN listener setting. Migration 29 adds
encrypted upstream gateway connections. Migration 30 adds downstream activity
metadata. The latter stores gateway, operation, capability id, status,
duration, error code and time only—not prompts, responses or Tool arguments.
Migration 31 adds the optional per-Grant request budget.
Migration 32 expands exports to `service` and `agent` while preserving existing
exports, Grants, associations, and audit metadata. Migration 33 formalizes an
upstream connection as a Parent Local, including Node identity/ancestry,
priority/default selection, model/MCP route switches, periodic health, and the
`explicit_only` / `parent_first` model policy. See
`docs/ai2apps-parent-local-routing-v1.md`.

## Deferred work

The next Local-only increments are:

1. per-Agent Core configuration for allowed underlying Tool/Service subsets;
2. interaction forwarding for explicitly safe, non-privilege decisions;
3. per-Grant token and estimated-cost budgets in addition to request count;
4. end-to-end testing from a second physical machine and mixed IPv4/IPv6 LAN;
5. signed gateway identity for Cloud-assisted cross-network discovery.

LAN Parent Local routing is now implemented. Cloud relay remains a separate
transport and authorization phase; it must preserve the same narrow Share
Grant and Node-path semantics rather than exposing Local Apps or management
APIs.
