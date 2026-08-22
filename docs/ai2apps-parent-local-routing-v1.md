# AI2Apps Parent Local Routing v1

## Product boundary

A Local may connect another Local as its **Parent Local**. The child receives
only capabilities covered by the parent's revocable Share Grant:

- locally hosted and Local-BYOK models over the OpenAI-compatible endpoint;
- explicitly published Tool, Service, and Agent operations over MCP.

The child never embeds or opens the parent's Apps. Cloud models, Terminal,
Secrets, browser control, and unapproved host-side-effect Tools are not
transitively exposed.

## Core-controlled configuration

Only the device Core user can add, update, test, disable, or remove a parent.
Each connection has:

- a priority from 1 to 1000 (lower is preferred);
- an optional default-parent marker (one per Local);
- independent `route_models` and `route_mcp` switches;
- an active/disabled state and live health state;
- a scoped token stored only in the secure credential backend.

The first Parent Local becomes the default. Changing the default or any route
setting uses an optimistic revision so stale Account/Sharing tabs cannot
overwrite a newer decision.

## Model routing

The global model policy defaults to `explicit_only`:

- `explicit_only`: callers must choose `gateway/{gatewayId}/{modelId}`;
- `parent_first`: for an unqualified model ID, use the healthy default parent
  when it exports that ID, then other healthy parents in priority order;
  if none matches, continue with this Local's normal model resolution.

An explicitly qualified gateway model never silently becomes a local model.
Failure marks that parent offline and removes its model/MCP projection. The
periodic health task probes active parents every 30 seconds by default and
restores projections after recovery. The interval can be changed with
`AI2APPS_PARENT_HEALTH_INTERVAL_SECONDS`; a non-positive value disables only
the periodic task, not manual tests.

## Identity and loop prevention

Every Local derives a non-secret Node ID. Issued connection JSON/QR and MCP
`initialize` include:

```json
{
  "nodeId": "stable-local-node-id",
  "ancestorNodeIds": ["parent-a", "parent-b"]
}
```

Adding a parent is rejected when its Node ID equals the child Node ID or its
ancestry already contains the child. Every health probe reads the live MCP
identity again. This catches stale or altered connection JSON and later graph
changes, including `A -> B -> A`. A changed Node ID also fails closed instead
of silently trusting a replacement server at the saved URL.

Legacy connections without Node identity remain readable for migration
compatibility, but the Sharing UI marks them as identity pending until a live
probe supplies a valid identity.

## Local API

Core-only management endpoints:

```text
GET    /v1/platform/upstreams
POST   /v1/platform/upstreams
PATCH  /v1/platform/upstreams/{gatewayId}
DELETE /v1/platform/upstreams/{gatewayId}
POST   /v1/platform/upstreams/{gatewayId}/probe
GET    /v1/platform/upstreams/routing
PATCH  /v1/platform/upstreams/routing
GET    /v1/platform/upstreams/activity
```

Migration 33 adds Parent identity, ancestry, default, priority, route switches,
and the singleton model-routing policy. Operational activity stores endpoint,
capability ID, outcome, duration, and error code only; it never stores prompts,
responses, Tool arguments, or credentials.

## Acceptance

Unit acceptance covers direct/transitive cycle rejection, default-parent
selection, priority failover, parent-first/local fallback resolution, and live
ancestry revalidation. `scripts/acceptance_two_gateway.py` performs the real
two-instance flow: identity-bound parent creation, probe/projection, MCP Tool
call, parent-first model call, disconnect degradation, and recovery.

The data plane now uses a replaceable `ParentTransport`. LAN uses
`DirectParentTransport`; Cloud Relay will reuse the same manager, routing,
health, and loop protection through a separate adapter. See
`docs/ai2apps-cloud-relay-local-integration-v1.md`.
